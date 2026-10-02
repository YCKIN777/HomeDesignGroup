# -*- coding: utf-8 -*-
"""Step 1.1 自检脚本：核对目录、数据库表、默认账号、meta 版本"""
import os
import sqlite3

ROOT = r"H:\AgentProjects\HomeDesignGroup"
DB_PATH = os.path.join(ROOT, "db", "壹城精工.db")

EXPECT_DIRS = ["src\\kernel", "company_profiles\\壹城精工", "db", "knowledge",
               "sedimentation", "memory", "tests", "scripts"]
EXPECT_TABLES = {"customers", "projects", "messages", "followups",
                 "sedimentation_items", "users", "audit_log", "sessions", "meta"}

ok = True

print("== 1) 目录核对 ==")
for d in EXPECT_DIRS:
    exists = os.path.isdir(os.path.join(ROOT, d))
    ok = ok and exists
    print(f"  {'OK ' if exists else 'MISS'} {d}")

print("== 2) 数据库文件 ==")
exists = os.path.isfile(DB_PATH)
ok = ok and exists
print(f"  {'OK ' if exists else 'MISS'} {DB_PATH} ({os.path.getsize(DB_PATH) if exists else 0} bytes)")

print("== 3) 表核对 ==")
conn = sqlite3.connect(DB_PATH)
tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
missing = EXPECT_TABLES - tables
ok = ok and not missing
print(f"  {len(tables)} 张表: {sorted(tables)}")
print(f"  {'OK  全部9张表就位' if not missing else 'MISS ' + str(missing)}")

print("== 4) 默认账号 ==")
rows = conn.execute("SELECT account, role, company FROM users").fetchall()
print(f"  {rows}")
ok = ok and any(r[0] == "admin" for r in rows)

print("== 5) schema 版本 ==")
meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
print(f"  {meta}")
ok = ok and meta.get("schema_version") == "1"
conn.close()

print("\n== 自检结论 ==")
print("  PASS — Step 1.1 产物完整，可进入 Step 1.2" if ok else "  FAIL — 请检查上述 MISS 项")
