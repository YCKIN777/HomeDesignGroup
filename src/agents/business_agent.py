# -*- coding: utf-8 -*-
"""business_agent.py — 业务员 Agent（编队计划 v3 · P2 归并收敛）

组合：lead(线索归集/建档/起草) + scoring(评分) + sop(SOP待办) + invite(邀约)
职责：跑业务全链路——线索→建档打标→评分→SOP跟进→邀约到店。
对外闸门：邀约发送人工确认（Sentinel external_send）。
行为不变：内部委托原 Agent 类，接口与 main.py 原 handler 语义一致。
"""
from db import get_conn
from agents.lead_agent import LeadAgent
from agents.scoring_agent import ScoringAgent
from agents.sop_agent import SopAgent
from agents.invite_agent import InviteAgent
from agents.base import BaseAgent


class BusinessAgent(BaseAgent):
    name = "business"
    role = "业务员（获客运营）"
    capabilities = [
        "线索归集/去重/建档打标",
        "评分分级 A/B/C",
        "SOP 跟进待办与逾期提醒",
        "邀约到店与爽约回捞",
        "首联/跟进消息起草（人审后发）",
    ]

    def __init__(self):
        self.lead = LeadAgent()
        self.scoring = ScoringAgent()
        self.sop = SopAgent()
        self.invite = InviteAgent()

    # ---------- M1 线索归集 ----------
    def ingest(self, user: str, phone: str, **fields) -> dict:
        return self.lead.ingest(user, phone, **fields)

    # ---------- M2 建档打标 ----------
    def profile(self, user: str, customer_id: int, **fields) -> dict:
        return self.lead.profile(user, customer_id, **fields)

    # ---------- 状态迁移 ----------
    def transition(self, user: str, customer_id: int, to: str) -> dict:
        return self.lead.transition(user, customer_id, to)

    # ---------- M3a 首联起草（人审后发，收件箱在客服 Agent 侧） ----------
    def prepare_draft(self, user: str, customer_id: int, kind: str = "first_contact",
                      context: str = "") -> dict:
        return self.lead.prepare_draft(user, customer_id, kind, context)

    # ---------- M6 评分分级 ----------
    def score(self, user: str, customer_id: int) -> dict:
        return self.scoring.score(user, customer_id)

    # ---------- M7 SOP 待办 ----------
    def check_due(self) -> list:
        return self.sop.check_due()

    # ---------- M8 邀约 ----------
    def create_invite(self, user: str, customer_id: int, when: str = "",
                      where: str = "公司展厅") -> dict:
        return self.invite.create_invite(user, customer_id, when, where)

    def noshow(self, user: str, customer_id: int) -> dict:
        return self.invite.noshow(user, customer_id)

    # ---------- 查询视图（客户列表/详情，供中控与看板复用） ----------
    def list_customers(self, limit: int = 20) -> list:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT id,name,phone,estate,status,score FROM customers "
                "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def get_customer(self, customer_id: int) -> dict:
        with get_conn() as conn:
            row = conn.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
            if not row:
                raise ValueError(f"客户 {customer_id} 不存在")
            d = dict(row)
        l2 = self.lead.mm.load_l2(customer_id)
        d["l2"] = l2
        return d

    def handle(self, ctx, message: str):
        return self.todo("业务员 Agent：ingest/profile/transition/score/check_due/create_invite/prepare_draft")
