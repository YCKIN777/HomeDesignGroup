# -*- coding: utf-8 -*-
"""sentinel.py — Sentinel 审批闸门（架构契约 v0.1 原则 3）

所有 Agent 想"对外做事"的动作，执行前必须过 Sentinel。规则集中在此表，
统一在一个地方改（@sentinel_check 装饰器挂到 tool 函数）。

规则表（契约 5 条，SENTINEL_MODE=strict 默认）：
  read              查资料/写草稿/生成报价/报告（不对外）→ 自动放行
  draft             生成草稿（人审后发流程入口）        → 自动放行
  external_send     发微信消息给业主/工长              → pending_human（必须人工点发送）
  payment           下单/付款/调用支付接口             → deny_auto（拒绝自动，仅订单摘要给人工确认）
  owner_edit        修改 owners 档案预算/户型字段      → require_confirm（二次确认）
  third_party_api   调用第三方 API（非只读）           → audit（记录谁/何时/改了什么/可回滚）

模式：SENTINEL_MODE=strict（生产默认）| auto（仅开发调试放行所有）；
      SENTINEL_AUTO_ALLOWED=逗号分隔的动作类型白名单（strict 下对这些动作放行）。
"""
import os
from dataclasses import dataclass, field
from functools import wraps

from providers.env import get_env

# ------- 动作类型分类 -------
READ = "read"
DRAFT = "draft"
EXTERNAL_SEND = "external_send"
PAYMENT = "payment"
OWNER_EDIT = "owner_edit"
THIRD_PARTY_API = "third_party_api"


@dataclass
class SentinelDecision:
    """一次 Sentinel 评估结果"""
    action_type: str
    allowed: bool                # 是否放行执行
    needs_human: bool = False    # True=须人工确认后才执行（如点"发送"）
    audit_required: bool = False  # True=必须记审计（可回滚）
    reason: str = ""
    meta: dict = field(default_factory=dict)


class SentinelDenied(Exception):
    """Sentinel 拒绝自动执行（payment 等）；携带给人工的订单摘要"""

    def __init__(self, summary: dict, message: str = "Sentinel 拒绝自动执行，请人工确认"):
        self.summary = summary
        super().__init__(message)


class PendingHuman(Exception):
    """动作已生成草稿/待确认，须人工触发才真正对外执行"""

    def __init__(self, draft: dict, message: str = "已生成草稿，等待人工发送/确认"):
        self.draft = draft
        super().__init__(message)


# ------- 规则表（唯一改规则的地方） -------
RULES = {
    READ:           {"strategy": "allow",      "needs_human": False, "audit": False},
    DRAFT:          {"strategy": "allow",      "needs_human": False, "audit": True},
    EXTERNAL_SEND:  {"strategy": "pending",    "needs_human": True,  "audit": True},
    PAYMENT:        {"strategy": "deny",       "needs_human": True,  "audit": True},
    OWNER_EDIT:     {"strategy": "confirm",    "needs_human": True,  "audit": True},
    THIRD_PARTY_API: {"strategy": "audit",     "needs_human": False, "audit": True},
}


def sentinel_mode() -> str:
    return get_env("SENTINEL_MODE", "strict").strip().lower() or "strict"


def auto_allowed_set() -> set:
    raw = get_env("SENTINEL_AUTO_ALLOWED", "")
    return {x.strip() for x in raw.split(",") if x.strip()}


def evaluate(action_type: str) -> SentinelDecision:
    """按规则表 + 模式评估动作。auto 模式放行所有（仅开发调试）。"""
    if action_type not in RULES:
        raise ValueError(f"未知动作类型: {action_type}（可选 {list(RULES)}）")
    if sentinel_mode() == "auto":
        return SentinelDecision(action_type, allowed=True, reason="SENTINEL_MODE=auto 放行（仅调试）")
    rule = RULES[action_type]
    if action_type in auto_allowed_set():
        return SentinelDecision(action_type, allowed=True,
                                reason=f"SENTINEL_AUTO_ALLOWED 白名单放行: {action_type}")
    # allow/audit/pending/confirm 都放行"动作本身"（草稿/待确认拦截对外执行）；
    # 仅 deny 拒绝自动执行
    return SentinelDecision(
        action_type,
        allowed=(rule["strategy"] != "deny"),
        needs_human=rule["needs_human"],
        audit_required=rule["audit"],
        reason=f"Sentinel[{rule['strategy']}] {action_type}")


def sentinel_check(action_type: str, user: str = "system"):
    """装饰器：挂到 tool 函数上，统一过闸门。

    用法：
        @sentinel_check("external_send", user="sales01")
        def send_wechat(owner, content): ...

    行为（strict）：
        allow      → 直接执行
        audit      → 执行 + 记审计（调用方负责 audit）
        pending    → 抛 PendingHuman（草稿进 pending_human，人工点发送才执行）
        deny       → 抛 SentinelDenied（附订单摘要给人工确认）
        confirm    → 第一次调用抛 PendingHuman 请求二次确认；带 confirm_token 才执行
    """

    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            decision = evaluate(action_type)
            if not decision.allowed:
                # deny：拒绝自动执行，构造订单摘要（由被装饰函数提供 summary 时用之）
                summary = kwargs.pop("_summary", {}) or {}
                raise SentinelDenied(summary)
            if decision.needs_human and decision.action_type != DRAFT:
                # pending/confirm：抛待人工确认（草稿态）
                draft = kwargs.pop("_draft", {}) or {}
                raise PendingHuman(draft)
            # allow / audit：执行；audit 由调用方按既有 audit_log 机制记账
            return fn(*args, **kwargs)

        return wrapper

    return deco
