# -*- coding: utf-8 -*-
"""kb 路由：M9 谈单知识库检索"""
from fastapi import APIRouter

from agents.kb_agent import KbAgent

router = APIRouter(prefix="/api/kb", tags=["kb"])
kb_agent = KbAgent()


@router.get("/search")
def search(q: str, top_k: int = 5):
    return {"query": q, "hits": kb_agent.search(q, top_k=top_k)}
