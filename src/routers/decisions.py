# -*- coding: utf-8 -*-
"""decisions 路由：Step 4.10 决策捕获查询/显式捕获/结果回填"""
from fastapi import APIRouter
from pydantic import BaseModel

from kernel import decisions as d
from kernel.roles import require as _perm

router = APIRouter(prefix="/api/decisions", tags=["decisions"])


class CaptureIn(BaseModel):
    user: str
    kind: str                     # score/invite/noshow/transition/approve/reject/dispatch
    customer_id: int
    context: dict = {}
    outcome: str = ""


@router.get("")
def list_decisions(kind: str = "", customer_id: int = 0, limit: int = 50):
    """决策记录查询（读开放）：复盘/审计/沉淀证据引用"""
    return {"total": None, "items": d.list_decisions(
        kind=kind, customer_id=customer_id or None, limit=limit)}


@router.post("")
def capture(body: CaptureIn):
    """显式捕获一次决策（供外部/复盘写入；业务钩子自动捕获的无需手工调用）"""
    _perm(body.user, "review")
    did = d.capture(body.kind, body.customer_id, body.user, body.context)
    if body.outcome:
        d.set_outcome(did, body.outcome)
    return {"id": did, "ok": True}


@router.post("/{did}/outcome")
def outcome(did: int, body: dict):
    """回填决策后续结果（邀约到店/未到店、成交/流失等）"""
    user = body.get("user", "system")
    _perm(user, "review")
    d.set_outcome(did, body.get("outcome", ""))
    return {"id": did, "outcome": body.get("outcome", "")}
