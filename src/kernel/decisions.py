# -*- coding: utf-8 -*-
"""
decisions.py — 决策捕获（Step 4.10，对齐 Palantir"决策→行动→结果→学习"闭环）
把关键业务动作（评分/邀约/爽约/迁移/审批/驳回/派单）的"输入+结果"结构化落库，
形成可复盘、可匿名、可喂给沉淀中心证据的决策记录（decision exhaust）。
  capture(kind, customer_id, user, context)   → 捕获一次决策
  list_decisions(kind, customer_id)            → 查询决策记录
  set_outcome(did, outcome)                    → 回填后续结果（邀约到店/未到店、成交/流失）
"""
import json

from db import get_conn


def capture(kind: str, customer_id: int, user: str, context: dict) -> int:
    """落一条决策记录，返回 id。context 仅存可匿名内容（不含手机号等隐私）。"""
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO decisions(kind, customer_id, user, context) VALUES(?,?,?,?)",
            (kind, customer_id, user, json.dumps(context, ensure_ascii=False)))
        return cur.lastrowid


def capture_result(r, kind: str, customer_id: int, user: str) -> int:
    """从业务结果 dict 自动提取可匿名 context 落库（排除 id/phone/正文等隐私冗余字段）。
    业务钩子统一入口：每个关键动作返回后调用一次。"""
    ctx = {}
    if isinstance(r, dict):
        for k, v in r.items():
            if k in ("id", "customer_id", "content", "summary", "phone", "name"):
                continue
            if isinstance(v, (str, int, float, bool)) or v is None:
                ctx[k] = v
    return capture(kind, customer_id, user, ctx)


def list_decisions(kind: str = "", customer_id: int = None, limit: int = 50) -> list:
    with get_conn() as conn:
        sql = "SELECT * FROM decisions WHERE 1=1"
        args = []
        if kind:
            sql += " AND kind=?"
            args.append(kind)
        if customer_id:
            sql += " AND customer_id=?"
            args.append(customer_id)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        rows = conn.execute(sql, args).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["context"] = json.loads(d.get("context") or "{}")
        except ValueError:
            d["context"] = {}
        out.append(d)
    return out


def set_outcome(did: int, outcome: str):
    with get_conn() as conn:
        conn.execute("UPDATE decisions SET outcome=? WHERE id=?", (outcome, did))


def anonymous(cid: int) -> int:
    """决策证据匿名化：返回不落盘的客户代号（供沉淀 evidence 引用，不泄露手机号）"""
    return cid
