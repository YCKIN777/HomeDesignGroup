# -*- coding: utf-8 -*-
"""team_api 路由：编队 v3 九部门视图 P8 · 总经办/材料/软装/售后 四部门 Web API

与 CLI 中控（main.py /ceo /mat /soft /as）同一套 Agent 内核；
Web/API 通道强制角色权限（roles.py 动作矩阵），CLI 演示通道由 Web/API 兜底强制。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.executive_office_agent import ExecutiveOfficeAgent
from agents.material_agent import MaterialAgent
from agents.soft_furnishing_agent import SoftFurnishingAgent
from agents.after_sales_agent import AfterSalesAgent
from kernel.roles import require as _perm
from kernel.roles import ROLE_ACTIONS

router = APIRouter(prefix="/api/team", tags=["team"])

ceo = ExecutiveOfficeAgent()
material = MaterialAgent()
soft = SoftFurnishingAgent()
aftersales = AfterSalesAgent()


# ---------- 组织（派单设计师下拉动态化 P11） ----------
@router.get("/designers")
def designers_list():
    """设计类角色用户（含 design_plan 动作的角色组），供派单下拉动态加载。"""
    import sqlite3
    from kernel import roles as _roles
    design_roles = [r for r, acts in _roles.ROLE_ACTIONS.items() if "design_plan" in acts]
    conn = sqlite3.connect(_roles.DB_PATH)
    rows = conn.execute(
        "SELECT account, role FROM users WHERE role IN (%s) ORDER BY id"
        % ",".join("?" * len(design_roles)), design_roles).fetchall()
    conn.close()
    return {"rows": [{"account": r[0], "role": r[1]} for r in rows]}


# ---------- 总经办 ----------
class CoordIn(BaseModel):
    user: str
    note: str


@router.get("/ceo/approvals")
def ceo_approvals(user: str = "admin"):
    _perm(user, "audit")
    return ceo.approval_inbox(user)


@router.get("/ceo/dashboard")
def ceo_dashboard(user: str = "admin"):
    _perm(user, "audit")
    return ceo.dashboard(user)


@router.get("/ceo/audit")
def ceo_audit(user: str = "admin", limit: int = 10):
    _perm(user, "audit")
    return {"rows": ceo.audit_trail(user, limit)}


@router.post("/ceo/coord")
def ceo_coord(body: CoordIn):
    _perm(body.user, "audit")
    return ceo.coordinate(body.user, body.note)


# ---------- 材料 ----------
@router.get("/materials")
def materials_list(user: str = "admin", category: str = "", keyword: str = "", limit: int = 30):
    return {"rows": material.list_materials(category=category, keyword=keyword, limit=limit)}


@router.get("/quotes/{qid}/materials")
def materials_of_quote(qid: int, user: str = "admin"):
    try:
        return material.build_material_list(qid)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---------- 软装 ----------
class SoftIn(BaseModel):
    user: str
    project_id: int
    category: str
    name: str
    spec: str = ""
    qty: float = 1
    unit_price: float = 0
    note: str = ""


class SoftUpIn(BaseModel):
    user: str
    category: str = None
    name: str = None
    spec: str = None
    qty: float = None
    unit_price: float = None
    status: str = None
    note: str = None


@router.get("/soft")
def soft_list(project_id: int, user: str = "admin"):
    return soft.build_soft_list(project_id)


@router.post("/soft")
def soft_add(body: SoftIn):
    _perm(body.user, "soft.write")
    try:
        return soft.add_item(body.user, body.project_id, body.category, body.name,
                             spec=body.spec, qty=body.qty, unit_price=body.unit_price,
                             note=body.note)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/soft/{item_id}")
def soft_update(item_id: int, body: SoftUpIn):
    _perm(body.user, "soft.write")
    fields = {k: v for k, v in body.dict().items()
              if k != "user" and v is not None}
    try:
        return soft.update_item(body.user, item_id, **fields)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/soft/{item_id}")
def soft_remove(item_id: int, user: str = "admin"):
    _perm(user, "soft.write")
    try:
        return soft.remove_item(user, item_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---------- 售后 ----------
class WarrantyIn(BaseModel):
    user: str
    project_id: int
    completed_at: str = ""


class TicketIn(BaseModel):
    user: str
    project_id: int
    title: str
    content: str = ""


class TicketStatusIn(BaseModel):
    user: str
    status: str   # 待处理/处理中/已关闭
    result: str = ""


@router.post("/aftersales/warranty")
def as_warranty(body: WarrantyIn):
    _perm(body.user, "aftersales.write")
    try:
        return aftersales.register_warranty(body.user, body.project_id, body.completed_at)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/aftersales/ticket")
def as_ticket(body: TicketIn):
    _perm(body.user, "aftersales.write")
    try:
        return aftersales.create_ticket(body.user, body.project_id, body.title, body.content)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/aftersales")
def as_list(project_id: int = None, user: str = "admin"):
    return {"rows": aftersales.list(project_id=project_id)}


@router.put("/aftersales/{ticket_id}/status")
def as_status(ticket_id: int, body: TicketStatusIn):
    _perm(body.user, "aftersales.write")
    try:
        return aftersales.update_status(body.user, ticket_id, body.status, body.result)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/aftersales/due")
def as_due(user: str = "admin"):
    return {"created": aftersales.check_due()}
