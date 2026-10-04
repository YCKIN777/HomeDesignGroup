# -*- coding: utf-8 -*-
"""lead_agent — 线索归集·建档·首联（M1/M2/M3a）"""
import re

from .base import BaseAgent
from db import get_conn, audit, customer_summary
from memory_manager import MemoryManager
from kernel import config_loader


class LeadAgent(BaseAgent):
    name = "lead"
    role = "线索归集·建档·首联（获客→客服）"
    capabilities = [
        "识别线索来源渠道并去重",
        "结构化提取客户需求标签",
        "起草首联消息（人审后发）",
        "判定线索真实性与意向",
    ]

    def __init__(self):
        self.mm = MemoryManager()
        self.cfg = config_loader.load_profile("壹城精工")

    # ---------- M1 线索归集（电话去重合并） ----------
    def ingest(self, user: str, phone: str, **fields) -> dict:
        phone = (phone or "").strip()
        if not re.fullmatch(r"1\d{10}", phone):
            raise ValueError(f"手机号格式不正确: {phone}")
        with get_conn() as conn:
            row = conn.execute("SELECT id FROM customers WHERE phone=?", (phone,)).fetchone()
            if row:
                # 已存在 → 合并更新（不重复建档）
                sets, vals = [], []
                for k, v in fields.items():
                    if v not in (None, ""):
                        sets.append(f"{k}=?")
                        vals.append(v)
                if sets:
                    conn.execute(f"UPDATE customers SET {','.join(sets)} WHERE id=?",
                                 vals + [row["id"]])
                audit(user, "线索合并", f"customers#{row['id']}", after="phone=" + phone)
                return {"id": row["id"], "deduped": True}
            cur = conn.execute(
                "INSERT INTO customers(phone, name, estate, layout, area, budget_range, "
                "style, intent_time, channel, tags, source) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (phone, fields.get("name"), fields.get("estate"), fields.get("layout"),
                 fields.get("area"), fields.get("budget_range"), fields.get("style"),
                 fields.get("intent_time"), fields.get("channel"), fields.get("tags"),
                 fields.get("source")))
            cid = cur.lastrowid
            audit(user, "线索录入", f"customers#{cid}", after="phone=" + phone)
            return {"id": cid, "deduped": False}

    # ---------- M2 建档打标（需求标签结构化） ----------
    def profile(self, user: str, customer_id: int, **fields) -> dict:
        tags = fields.pop("tags", None)
        if tags:
            # 标签规范化：支持逗号/顿号/分号分隔
            fields["tags"] = ",".join(t.strip() for t in re.split(r"[,，、;；]", tags) if t.strip())
        with get_conn() as conn:
            row = conn.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
            if not row:
                raise ValueError(f"客户 {customer_id} 不存在")
            sets, vals = [], []
            for k, v in fields.items():
                if v not in (None, ""):
                    sets.append(f"{k}=?")
                    vals.append(v)
            if sets:
                conn.execute(f"UPDATE customers SET {','.join(sets)} WHERE id=?",
                             vals + [customer_id])
            audit(user, "建档打标", f"customers#{customer_id}", after=";".join(fields))
            fresh = conn.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
            return dict(fresh)

    def transition(self, user: str, customer_id: int, to: str) -> dict:
        """状态迁移（校验 workflow.yaml 迁移规则）"""
        with get_conn() as conn:
            row = conn.execute("SELECT status FROM customers WHERE id=?", (customer_id,)).fetchone()
            if not row:
                raise ValueError(f"客户 {customer_id} 不存在")
            cur = row["status"]
            allowed = {t["to"] for t in self.cfg["workflow"]["transitions"] if t["from"] == cur}
            if to not in allowed and to != cur:
                raise ValueError(f"状态迁移不合法: {cur} -> {to}（允许: {allowed or '无'}）")
            conn.execute("UPDATE customers SET status=? WHERE id=?", (to, customer_id))
            audit(user, "状态迁移", f"customers#{customer_id}", before=cur, after=to)
            return {"id": customer_id, "from": cur, "to": to}

    # ---------- M3a 收件箱：AI 起草（人审后发） ----------
    def prepare_draft(self, user: str, customer_id: int, kind: str = "first_contact",
                      context: str = "") -> dict:
        """生成消息草稿（author=ai, approve_status=draft），等待人审批"""
        with get_conn() as conn:
            c = conn.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
            if not c:
                raise ValueError(f"客户 {customer_id} 不存在")
            cd = dict(c)
        sys_prompt = self.mm.build_system_prompt(self.cfg)
        l2 = self.mm.load_l2(customer_id, limit=5)
        history = "\n".join(f"[{m['author'] or m['direction']}] {m['content']}" for m in l2) or "（无历史）"
        if kind == "first_contact":
            task = "这是首次联系，写一条礼貌简短的破冰首联消息，介绍公司并询问需求。"
        elif kind == "followup":
            task = "写一条跟进消息，基于历史推进需求，约定下一步。"
        else:
            task = f"写一条消息。附加要求: {context}"
        llm = config_loader and None  # llm 由调用方注入或默认工厂
        from llm import get_llm
        content = get_llm().chat([
            {"role": "system", "content": sys_prompt + "\n纪律: AI 只起草，人审批后发。"},
            {"role": "user", "content":
                f"客户档案: {customer_summary(cd)}\n历史: {history}\n任务: {task}"},
        ])
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO messages(customer_id, direction, content, author, approve_status) "
                "VALUES(?,?,?,?,?)",
                (customer_id, "out", content, "ai", "draft"))
            mid = cur.lastrowid
        audit(user, "AI起草", f"messages#{mid}", after=kind)
        return {"id": mid, "customer_id": customer_id, "content": content,
                "approve_status": "draft"}

    def handle(self, ctx, message: str):
        return self.todo("M1/M2/M3a 已实现（ingest/profile/prepare_draft）")
