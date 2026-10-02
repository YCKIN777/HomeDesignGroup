# -*- coding: utf-8 -*-
"""
db.py — 数据访问公共层
职责：统一连接、审计写日志、常量。所有业务模块走本模块访问数据库。
"""
import os
import sqlite3

ROOT = r"H:\AgentProjects\HomeDesignGroup"
COMPANY = "壹城精工"
DB_PATH = os.path.join(ROOT, "db", f"{COMPANY}.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.isolation_level = None        # 自动提交：避免"database is locked"（单机单进程场景）
    return conn


def audit(user: str, action: str, target: str, before=None, after=None):
    """写审计日志（人审后发/派单/状态变更等全追溯）"""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO audit_log(user, action, target, before, after) VALUES(?,?,?,?,?)",
            (user, action, target, before, after))


def customer_summary(c: dict) -> str:
    """客户画像摘要（供派单/草稿/评分使用）"""
    parts = [c.get("estate") or "", c.get("layout") or "",
             f"{c.get('area')}㎡" if c.get("area") else "",
             f"预算{c.get('budget_range')}" if c.get("budget_range") else "",
             c.get("style") or "", c.get("tags") or ""]
    return " ".join(p for p in parts if p).strip() or "（暂无需求信息）"
