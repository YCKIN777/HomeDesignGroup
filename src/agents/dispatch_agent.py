# -*- coding: utf-8 -*-
"""dispatch_agent — 派单给设计师（M4）"""
from .base import BaseAgent
from db import get_conn, audit, customer_summary


class DispatchAgent(BaseAgent):
    name = "dispatch"
    role = "派单·建项目（客服→设计师）"
    capabilities = [
        "根据需求摘要匹配设计师",
        "创建项目进入状态机（量房）",
        "生成派单站内待办",
        "记录派单及时率",
    ]

    def dispatch(self, user: str, customer_id: int, designer: str = None) -> dict:
        """派单：建项目(status=量房) + 客户状态→派单 + 站内待办"""
        with get_conn() as conn:
            c = conn.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
            if not c:
                raise ValueError(f"客户 {customer_id} 不存在")
            cd = dict(c)
            # 幂等：已有未关闭项目则不重复建
            exist = conn.execute(
                "SELECT id FROM projects WHERE customer_id=? AND status='量房'",
                (customer_id,)).fetchone()
            if exist:
                return {"id": exist["id"], "customer_id": customer_id, "dup": True}
            summary = customer_summary(cd)
            cur = conn.execute(
                "INSERT INTO projects(customer_id, designer, summary, status, dispatched_at) "
                "VALUES(?,?,?,?, datetime('now','localtime'))",
                (customer_id, designer or "待分配", summary, "量房"))
            pid = cur.lastrowid
            conn.execute("UPDATE customers SET status='派单' WHERE id=?", (customer_id,))
            conn.execute(
                "INSERT INTO todos(customer_id, task, due_at) VALUES(?,?, datetime('now','localtime'))",
                (customer_id, f"设计师跟进: {summary[:40]}"))
            audit(user, "派单", f"projects#{pid}", after=f"designer={designer or '待分配'}")
            return {"id": pid, "customer_id": customer_id, "dup": False, "summary": summary}

    def handle(self, ctx, message: str):
        return self.todo("M4 已实现（dispatch）")
