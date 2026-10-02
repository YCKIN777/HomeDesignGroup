# -*- coding: utf-8 -*-
"""sop_agent — 跟进节奏与提醒（M7）"""
from datetime import datetime, timedelta

from .base import BaseAgent
from db import get_conn
from kernel import config_loader


class SopAgent(BaseAgent):
    name = "sop"
    role = "SOP 节奏提醒"
    capabilities = [
        "按配置包节奏生成跟进待办",
        "检测逾期（首联 24h / 3-7-15 天）",
        "推送站内提醒",
        "统计响应时长中位数",
    ]

    def __init__(self):
        self.cfg = config_loader.load_profile("壹城精工")
        self.first_hours = self.cfg["rules"]["sop"]["first_contact_hours"]

    def check_due(self) -> list:
        """扫描并生成待办：① 首联超时 ② 到期跟进。幂等：同客户同类未完成待办不重复"""
        with get_conn() as conn:
            # ① 首联超时：线索创建 > N 小时 且 无已发送外呼消息
            overdue = conn.execute(
                "SELECT c.id FROM customers c WHERE c.status IN ('线索','跟进') "
                "AND NOT EXISTS (SELECT 1 FROM messages m WHERE m.customer_id=c.id "
                "AND m.direction='out' AND m.approve_status='sent') "
                "AND (julianday('now','localtime') - julianday(c.created_at)) * 24 > ?",
                (self.first_hours,)).fetchall()
            for r in overdue:
                exists = conn.execute(
                    "SELECT id FROM todos WHERE customer_id=? AND task LIKE '首联超时%' AND done=0",
                    (r["id"],)).fetchone()
                if not exists:
                    conn.execute(
                        "INSERT INTO todos(customer_id, task) VALUES(?,?)",
                        (r["id"], f"首联超时（>{self.first_hours}h）：尽快联系客户"))
            # ② 到期跟进：followups.next_at 已到且未处理
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            due = conn.execute(
                "SELECT customer_id, content, next_at FROM followups "
                "WHERE next_at <= ? AND next_at != ''", (now,)).fetchall()
            for r in due:
                exists = conn.execute(
                    "SELECT id FROM todos WHERE customer_id=? AND task LIKE '%SOP跟进%' "
                    "AND due_at=? AND done=0", (r["customer_id"], r["next_at"])).fetchone()
                if not exists:
                    conn.execute(
                        "INSERT INTO todos(customer_id, task, due_at) VALUES(?,?,?)",
                        (r["customer_id"], f"SOP跟进: {r['content'][:30]}", r["next_at"]))
            todos = conn.execute(
                "SELECT t.*, c.name, c.phone FROM todos t LEFT JOIN customers c "
                "ON c.id=t.customer_id WHERE t.done=0 ORDER BY t.id DESC LIMIT 50").fetchall()
            return [dict(t) for t in todos]

    def handle(self, ctx, message: str):
        return self.todo("M7 已实现（check_due）")
