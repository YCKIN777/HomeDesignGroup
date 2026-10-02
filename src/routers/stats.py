# -*- coding: utf-8 -*-
"""stats 路由：阶段4 业务指标对账
24h首联率 / 响应时长中位数 / 派单及时率 / 线索转化
口径：首联=该客户第一条 approve_status='sent' 的外呼消息
"""
from datetime import datetime

from fastapi import APIRouter

from db import get_conn

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _hours_until_sent(cid: int, conn) -> float:
    """客户创建到首条已发送消息的间隔（小时）；无发送返回 None"""
    row = conn.execute(
        "SELECT (julianday(m.created_at) - julianday(c.created_at)) * 24 AS h "
        "FROM messages m JOIN customers c ON c.id=m.customer_id "
        "WHERE m.customer_id=? AND m.direction='out' AND m.approve_status='sent' "
        "ORDER BY m.id LIMIT 1", (cid,)).fetchone()
    return row["h"] if row else None


@router.get("")
def stats():
    with get_conn() as conn:
        leads = conn.execute(
            "SELECT id, created_at, julianday('now','localtime') - julianday(created_at) AS age_days "
            "FROM customers").fetchall()
        total = len(leads)
        contacted = [l for l in leads if _hours_until_sent(l["id"], conn) is not None]
        within24 = [l for l in contacted if _hours_until_sent(l["id"], conn) <= 24]

        # 响应时长中位数（首条已发送消息的等待小时）
        hours = sorted(_hours_until_sent(l["id"], conn) for l in contacted)
        n = len(hours)
        median = (hours[n // 2] + hours[(n - 1) // 2]) / 2 if n else None

        dispatched = conn.execute(
            "SELECT id, created_at, dispatched_at FROM projects").fetchall()
        disp_ok = [p for p in dispatched
                   if p["dispatched_at"]
                   and (datetime.strptime(p["dispatched_at"], "%Y-%m-%d %H:%M:%S")
                        - datetime.strptime(p["created_at"], "%Y-%m-%d %H:%M:%S")).days <= 3]
        return {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "线索总数": total,
            "24h首联率": round(len(within24) / total * 100, 1) if total else 0.0,
            "首联客户数": len(contacted),
            "响应时长中位数(小时)": round(median, 1) if median is not None else None,
            "派单数": len(dispatched),
            "派单及时率(3日内)": round(len(disp_ok) / len(dispatched) * 100, 1) if dispatched else 0.0,
            "线索转化率(派单/线索)": round(len(dispatched) / total * 100, 1) if total else 0.0,
        }
