# -*- coding: utf-8 -*-
"""customer_service_agent.py — 客服 Agent（编队计划 v3 · P3）

职责：前台客服——首联/咨询/跟进回复，AI 起草→收件箱人审后发（M3a），渠道消息接入（M3b）。
对外闸门：外发消息一律人工审批（Sentinel external_send / approve_status=draft→sent）。
行为不变：起草委托业务员 Agent（LeadAgent）；收件箱/审批/驳回逻辑由 main.py 迁入。
"""
from db import get_conn, audit
from agents.business_agent import BusinessAgent
from agents.base import BaseAgent


class CustomerServiceAgent(BaseAgent):
    name = "customer_service"
    role = "客服（前台：首联/跟进/人审后发）"
    capabilities = [
        "首联/跟进消息起草（AI 起草，人审后发）",
        "收件箱待审批草稿管理",
        "审批发送/驳回（防重复审批）",
        "渠道消息接入（webhook.ingest）",
    ]

    def __init__(self):
        self.business = BusinessAgent()

    # ---------- 起草（委托业务员，收件箱在客服侧） ----------
    def prepare_draft(self, user: str, customer_id: int, kind: str = "first_contact",
                      context: str = "") -> dict:
        return self.business.prepare_draft(user, customer_id, kind, context)

    # ---------- 收件箱 ----------
    def inbox(self, limit: int = 10) -> list:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT m.id,m.customer_id,m.content,m.created_at,c.name FROM messages m "
                "LEFT JOIN customers c ON c.id=m.customer_id "
                "WHERE m.approve_status='draft' ORDER BY m.id DESC LIMIT ?",
                (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ---------- 人审后发 ----------
    def approve(self, user: str, message_id: int) -> dict:
        with get_conn() as conn:
            row = conn.execute("SELECT approve_status FROM messages WHERE id=?",
                               (message_id,)).fetchone()
            if not row:
                raise ValueError(f"消息 {message_id} 不存在")
            if row["approve_status"] != "draft":
                raise ValueError(f"消息已 {row['approve_status']}，不可重复审批")
            conn.execute("UPDATE messages SET approve_status='sent' WHERE id=?", (message_id,))
            audit(user, "审批发送", f"messages#{message_id}", before="draft", after="sent")
        return {"id": message_id, "status": "sent"}

    def reject(self, user: str, message_id: int, reason: str = "") -> dict:
        reason = reason or "未说明"
        with get_conn() as conn:
            row = conn.execute("SELECT approve_status FROM messages WHERE id=?",
                               (message_id,)).fetchone()
            if not row:
                raise ValueError(f"消息 {message_id} 不存在")
            if row["approve_status"] != "draft":
                raise ValueError(f"消息已 {row['approve_status']}，不可驳回")
            conn.execute("UPDATE messages SET approve_status='rejected' WHERE id=?",
                         (message_id,))
            audit(user, "驳回", f"messages#{message_id}", before="draft", after=f"rejected:{reason}")
        return {"id": message_id, "status": "rejected", "reason": reason}

    # ---------- 渠道接入（M3b：webhook 落库，机器入口） ----------
    def channel_ingest(self, channel: str, phone: str, content: str,
                       name: str = "", source: str = "") -> dict:
        """渠道消息接入：自动建档（去重）+ 记入 messages + 触发首联待办"""
        r = self.business.ingest("system", phone, name=name or "", channel=channel,
                                 source=source or channel)
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO messages(customer_id, direction, content, author, approve_status) "
                "VALUES(?,?,?,?,'sent')",
                (r["id"], "in", content, f"渠道:{channel}"))
        return {"lead": r, "message_recorded": True}

    def handle(self, ctx, message: str):
        return self.todo("客服 Agent：prepare_draft/inbox/approve/reject/channel_ingest")
