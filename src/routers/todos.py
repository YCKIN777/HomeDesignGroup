# -*- coding: utf-8 -*-
"""todos 路由：M7 SOP 待办（生成/列表/完成）"""
from fastapi import APIRouter
from pydantic import BaseModel

from agents.sop_agent import SopAgent
from db import get_conn

router = APIRouter(prefix="/api/todos", tags=["todos"])
sop_agent = SopAgent()


class TodoIn(BaseModel):
    user: str = "system"


@router.get("")
def list_todos(only_open: bool = True):
    sop_agent.check_due()   # 每次查看先刷新待办（含逾期检测）
    with get_conn() as conn:
        sql = ("SELECT t.*, c.name, c.phone FROM todos t LEFT JOIN customers c "
               "ON c.id=t.customer_id WHERE 1=1")
        if only_open:
            sql += " AND t.done=0"
        sql += " ORDER BY t.id DESC LIMIT 50"
        rows = conn.execute(sql).fetchall()
    return {"total": len(rows), "items": [dict(r) for r in rows]}


@router.post("/{tid}/done")
def done_todo(tid: int, body: TodoIn):
    with get_conn() as conn:
        conn.execute("UPDATE todos SET done=1 WHERE id=?", (tid,))
    from db import audit
    audit(body.user, "待办完成", f"todos#{tid}")
    return {"id": tid, "done": True}
