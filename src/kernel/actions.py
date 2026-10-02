# -*- coding: utf-8 -*-
"""
actions.py — 动作注册表（Step 4.7，对齐 Palantir Action Types + Functions）
把散落在各路由/Agent 里的写操作收拢为"可治理动作单元"：
  每个动作显式声明：所需权限动作 / 前置条件(guard) / 副作用(side_effects) / 审计
用途：
  - describe_actions(user)：某账号可执行动作清单（供工作台 CAN() 与 MCP 工具声明）
  - check_action(user, name)：动作级权限+前置校验（与 roles.py 联动）
  - execute(name, user, target, before, after)：统一审计执行入口（对齐"每个动作
    是权限+审计+副作用声明"的治理单元；业务实现仍在各 Agent/路由，本层负责声明与记账）
"""
from kernel.roles import allowed

REGISTRY = {}   # name -> dict(label, roles, guard, side_effects, audit)


def _register(name: str, label: str, roles: str, guard: str,
              side_effects: str, audit: bool = True):
    REGISTRY[name] = {
        "name": name,
        "label": label,
        "roles": roles,            # 所需权限动作名（roles.py 判定）
        "guard": guard,            # 前置条件（人类可读）
        "side_effects": side_effects,  # 副作用（人类可读）
        "audit": audit,
    }


# ---------- 线索域 ----------
_register("lead.write", "录线索/建档打标", "lead.write",
          "手机号非空", "customers 新增或合并（按手机号去重），L2 记忆载入")
_register("lead.import", "JSON 批量导入线索", "lead.write",
          "rows 每行含 phone", "按手机号去重合并，返回 created/merged/error 统计")
_register("lead.csv", "CSV 批量导入线索", "lead.write",
          "csv_text 表头与模板一致，UTF-8/BOM 兼容", "同上，经 csv 解析后走同一导入核心")
_register("transition", "客户状态迁移", "transition",
          "迁移须在 workflow 合法边内（非法迁移被拦截）", "customers.status 变更 + 审计")
_register("score", "意向评分", "score",
          "客户存在", "customers.score 更新 0-100（阈值走配置）")
_register("invite", "邀约到店", "invite",
          "客户存在且已建档", "生成邀约安排（时间/地点），可触发到店跟进")
_register("noshow", "爽约回捞", "invite",
          "存在未到店邀约", "邀约标记未到店，生成回捞跟进")

# ---------- 收件箱域 ----------
_register("draft", "AI 起草待发消息", "draft",
          "客户存在", "messages 新增 draft 状态消息（人审后发）")
_register("approve", "审批通过并发送", "approve",
          "消息处于 draft 且未被处理（重复审批 409）", "messages draft→approved/sent，触发外呼/发送")
_register("reject", "审批驳回", "approve",
          "消息处于 draft 且未被处理", "messages draft→rejected")

# ---------- 派单/项目域 ----------
_register("dispatch", "派单建项目", "dispatch",
          "客户存在且未派单（防重复）", "projects 新增，客户状态→派单，生成设计师待办")
_register("design_plan", "设计方案沉淀/流转", "design_plan",
          "项目存在", "design_plans 新增版本或状态流转（初稿→评审中→已定稿/已否决）")
_register("quote", "报价生成/折扣提交", "quote",
          "项目存在且未签约", "quotes 新增草稿；提交折扣后低于阈值自动转待审批")
_register("quote.approve", "报价审批（折扣）", "quote.approve",
          "报价处于待审批", "quotes 待审批→已审批/已否决（审批人=配置 approver_role）")
_register("site_report", "工地日报", "site_report",
          "项目存在", "site_reports 新增日报（阶段+内容）")
_register("inspection", "节点验收", "inspection",
          "项目存在且验收节点合法（水电/防水/泥木/油漆/竣工）", "inspections 写入结果（待验收/合格/整改）")

# ---------- 沉淀域 ----------
_register("sediment", "沉淀提交", "sediment",
          "通过提炼准入 4 条（实例/可复现/匿名/不违内核）", "sedimentation_items 新增候选")
_register("review", "沉淀评审", "review",
          "目标状态为 已入内核/已剔除", "候选→已入内核/已剔除")

# ---------- 事务/记忆域 ----------
_register("todo.done", "待办完成", "todo.done",
          "待办存在", "todos.done 置 1（SOP 提醒闭环）")
_register("memory.write", "记忆写入/追加", "memory.write",
          "记忆文件可写", "memory/*.md 写入或追加（含本体 frontmatter）")
_register("webhook.ingest", "渠道消息接入", "webhook.ingest",
          "渠道来源合法（内部/渠道账号放行）", "渠道消息转线索或客户记录")


def describe_actions(user: str) -> list:
    """返回某账号可执行的动作清单（读开放；写动作按权限过滤）"""
    out = []
    for name, a in REGISTRY.items():
        ok, _ = allowed(user, a["roles"])
        if ok:
            out.append(dict(a))
    return out


def check_action(user: str, name: str) -> tuple:
    """动作级校验：返回 (是否允许, 说明)。未知动作拒绝。"""
    a = REGISTRY.get(name)
    if a is None:
        return False, f"未知动作: {name}"
    return allowed(user, a["roles"])


def execute(name: str, user: str, target: str, before=None, after=None):
    """动作统一记账入口：校验权限后写审计（业务实现仍在各 Agent/路由）。
    对齐"每个动作=权限+审计+副作用声明"的治理单元；返回 (ok, 说明)。"""
    ok, msg = check_action(user, name)
    if not ok:
        return False, msg
    if REGISTRY[name]["audit"]:
        from db import audit as _audit
        _audit(user, name, target, before=before, after=after)
    return True, msg


if __name__ == "__main__":
    # 自检：注册表完整性 + 各角色可执行动作
    from kernel.roles import role_of
    print(f"[actions] 注册动作 {len(REGISTRY)} 个：{', '.join(REGISTRY)}")
    for u in ("admin", "客服", "销售", "董事长"):
        acts = describe_actions(u)
        print(f"[actions] {u} -> {len(acts)} 个：{', '.join(a['name'] for a in acts)}")
