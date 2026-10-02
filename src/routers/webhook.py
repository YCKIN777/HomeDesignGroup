# -*- coding: utf-8 -*-
"""webhook 路由：M3b 渠道直连（通用收口 → 转线索入库）
企微/微信等具体渠道适配 = 一个把渠道消息翻译成本 payload 的转发器，后续接真实账号。
"""
from fastapi import APIRouter
from pydantic import BaseModel

from agents.lead_agent import LeadAgent

router = APIRouter(prefix="/api/webhook", tags=["webhook"])


class ChannelMsg(BaseModel):
    channel: str = "web"          # 渠道标识: web/wecom/wechat/...
    phone: str                    # 客户手机号（线索主键）
    name: str = None
    estate: str = None
    layout: str = None
    budget_range: str = None
    style: str = None
    intent_time: str = None
    message: str = None           # 客户原话 → 存入 followups
    source: str = "webhook"


@router.post("/{channel}")
def channel_in(channel: str, body: ChannelMsg):
    if body.channel != channel:
        body.channel = channel
    lead = LeadAgent().ingest(user=f"渠道:{channel}", phone=body.phone,
                              name=body.name, estate=body.estate, layout=body.layout,
                              budget_range=body.budget_range, style=body.style,
                              intent_time=body.intent_time, channel=channel,
                              source=body.source or channel)
    if body.message:
        from db import get_conn
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO followups(customer_id, channel, content) VALUES(?,?,?)",
                (lead["id"], channel, body.message))
    return {"ok": True, "lead": lead, "message_recorded": bool(body.message)}
