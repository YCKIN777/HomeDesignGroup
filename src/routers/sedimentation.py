# -*- coding: utf-8 -*-
"""sedimentation 路由：阶段4 沉淀中心（提炼准入 4 条 + 状态机 + 入内核物化）"""
import os

from fastapi import APIRouter
from pydantic import BaseModel

from db import get_conn, audit
from kernel.roles import require as _perm

ROOT = r"H:\AgentProjects\HomeDesignGroup"
SED_DIR = os.path.join(ROOT, "sedimentation")

router = APIRouter(prefix="/api/sedimentation", tags=["sedimentation"])


class SedimentIn(BaseModel):
    user: str
    category: str = "最佳实践"   # 规则/话术/术语/最佳实践
    title: str
    description: str
    condition: str = ""
    evidence: str = ""           # 验证证据（匿名）
    has_instance: bool = True    # 准入1: 有真实实例支撑
    reproducible: bool = True    # 准入2: 可复现（≥2家或权威证据）
    anonymized: bool = True      # 准入3: 不泄露公司
    respects_core: bool = True   # 准入4: 不违背内核强约束


@router.post("")
def submit(body: SedimentIn):
    _perm(body.user, "sediment")
    checks = {
        "有真实实例支撑": body.has_instance,
        "可复现(≥2家或权威)": body.reproducible,
        "匿名化不泄露公司": body.anonymized,
        "不违背内核强约束": body.respects_core,
    }
    if not all(checks.values()):
        return {"ok": False, "error": "未通过提炼准入4条", "checks": checks}
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO sedimentation_items(category, title, description, condition, "
            "evidence, status) VALUES(?,?,?,?,?,?)",
            (body.category, body.title, body.description, body.condition,
             body.evidence, "候选"))
        sid = cur.lastrowid
    audit(body.user, "沉淀提交", f"sedimentation_items#{sid}", after=body.category)
    return {"ok": True, "id": sid, "status": "候选", "checks": checks}


@router.get("")
def list_items(status: str = "", limit: int = 50):
    with get_conn() as conn:
        sql = "SELECT * FROM sedimentation_items WHERE 1=1"
        args = []
        if status:
            sql += " AND status=?"
            args.append(status)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        rows = conn.execute(sql, args).fetchall()
    return {"total": len(rows), "items": [dict(r) for r in rows]}


def _materialize(conn, row, user: str):
    """评审入内核 → 物化提炼物 md 到 sedimentation/ + 追加 CHANGELOG（Step 4.12）"""
    from datetime import datetime
    d = dict(row)
    fname = f"{datetime.now().strftime('%Y-%m-%d')}-{d['id']:03d}-{d['title'][:12]}.md"
    path = os.path.join(SED_DIR, fname)
    text = (f"---\ncategory: {d['category']}\ntitle: {d['title']}\n"
            f"time: \"{datetime.now().strftime('%Y-%m-%d')}\"\nsource: 沉淀评审\n"
            f"reviewer: {user}\nstatus: 已入内核\n---\n\n"
            f"# {d['title']}\n\n"
            f"适用条件：{d.get('condition') or '（通用）'}\n\n"
            f"描述：{d['description']}\n\n"
            f"证据：{d.get('evidence') or '（匿名）'}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    rel = os.path.relpath(path, ROOT)
    cl = os.path.join(ROOT, "CHANGELOG.md")
    line = (f"- {datetime.now().strftime('%Y-%m-%d')} 沉淀入内核 #{d['id']} "
            f"[{d['category']}] {d['title']}（物化 {rel}）")
    with open(cl, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return rel


@router.post("/{sid}/review")
def review(sid: int, body: dict):
    """评审：候选 → 已入内核 / 已剔除（入内核自动物化 md + 记 CHANGELOG）"""
    to = body.get("to")
    if to not in ("已入内核", "已剔除"):
        return {"error": "to 只能为 已入内核 / 已剔除"}
    user = body.get("user", "system")
    _perm(user, "review")
    materialized = None
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM sedimentation_items WHERE id=?", (sid,)).fetchone()
        if not row:
            return {"error": f"沉淀 {sid} 不存在"}
        conn.execute("UPDATE sedimentation_items SET status=? WHERE id=?", (to, sid))
        if to == "已入内核":
            materialized = _materialize(conn, row, user)
    audit(user, "沉淀评审", f"sedimentation_items#{sid}", after=to)
    return {"id": sid, "status": to, "materialized": materialized}
