# -*- coding: utf-8 -*-
"""init_core_tables.py — 契约 Step 3 迁移脚本（幂等：重复执行安全）

建三张核心表到 db/homeagent.db（契约线独立库）：
  owners / craft_knowledge / materials
验证：python scripts/init_core_tables.py
"""
import os
import sqlite3
import sys

sys.path.insert(0, r"H:\AgentProjects\HomeDesignGroup\src")

from models.core import DDL, DB_PATH, connect

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
conn = connect()
for ddl in DDL:
    conn.execute(ddl)
conn.commit()

# 校验：三张表都在
rows = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
    "('owners','craft_knowledge','materials')").fetchall()
got = {r["name"] for r in rows}
need = {"owners", "craft_knowledge", "materials"}
conn.close()

if need - got:
    print(f"FAIL: 缺表 {need - got}")
    raise SystemExit(1)
print(f"PASS: 三张核心表就绪（{sorted(got)}）@ {DB_PATH}")
