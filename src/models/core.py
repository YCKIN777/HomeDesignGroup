# -*- coding: utf-8 -*-
"""core.py — 契约 Step 3：三张核心表的 model 定义（Day 1 结构化入库，原则 2）

架构契约 v0.1 指定三张表（owners 业主档案 / craft_knowledge 工艺知识库 /
materials 建材供应链库），schema 字段严格按契约。本文件为 dataclass 语义层 +
DDL 常量；读写一律走 API（routers/core_api.py），禁止硬编码在 prompt。
未来迁 SQLAlchemy：DDL 同构建 model，业务接口不变。
"""
from dataclasses import dataclass, field
from typing import Optional

DB_PATH = r"H:\AgentProjects\HomeDesignGroup\db\homeagent.db"

DDL = [
    """CREATE TABLE IF NOT EXISTS owners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        wechat_id TEXT UNIQUE,
        nickname TEXT,
        community TEXT,
        house_area REAL,
        layout_json TEXT,
        budget_total REAL,
        budget_used REAL,
        style_preference TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        updated_at TEXT DEFAULT (datetime('now','localtime'))
    )""",
    """CREATE TABLE IF NOT EXISTS craft_knowledge (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,
        title TEXT,
        content TEXT,
        source_file TEXT,
        embedding_id TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,
        name TEXT,
        spec TEXT,
        supplier TEXT,
        price REAL,
        moq REAL,
        tags TEXT,
        source_file TEXT
    )""",
]


@dataclass
class Owner:
    """业主档案（Library）"""
    wechat_id: str
    nickname: str = ""
    community: str = ""
    house_area: float = 0.0
    layout_json: str = "{}"
    budget_total: float = 0.0
    budget_used: float = 0.0
    style_preference: str = ""
    id: Optional[int] = None


@dataclass
class CraftKnowledge:
    """工艺知识条目（RAG 语料）"""
    category: str
    title: str
    content: str
    source_file: str = ""
    embedding_id: str = ""
    id: Optional[int] = None


@dataclass
class Material:
    """建材供应条目"""
    category: str
    name: str
    spec: str = ""
    supplier: str = ""
    price: float = 0.0
    moq: float = 0.0
    tags: str = ""
    source_file: str = ""
    id: Optional[int] = None


def connect(db_path: str = DB_PATH):
    import sqlite3
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn
