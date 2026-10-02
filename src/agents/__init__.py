# -*- coding: utf-8 -*-
"""
agents/__init__.py — 六 Agent 骨架注册中心（Step 1.4）
load_agents() 返回 {name: instance}，中控 main.py 装载全部 Agent。
每个 Agent = 一组能力问题（对齐本体：每 Agent 处理的能力集合）。
"""
from .lead_agent import LeadAgent
from .dispatch_agent import DispatchAgent
from .scoring_agent import ScoringAgent
from .sop_agent import SopAgent
from .invite_agent import InviteAgent
from .kb_agent import KbAgent

_AGENT_CLASSES = [LeadAgent, DispatchAgent, ScoringAgent, SopAgent, InviteAgent, KbAgent]


def load_agents() -> dict:
    """实例化并注册全部 Agent，返回 {name: instance}"""
    agents = {}
    for cls in _AGENT_CLASSES:
        inst = cls()
        agents[inst.name] = inst
    return agents
