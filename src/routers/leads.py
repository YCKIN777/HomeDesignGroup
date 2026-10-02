# -*- coding: utf-8 -*-
"""leads 路由：M1 归集 / M2 建档打标 / M6 评分 / M8 邀约"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.lead_agent import LeadAgent
from agents.scoring_agent import ScoringAgent
from agents.invite_agent import InviteAgent
from db import get_conn
from kernel import decisions as _dec
from kernel.roles import require as _perm
from memory_manager import MemoryManager

router = APIRouter(prefix="/api", tags=["leads"])
lead_agent = LeadAgent()
mm = MemoryManager("壹城精工")


class LeadIn(BaseModel):
    phone: str
    name: Optional[str] = None
    estate: Optional[str] = None
    layout: Optional[str] = None
    area: Optional[float] = None
    budget_range: Optional[str] = None
    style: Optional[str] = None
    intent_time: Optional[str] = None
    channel: Optional[str] = None
    tags: Optional[str] = None
    source: Optional[str] = None
    user: str = "system"


class ProfileIn(BaseModel):
    user: str = "system"
    name: Optional[str] = None
    estate: Optional[str] = None
    layout: Optional[str] = None
    area: Optional[float] = None
    budget_range: Optional[str] = None
    style: Optional[str] = None
    intent_time: Optional[str] = None
    channel: Optional[str] = None
    tags: Optional[str] = None


class StatusIn(BaseModel):
    user: str
    to: str


class ImportIn(BaseModel):
    user: str = "system"
    rows: list  # 每行: phone/name/estate/layout/area/budget_range/style/intent_time/channel/tags/source


class CsvImportIn(BaseModel):
    user: str = "system"
    csv_text: str  # CSV 文本（表头与 input/线索导入模板.csv 一致）


def _import_rows(user: str, rows: list) -> dict:
    """批量导入核心：按手机号去重合并，返回统计+逐行结果"""
    results = []
    created = merged = error = 0
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            results.append({"row": i, "status": "error", "reason": "行格式须为对象"})
            error += 1
            continue
        phone = str(row.get("phone") or "").strip()
        if not phone:
            results.append({"row": i, "phone": "", "status": "skipped", "reason": "缺手机号"})
            error += 1
            continue
        try:
            r = _guard(lead_agent.ingest, user=user, phone=phone,
                       name=row.get("name"), estate=row.get("estate"),
                       layout=row.get("layout"), area=row.get("area"),
                       budget_range=row.get("budget_range"), style=row.get("style"),
                       intent_time=row.get("intent_time"), channel=row.get("channel"),
                       tags=row.get("tags"), source=row.get("source"))
            status = "merged" if r.get("deduped") else "created"
            if r.get("deduped"):
                merged += 1
            else:
                created += 1
            results.append({"row": i, "phone": phone, "status": status, "id": r["id"]})
        except HTTPException as e:
            error += 1
            results.append({"row": i, "phone": phone, "status": "error", "reason": e.detail})
    return {"total": len(rows), "created": created, "merged": merged,
            "error": error, "results": results}


# ---------- M1 批量导入（JSON 行 / CSV 文本，补齐计划 2.1）----------
@router.post("/leads/import")
def import_leads(body: ImportIn):
    _perm(body.user, "lead.write")
    return _import_rows(body.user, body.rows)


@router.post("/leads/import/csv")
def import_leads_csv(body: CsvImportIn):
    _perm(body.user, "lead.write")
    import csv
    import io

    def _cell(v):
        """CSV 单元格防御：None→空串，多出字段的 list→拼回字符串"""
        if isinstance(v, list):
            v = ",".join(x for x in v if x != "")
        return str(v).strip() if v is not None else ""

    text = (body.csv_text or "").lstrip("\ufeff")   # 兼容 Excel 另存的 UTF-8 BOM
    rows = []
    try:
        for rec in csv.DictReader(io.StringIO(text)):
            safe = {k: _cell(v) for k, v in rec.items() if k}
            if not any(safe.values()):
                continue                       # 跳过空行
            rows.append(safe)
    except Exception as e:
        raise HTTPException(400, f"CSV 解析失败: {e}")
    return _import_rows(body.user, rows)


def _guard(fn, *a, **kw):
    """业务 ValueError → HTTP 400"""
    try:
        return fn(*a, **kw)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---------- M1 归集 ----------
@router.post("/leads")
def create_lead(body: LeadIn):
    _perm(body.user, "lead.write")
    return _guard(lead_agent.ingest, user=body.user, phone=body.phone,
                  name=body.name, estate=body.estate, layout=body.layout,
                  area=body.area, budget_range=body.budget_range,
                  style=body.style, intent_time=body.intent_time,
                  channel=body.channel, tags=body.tags, source=body.source)


@router.get("/leads")
def list_leads(status: str = "", q: str = "", limit: int = 50):
    with get_conn() as conn:
        sql = "SELECT * FROM customers WHERE 1=1"
        args = []
        if status:
            sql += " AND status=?"
            args.append(status)
        if q:
            sql += " AND (name LIKE ? OR estate LIKE ? OR phone LIKE ? OR tags LIKE ?)"
            args += [f"%{q}%"] * 4
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        rows = conn.execute(sql, args).fetchall()
    return {"total": len(rows), "items": [dict(r) for r in rows]}


@router.get("/leads/{cid}")
def get_lead(cid: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone()
        if not row:
            return {"error": f"客户 {cid} 不存在"}
        lead = dict(row)
    lead["l2"] = mm.load_l2(cid)          # Otter: 打开客户自动载 L2
    return lead


# ---------- M2 建档打标 ----------
@router.put("/leads/{cid}")
def profile_lead(cid: int, body: ProfileIn):
    _perm(body.user, "lead.write")
    return _guard(lead_agent.profile, user=body.user, customer_id=cid,
                  name=body.name, estate=body.estate, layout=body.layout,
                  area=body.area, budget_range=body.budget_range,
                  style=body.style, intent_time=body.intent_time,
                  channel=body.channel, tags=body.tags)


@router.post("/leads/{cid}/status")
def transition_lead(cid: int, body: StatusIn):
    _perm(body.user, "transition")
    r = _guard(lead_agent.transition, user=body.user, customer_id=cid, to=body.to)
    _dec.capture_result(r, "transition", cid, body.user)
    return r


# ---------- M6 评分 ----------
@router.post("/leads/{cid}/score")
def score_lead(cid: int, body: dict):
    user = body.get("user", "system")
    _perm(user, "score")
    r = _guard(ScoringAgent().score, user=user, customer_id=cid)
    _dec.capture_result(r, "score", cid, user)
    return r


# ---------- M8 邀约 ----------
@router.post("/leads/{cid}/invite")
def invite_lead(cid: int, body: dict):
    user = body.get("user", "system")
    _perm(user, "invite")
    r = _guard(InviteAgent().create_invite, user=user, customer_id=cid,
               when=body.get("when", ""), where=body.get("where", "公司展厅"))
    _dec.capture_result(r, "invite", cid, user)
    return r


@router.post("/leads/{cid}/noshow")
def noshow_lead(cid: int, body: dict):
    user = body.get("user", "system")
    _perm(user, "invite")
    r = _guard(InviteAgent().noshow, user=user, customer_id=cid)
    _dec.capture_result(r, "noshow", cid, user)
    return r
