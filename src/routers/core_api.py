# -*- coding: utf-8 -*-
"""core_api.py — 契约 Step 3：三张核心表的读写 API（原则 2：通过 API 读写）

端点（统一前缀 /api/core）：
  POST   /api/core/owners            新建业主档案
  GET    /api/core/owners?q=&style=  查业主
  PUT    /api/core/owners/{id}       更新（预算/户型字段修改由 Sentinel 二次确认，见 Step 4）
  POST   /api/core/craft             新增工艺知识（可选同步 embedding_id）
  GET    /api/core/craft?category=&q= 查工艺知识
  POST   /api/core/materials         新增建材条目
  GET    /api/core/materials?category=&tags=&q=  查建材
"""
import json

from fastapi import APIRouter
from pydantic import BaseModel

from db import audit
from kernel.roles import require as _perm
from models.core import connect

router = APIRouter(prefix="/api/core", tags=["core"])


class OwnerIn(BaseModel):
    user: str = "admin"
    wechat_id: str
    nickname: str = ""
    community: str = ""
    house_area: float = 0.0
    layout_json: str = "{}"
    budget_total: float = 0.0
    budget_used: float = 0.0
    style_preference: str = ""


class CraftIn(BaseModel):
    user: str = "admin"
    category: str
    title: str
    content: str
    source_file: str = ""
    embedding_id: str = ""


class MaterialIn(BaseModel):
    user: str = "admin"
    category: str
    name: str
    spec: str = ""
    supplier: str = ""
    price: float = 0.0
    moq: float = 0.0
    tags: str = ""


def _row_to_dict(r):
    return {k: r[k] for k in r.keys()}


# ---------- owners ----------
@router.post("/owners")
def create_owner(body: OwnerIn):
    _perm(body.user, "lead.write")
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO owners (wechat_id,nickname,community,house_area,layout_json,"
            "budget_total,budget_used,style_preference) VALUES (?,?,?,?,?,?,?,?)",
            (body.wechat_id, body.nickname, body.community, body.house_area,
             body.layout_json, body.budget_total, body.budget_used, body.style_preference))
        oid = cur.lastrowid
    audit(body.user, "新建业主档案", f"owners#{oid}")
    return {"id": oid, "ok": True}


@router.get("/owners")
def list_owners(q: str = "", style: str = "", limit: int = 20):
    sql = "SELECT * FROM owners WHERE 1=1"
    params = []
    if q:
        sql += " AND (nickname LIKE ? OR community LIKE ?)"
        params += [f"%{q}%"] * 2
    if style:
        sql += " AND style_preference LIKE ?"
        params.append(f"%{style}%")
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {"total": len(rows), "items": [_row_to_dict(r) for r in rows]}


@router.get("/owners/{oid}")
def get_owner(oid: int):
    with connect() as conn:
        r = conn.execute("SELECT * FROM owners WHERE id=?", (oid,)).fetchone()
    if not r:
        return {"error": f"业主 {oid} 不存在"}
    return _row_to_dict(r)


# ---------- craft_knowledge ----------
@router.post("/craft")
def create_craft(body: CraftIn):
    _perm(body.user, "lead.write")
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO craft_knowledge (category,title,content,source_file,embedding_id) "
            "VALUES (?,?,?,?,?)",
            (body.category, body.title, body.content, body.source_file, body.embedding_id))
        cid = cur.lastrowid
    audit(body.user, "新增工艺知识", f"craft_knowledge#{cid}")
    return {"id": cid, "ok": True}


@router.get("/craft")
def list_craft(category: str = "", q: str = "", limit: int = 20):
    sql = "SELECT * FROM craft_knowledge WHERE 1=1"
    params = []
    if category:
        sql += " AND category=?"
        params.append(category)
    if q:
        sql += " AND (title LIKE ? OR content LIKE ?)"
        params += [f"%{q}%"] * 2
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {"total": len(rows), "items": [_row_to_dict(r) for r in rows]}


# ---------- materials ----------
@router.post("/materials")
def create_material(body: MaterialIn):
    _perm(body.user, "lead.write")
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO materials (category,name,spec,supplier,price,moq,tags) "
            "VALUES (?,?,?,?,?,?,?)",
            (body.category, body.name, body.spec, body.supplier,
             body.price, body.moq, body.tags))
        mid = cur.lastrowid
    audit(body.user, "新增建材条目", f"materials#{mid}")
    return {"id": mid, "ok": True}


@router.get("/materials")
def list_materials(category: str = "", q: str = "", limit: int = 20):
    sql = "SELECT * FROM materials WHERE 1=1"
    params = []
    if category:
        sql += " AND category=?"
        params.append(category)
    if q:
        sql += " AND (name LIKE ? OR spec LIKE ? OR tags LIKE ?)"
        params += [f"%{q}%"] * 3
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {"total": len(rows), "items": [_row_to_dict(r) for r in rows]}
