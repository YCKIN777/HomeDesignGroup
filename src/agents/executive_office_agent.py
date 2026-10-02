# -*- coding: utf-8 -*-
"""executive_office_agent.py — 总经办 Agent（编队计划 v3 · P4，兼平台中控）

职责：审批汇总 + 数据看板 + 跨部门协调 + 审计追溯。
对外闸门：不直接对外；审批动作（折扣/外发/方案/质保认定）全部经此汇总入口人工裁决。
数据来源：audit_log（追溯）、messages/quotes/payments/after_sales（审批件）、业务表（看板）。
"""
from db import get_conn
from agents.base import BaseAgent
from kernel.roles import require


class ExecutiveOfficeAgent(BaseAgent):
    name = "executive_office"
    role = "总经办（审批/看板/协调/审计）"
    capabilities = [
        "审批汇总（外发消息/报价折扣/售后认定待办）",
        "数据看板（线索漏斗/收款/工程进度）",
        "审计追溯（谁/何时/改了什么）",
        "跨部门协调（预留调度入口）",
    ]

    # ---------- 审批汇总 ----------
    def approval_inbox(self, user: str, limit: int = 20) -> dict:
        """汇总三类待审批：外发消息草稿 / 报价折扣待审批 / 售后待处理"""
        with get_conn() as conn:
            drafts = conn.execute(
                "SELECT m.id, m.customer_id, m.content, c.name "
                "FROM messages m LEFT JOIN customers c ON c.id=m.customer_id "
                "WHERE m.approve_status='draft' ORDER BY m.id DESC LIMIT ?",
                (limit,)).fetchall()
            quotes = conn.execute(
                "SELECT q.id, q.project_id, q.total, q.discount, q.status "
                "FROM quotes q WHERE q.status='待审批' ORDER BY q.id DESC LIMIT ?",
                (limit,)).fetchall()
            aftersales = conn.execute(
                "SELECT a.id, a.project_id, a.kind, a.title, a.status "
                "FROM after_sales a WHERE a.status IN ('待处理','处理中') "
                "ORDER BY a.id DESC LIMIT ?", (limit,)).fetchall()
        return {
            "pending_messages": [dict(r) for r in drafts],
            "pending_quote_approvals": [dict(r) for r in quotes],
            "pending_after_sales": [dict(r) for r in aftersales],
        }

    # ---------- 数据看板 ----------
    def dashboard(self, user: str) -> dict:
        with get_conn() as conn:
            funnel = conn.execute(
                "SELECT status, COUNT(*) AS n FROM customers GROUP BY status "
                "ORDER BY n DESC").fetchall()
            projects = conn.execute(
                "SELECT status, COUNT(*) AS n FROM projects GROUP BY status "
                "ORDER BY n DESC").fetchall()
            collected = conn.execute(
                "SELECT COALESCE(SUM(amount),0) AS s FROM payments").fetchone()["s"]
            quotes_total = conn.execute(
                "SELECT COALESCE(SUM(total),0) AS s FROM quotes "
                "WHERE status IN ('已审批','已签约')").fetchone()["s"]
            inspections = conn.execute(
                "SELECT COUNT(*) AS n FROM inspections WHERE result='合格'").fetchone()["n"]
            todos_open = conn.execute(
                "SELECT COUNT(*) AS n FROM todos WHERE done=0").fetchone()["n"]
        return {
            "customers_by_status": [dict(r) for r in funnel],
            "projects_by_status": [dict(r) for r in projects],
            "payments_collected": collected,
            "approved_quotes_total": quotes_total,
            "inspections_passed": inspections,
            "open_todos": todos_open,
        }

    # ---------- 审计追溯 ----------
    def audit_trail(self, user: str, limit: int = 30) -> list:
        require(user, "audit")
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT id,user,action,target,before,after,time AS created_at FROM audit_log "
                "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ---------- 协调入口（预留：跨部门指令落 audit 留痕） ----------
    def coordinate(self, user: str, note: str) -> dict:
        from db import audit
        audit(user, "跨部门协调", "executive_office", after=note[:200])
        return {"ok": True, "note": note}

    def handle(self, ctx, message: str):
        return self.todo("总经办 Agent：approval_inbox/dashboard/audit_trail/coordinate")
