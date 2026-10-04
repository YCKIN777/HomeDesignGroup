# -*- coding: utf-8 -*-
"""invite_agent — 邀约到店·回捞（M8）"""
from .base import BaseAgent
from db import get_conn, audit, customer_summary
from memory_manager import MemoryManager
from kernel import config_loader


class InviteAgent(BaseAgent):
    name = "invite"
    role = "邀约到店·回捞"
    capabilities = [
        "生成邀约话术（含到店卖点）",
        "记录邀约时间地点与爽约状态",
        "爽约回捞策略",
        "统计到店转化",
    ]

    def __init__(self):
        self.mm = MemoryManager()
        self.cfg = config_loader.load_profile("壹城精工")

    def create_invite(self, user: str, customer_id: int, when: str = "",
                      where: str = "公司展厅") -> dict:
        """生成邀约（话术 AI 起草→存 followups，状态→邀约）"""
        with get_conn() as conn:
            c = conn.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
            if not c:
                raise ValueError(f"客户 {customer_id} 不存在")
            cd = dict(c)
        from llm import get_llm
        sys_prompt = self.mm.build_system_prompt(self.cfg)
        content = get_llm().chat([
            {"role": "system", "content": sys_prompt + "\n纪律: AI 只起草，人审批后发。"},
            {"role": "user", "content":
                f"客户: {customer_summary(cd)}\n写一条到店邀约话术，时间{when or '另行约定'}，"
                f"地点{where}，突出案例与免费量房。"},
        ])
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO followups(customer_id, channel, content, result, next_at) "
                "VALUES(?,?,?,?,?)",
                (customer_id, "邀约", content, "待确认", when))
            fid = cur.lastrowid
            conn.execute("UPDATE customers SET status='邀约' WHERE id=?", (customer_id,))
            audit(user, "邀约", f"followups#{fid}", after=f"{when}@{where}")
        return {"id": fid, "customer_id": customer_id, "content": content,
                "when": when, "where": where}

    def noshow(self, user: str, customer_id: int) -> dict:
        """爽约回捞：记录并重新生成跟进"""
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO followups(customer_id, channel, content, result) VALUES(?,?,?,?)",
                (customer_id, "爽约回捞", "客户爽约，需回捞", "爽约"))
            audit(user, "爽约回捞", f"customers#{customer_id}")
        return self.create_invite(user, customer_id, when="", where="可线上方案讲解")

    def handle(self, ctx, message: str):
        return self.todo("M8 已实现（create_invite/noshow）")
