# -*- coding: utf-8 -*-
"""engineer_agent.py — 工程 Agent（编队计划 v3 · P2 归并收敛）

组合：site_report(工地日报/OCR) + craft_qa(工艺问答) + 五节点验收
职责：施工过程——工地日报 + 五节点验收(水电/防水/泥木/油漆/竣工) + 工艺问答。
对外闸门：日报/验收结果对外走 Sentinel external_send（人工点发送）。
行为不变：site_report/craft_qa 委托原 Agent；验收与日报落库逻辑由 main.py 迁入。
"""
from datetime import datetime

from db import get_conn, audit
from agents.site_report_agent import SiteReportAgent
from agents.craft_qa_agent import CraftQaAgent
from agents.base import BaseAgent

INSPECT_NODES = ["水电", "防水", "泥木", "油漆", "竣工"]


class EngineerAgent(BaseAgent):
    name = "engineer"
    role = "工程（施工日报+验收+工艺）"
    capabilities = [
        "工地日报记录（项目经理上报，对外人审）",
        "五节点验收（水电/防水/泥木/油漆/竣工）",
        "工艺问答与建材参考价（craft_knowledge/materials）",
        "现场照片 OCR 识别进度（MultimodalProvider）",
    ]

    def __init__(self):
        self.site = SiteReportAgent()
        self.qa = CraftQaAgent()

    # ---------- 工地日报 ----------
    def add_report(self, user: str, project_id: int, stage: str, content: str) -> dict:
        with get_conn() as conn:
            if not conn.execute("SELECT id FROM projects WHERE id=?", (project_id,)).fetchone():
                raise ValueError(f"项目 {project_id} 不存在")
            cur = conn.execute(
                "INSERT INTO site_reports(project_id,stage,content,reporter) "
                "VALUES(?,?,?,?)", (project_id, stage, content, user))
            rid = cur.lastrowid
            audit(user, "工地日报", f"site_reports#{rid}", after=f"stage={stage}")
        return {"id": rid, "project_id": project_id, "stage": stage, "content": content}

    def list_reports(self, project_id: int) -> list:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT id,stage,content,reporter,created_at FROM site_reports "
                "WHERE project_id=? ORDER BY id DESC LIMIT 50", (project_id,)).fetchall()
        return [dict(r) for r in rows]

    # ---------- 五节点验收 ----------
    def inspect(self, user: str, project_id: int, node: str, result: str,
                note: str = "") -> dict:
        if node not in INSPECT_NODES:
            raise ValueError(f"验收节点须为 {'/'.join(INSPECT_NODES)}（收到 {node}）")
        if result not in ("合格", "整改"):
            raise ValueError("result 须为 合格/整改")
        with get_conn() as conn:
            if not conn.execute("SELECT id FROM projects WHERE id=?", (project_id,)).fetchone():
                raise ValueError(f"项目 {project_id} 不存在")
            old = conn.execute("SELECT result FROM inspections WHERE project_id=? AND node=?",
                               (project_id, node)).fetchone()
            conn.execute(
                "INSERT INTO inspections(project_id,node,result,checked_by,checked_at,note) "
                "VALUES(?,?,?,?,datetime('now','localtime'),?) "
                "ON CONFLICT(project_id,node) DO UPDATE SET result=excluded.result, "
                "checked_by=excluded.checked_by, checked_at=excluded.checked_at, note=excluded.note",
                (project_id, node, result, user, note))
            audit(user, "节点验收", f"inspections#{project_id}:{node}",
                  before=old["result"] if old else "待验收", after=result)
        return {"project_id": project_id, "node": node, "result": result, "note": note}

    def list_inspections(self, project_id: int) -> list:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT node,result,checked_by,checked_at,note FROM inspections "
                "WHERE project_id=?", (project_id,)).fetchall()
        return [dict(r) for r in rows]

    # ---------- 工艺问答（契约线能力保留） ----------
    def craft_answer(self, question: str, category: str = "", user: str = "客服") -> dict:
        return self.qa.answer(question, category, user)

    # ---------- 工地日报草稿（OCR+LLM，对外人审） ----------
    def build_report_draft(self, project: str, photo_desc: str = "",
                           image_bytes: bytes = b"") -> dict:
        return self.site.build_report(project, photo_desc, image_bytes)

    def handle(self, ctx, message: str):
        return self.todo("工程 Agent：add_report/inspect/craft_answer/build_report_draft")
