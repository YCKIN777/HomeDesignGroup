# -*- coding: utf-8 -*-
"""memory_api 路由：L4 文本记忆（写入/检索/模板），本体 frontmatter 标注"""
import os
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

ROOT = r"H:\AgentProjects\HomeDesignGroup"
MEMORY_DIR = os.path.join(ROOT, "memory")


class MemoryIn(BaseModel):
    concept_id: str
    relation: str = "derived_from"      # 关系白名单: part_of/preceded_by/has_participant/has_responsible/derived_from
    state: str = "观察"
    source: str = "人工录入"
    content: str


router = APIRouter(prefix="/api/memory", tags=["memory"])

RELATIONS = {"part_of", "preceded_by", "has_participant", "has_responsible", "derived_from"}


@router.post("")
def write_memory(body: MemoryIn):
    if body.relation not in RELATIONS:
        return {"error": f"关系不在白名单: {body.relation}（可选 {sorted(RELATIONS)}）"}
    if not body.content.strip():
        return {"error": "内容为空"}
    fname = f"{datetime.now().strftime('%Y-%m-%d')}-{body.concept_id.replace('.', '-')}.md"
    path = os.path.join(MEMORY_DIR, fname)
    if os.path.exists(path):  # 同一天同概念 → 追加而非覆盖
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n\n---\n{body.content.strip()}\n")
        return {"file": os.path.relpath(path, ROOT), "append": True}
    text = (f"---\nconcept_id: {body.concept_id}\nrelation: {body.relation}\n"
            f"state: {body.state}\ntime: \"{datetime.now().strftime('%Y-%m-%d')}\"\n"
            f"source: {body.source}\n---\n\n{body.content.strip()}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return {"file": os.path.relpath(path, ROOT), "append": False}


@router.get("/template")
def template():
    return {
        "说明": "L4 文本记忆 = 可读 md + YAML frontmatter（本体标注），供人维护、按需检索。",
        "frontmatter字段": {"concept_id": "术语注册表 id", "relation": "关系白名单",
                            "state": "观察/已核验/已废弃", "time": "日期", "source": "来源"},
        "示例": "---\nconcept_id: concept.channel\nrelation: derived_from\nstate: 观察\n"
                "time: \"2026-09-30\"\nsource: 壹城内部沟通\n---\n正文内容",
        "关系白名单": sorted(RELATIONS),
    }


@router.get("/search")
def search(q: str, top_k: int = 5):
    """Otter 读取第3步：按需检索 L3+L4（知识库/沉淀/记忆文件/客户画像），带来源"""
    from memory_manager import MemoryManager
    mm = MemoryManager("壹城精工")
    if not q.strip():
        return {"total": 0, "items": []}
    hits = mm.retrieve(q, top_k=top_k)
    return {"total": len(hits), "items": hits, "layer_note": "L3=知识库/沉淀/画像, L4=文本记忆"}


@router.get("/list")
def list_memory():
    files = sorted(os.listdir(MEMORY_DIR)) if os.path.isdir(MEMORY_DIR) else []
    return {"total": len(files), "files": files}
