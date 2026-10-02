# -*- coding: utf-8 -*-
"""scoring_agent — 线索评分分级（M6）"""
from .base import BaseAgent
from db import get_conn, audit
from kernel import config_loader


class ScoringAgent(BaseAgent):
    name = "scoring"
    role = "评分分级（A/B/C 意向）"
    capabilities = [
        "评估需求真实性（有房/面积/预算）",
        "评估意向度（时间/进度/急迫度）",
        "输出评分与分级建议",
        "触发下一步 SOP",
    ]

    def __init__(self):
        self.cfg = config_loader.load_profile("壹城精工")
        self.th = self.cfg["rules"].get("scoring", {"A": 80, "B": 50})

    def score(self, user: str, customer_id: int) -> dict:
        """真实性(0-60) + 意向度(0-40) → 0-100，按规则分级 A/B/C"""
        with get_conn() as conn:
            c = conn.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
            if not c:
                raise ValueError(f"客户 {customer_id} 不存在")
            cd = dict(c)
        real = 0
        if cd.get("estate"): real += 20        # 有楼盘
        if cd.get("area"): real += 20          # 有面积
        if cd.get("budget_range"): real += 20  # 有预算
        intent = 0
        if cd.get("intent_time"): intent += 20  # 有意向时间
        if cd.get("tags"): intent += 10         # 有需求标签
        if cd.get("status") in ("跟进", "邀约", "到店", "派单"): intent += 10  # 已推进
        score = min(100, real + intent)
        grade = "A" if score >= self.th.get("A", 80) else \
                "B" if score >= self.th.get("B", 50) else "C"
        with get_conn() as conn:
            conn.execute("UPDATE customers SET score=? WHERE id=?", (score, customer_id))
        audit(user, "评分分级", f"customers#{customer_id}", after=f"{score}分/{grade}")
        return {"id": customer_id, "score": score, "grade": grade,
                "breakdown": {"真实性": real, "意向度": intent}}

    def handle(self, ctx, message: str):
        return self.todo("M6 已实现（score）")
