# -*- coding: utf-8 -*-
"""verify_sentinel.py — Step 4 自检：Sentinel 5 条规则单元测试"""
import sys

sys.path.insert(0, r"H:\AgentProjects\HomeDesignGroup\src")

from kernel.sentinel import (
    DRAFT, EXTERNAL_SEND, OWNER_EDIT, PAYMENT, READ, THIRD_PARTY_API,
    PendingHuman, SentinelDecision, SentinelDenied,
    evaluate, sentinel_check, sentinel_mode,
)

fails = []


def check(name, cond, msg):
    if not cond:
        fails.append(name)
        print(f"[FAIL] {name}: {msg}")
    else:
        print(f"[PASS] {name}")


# 0. 默认 strict 模式
check("默认 strict 模式", sentinel_mode() == "strict", f"mode={sentinel_mode()}")

# 规则1：查资料/写草稿/生成报价（不对外）→ 自动放行
d1 = evaluate(READ)
check("规则1 read 自动放行", d1.allowed and not d1.needs_human, f"{d1}")
d2 = evaluate(DRAFT)
check("规则1 draft 自动放行(记审计)", d2.allowed and d2.audit_required, f"{d2}")

# 规则2：发微信消息 → pending_human（人工点发送）
d3 = evaluate(EXTERNAL_SEND)
check("规则2 external_send 待人工", d3.needs_human and d3.audit_required, f"{d3}")


@sentinel_check(EXTERNAL_SEND)
def _send_wechat(owner, content):
    return "已发送"


try:
    _send_wechat("业主A", "进度消息")
    check("规则2 实际发送被拦", False, "应抛 PendingHuman")
except PendingHuman:
    check("规则2 实际发送被拦(草稿态)", True, "")

# 规则3：下单/付款 → 拒绝自动，仅订单摘要
d4 = evaluate(PAYMENT)
check("规则3 payment 拒绝自动", not d4.allowed and d4.needs_human, f"{d4}")


@sentinel_check(PAYMENT)
def _pay(order_id):
    return "扣款成功"


try:
    _pay(1)
    check("规则3 自动扣款被拒", False, "应抛 SentinelDenied")
except SentinelDenied as e:
    check("规则3 自动扣款被拒(带摘要)", isinstance(e.summary, dict), f"summary={e.summary}")

# 规则4：修改 owners 预算/户型 → 二次确认
d5 = evaluate(OWNER_EDIT)
check("规则4 owner_edit 需二次确认", d5.needs_human, f"{d5}")


@sentinel_check(OWNER_EDIT)
def _edit_budget(owner_id, new_budget):
    return f"预算已改为 {new_budget}"


try:
    _edit_budget(7, 900000)
    check("规则4 首次修改被拦", False, "应抛 PendingHuman(二次确认)")
except PendingHuman:
    check("规则4 首次修改被拦(待确认)", True, "")

# 规则5：第三方 API（非只读）→ 审计
d6 = evaluate(THIRD_PARTY_API)
check("规则5 third_party_api 记审计", d6.allowed and d6.audit_required, f"{d6}")


@sentinel_check(THIRD_PARTY_API)
def _call_3rd():
    return "ok"


check("规则5 第三方API可执行(带审计要求)", _call_3rd() == "ok", "执行失败")

# 模式切换：auto 放行所有（仅开发调试）
import os
os.environ["SENTINEL_MODE"] = "auto"
da = evaluate(PAYMENT)
check("auto 模式放行（调试）", da.allowed, f"{da}")
os.environ["SENTINEL_MODE"] = "strict"

# 白名单：strict 下放行指定动作
os.environ["SENTINEL_AUTO_ALLOWED"] = "payment"
dw = evaluate(PAYMENT)
check("strict+白名单放行 payment", dw.allowed, f"{dw}")
os.environ.pop("SENTINEL_AUTO_ALLOWED", None)

print("\n" + ("全部通过" if not fails else f"{len(fails)} 项失败"))
sys.exit(1 if fails else 0)
