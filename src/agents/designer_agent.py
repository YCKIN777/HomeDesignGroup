# -*- coding: utf-8 -*-
"""designer_agent.py — 设计师 Agent（编队计划 v3 · P2 归并收敛）

组合：dispatch(派单建项目) + kb(谈单知识库) + 方案沉淀(design_plans 版本递增)
职责：接客服派单→建项目→量房设计方案→谈单知识库问答。
对外闸门：方案定稿人工确认（对外动作走 Sentinel）。
行为不变：派单与知识库委托原 Agent；方案沉淀逻辑由 main.py 迁入。
"""
from db import get_conn, audit
from agents.dispatch_agent import DispatchAgent
from agents.kb_agent import KbAgent
from agents.base import BaseAgent

PLAN_FLOW = {"初稿": ["评审中", "已否决"], "评审中": ["已定稿", "已否决", "初稿"],
             "已定稿": [], "已否决": []}


class DesignerAgent(BaseAgent):
    name = "designer"
    role = "设计师（派单承接+方案+谈单）"
    capabilities = [
        "客服派单承接，建项目（状态机量房起步）",
        "量房设计方案沉淀（版本递增/状态流转）",
        "谈单知识库检索（设计/报价/工艺/案例）",
    ]

    def __init__(self):
        self.dispatch_agent = DispatchAgent()
        self.kb = KbAgent()

    # ---------- M4 派单承接 ----------
    def dispatch(self, user: str, customer_id: int, designer: str = None) -> dict:
        return self.dispatch_agent.dispatch(user, customer_id, designer)

    # ---------- M9 谈单知识库 ----------
    def search(self, query: str, top_k: int = 5) -> list:
        return self.kb.search(query, top_k)

    # ---------- 方案沉淀（版本递增） ----------
    def add_plan(self, user: str, project_id: int, style: str, points: str = "") -> dict:
        """沉淀设计方案：项目下版本递增，初始状态=初稿"""
        with get_conn() as conn:
            if not conn.execute("SELECT id FROM projects WHERE id=?", (project_id,)).fetchone():
                raise ValueError(f"项目 {project_id} 不存在")
            v = conn.execute("SELECT COALESCE(MAX(version),0)+1 AS v FROM design_plans "
                             "WHERE project_id=?", (project_id,)).fetchone()["v"]
            cur = conn.execute(
                "INSERT INTO design_plans(project_id,version,style,points,status,created_by) "
                "VALUES(?,?,?,?,'初稿',?)", (project_id, v, style, points, user))
            plid = cur.lastrowid
            audit(user, "设计方案", f"design_plans#{plid}", after=f"project={project_id} v{v} {style}")
        return {"id": plid, "project_id": project_id, "version": v,
                "style": style, "points": points, "status": "初稿"}

    def list_plans(self, project_id: int) -> list:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT id,version,style,points,status,created_by FROM design_plans "
                "WHERE project_id=? ORDER BY version DESC", (project_id,)).fetchall()
        return [dict(r) for r in rows]

    def status_plan(self, user: str, plan_id: int, to: str) -> dict:
        """方案状态流转。P2 收敛保持行为不变：沿用原 main.py 直接写状态；
        PLAN_FLOW 常量保留，供后续闸门（方案定稿人工确认）启用。"""
        with get_conn() as conn:
            row = conn.execute("SELECT status FROM design_plans WHERE id=?", (plan_id,)).fetchone()
            if not row:
                raise ValueError(f"方案 {plan_id} 不存在")
            cur = row["status"]
            conn.execute("UPDATE design_plans SET status=? WHERE id=?", (to, plan_id))
            audit(user, "方案状态", f"design_plans#{plan_id}", before=cur, after=to)
        return {"id": plan_id, "from": cur, "to": to}

    def handle(self, ctx, message: str):
        return self.todo("设计师 Agent：dispatch/search/add_plan/list_plans/status_plan")
