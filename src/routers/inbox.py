# -*- coding: utf-8 -*-
"""inbox 路由：M3a 收件箱（AI 起草 → 人审批 → 发送），全审计"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.lead_agent import LeadAgent
from db import get_conn, audit
from kernel import decisions as _dec
from kernel.roles import require as _perm

router = APIRouter(prefix="/api/inbox", tags=["inbox"])
lead_agent = LeadAgent()


class DraftIn(BaseModel):
    user: str
    customer_id: int
    kind: str = "first_contact"   # first_contact / followup / custom
    context: str = ""


class ReviewIn(BaseModel):
    user: str
    reason: str = ""


@router.post("/draft")
def draft(body: DraftIn):
    _perm(body.user, "draft")
    return lead_agent.prepare_draft(user=body.user, customer_id=body.customer_id,
                                    kind=body.kind, context=body.context)


@router.get("")
def inbox(only: str = "draft"):
    """收件箱：待审批草稿（默认）/ 已发送 / 已驳回"""
    with get_conn() as conn:
        if only == "all":
            rows = conn.execute(
                "SELECT m.*, c.name, c.phone FROM messages m LEFT JOIN customers c "
                "ON c.id=m.customer_id WHERE m.direction='out' AND m.author='ai' "
                "ORDER BY m.id DESC LIMIT 50").fetchall()
        else:
            rows = conn.execute(
                "SELECT m.*, c.name, c.phone FROM messages m LEFT JOIN customers c "
                "ON c.id=m.customer_id WHERE m.approve_status=? AND m.direction='out' "
                "ORDER BY m.id DESC LIMIT 50", (only,)).fetchall()
    return {"total": len(rows), "items": [dict(r) for r in rows]}


@router.post("/{mid}/approve")
def approve(mid: int, body: ReviewIn):
    _perm(body.user, "approve")
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
        if not row:
            raise HTTPException(404, f"消息 {mid} 不存在")
        if row["approve_status"] != "draft":
            raise HTTPException(409, f"消息 {mid} 状态为 {row['approve_status']}，不可审批")
        conn.execute("UPDATE messages SET approve_status='sent' WHERE id=?", (mid,))
    audit(body.user, "审批发送", f"messages#{mid}", before="draft", after="sent")
    _dec.capture("approve", row["customer_id"], body.user, {"mid": mid})
    return {"id": mid, "approve_status": "sent", "user": body.user}


@router.post("/{mid}/reject")
def reject(mid: int, body: ReviewIn):
    _perm(body.user, "approve")
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
        if not row:
            raise HTTPException(404, f"消息 {mid} 不存在")
        if row["approve_status"] != "draft":
            raise HTTPException(409, f"消息 {mid} 状态为 {row['approve_status']}，不可驳回")
        conn.execute("UPDATE messages SET approve_status='rejected' WHERE id=?", (mid,))
    audit(body.user, "驳回", f"messages#{mid}", before="draft",
          after=f"rejected:{body.reason}")
    _dec.capture("reject", row["customer_id"], body.user, {"mid": mid, "reason": body.reason})
    return {"id": mid, "approve_status": "rejected", "user": body.user, "reason": body.reason}
