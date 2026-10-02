# -*- coding: utf-8 -*-
"""agent_api.py — 契约线 3 个 MVP Sub-agent 的 HTTP 出口（架构契约 Step 6 外层集成）"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.craft_qa_agent import CraftQaAgent
from agents.quote_agent import QuoteAgent
from agents.site_report_agent import SiteReportAgent

router = APIRouter(prefix="/api/agents", tags=["contract-agents"])


class CraftQAIn(BaseModel):
    question: str
    category: str = ""
    user: str = "客服"


class QuoteIn(BaseModel):
    owner_id: int
    requirements: str = ""
    category: str = ""
    user: str = "销售"


class SiteReportIn(BaseModel):
    project: str
    photo_desc: str = ""
    user: str = "监理"


@router.post("/craft-qa")
def craft_qa(b: CraftQAIn):
    try:
        return CraftQaAgent().answer(b.question, b.category, b.user)
    except Exception as e:
        raise HTTPException(500, f"工艺问答失败: {e}")


@router.post("/quote")
def quote(b: QuoteIn):
    try:
        return QuoteAgent(b.user).build_quote(b.owner_id, b.requirements, b.category)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"报价单失败: {e}")


@router.post("/site-report")
def site_report(b: SiteReportIn):
    try:
        rep = SiteReportAgent().build_report(b.project, b.photo_desc)
        return rep
    except Exception as e:
        raise HTTPException(500, f"工地日报失败: {e}")
