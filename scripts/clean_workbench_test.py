# -*- coding: utf-8 -*-
"""清理工作台v2验证产生的测试数据（手机号 13707770001，AI 自产测试数据）"""
import sqlite3

DB = r"H:\AgentProjects\HomeDesignGroup\db\壹城精工.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()
rows = cur.execute("SELECT id FROM customers WHERE phone='13707770001'").fetchall()
for (cid,) in rows:
    for t in ("messages", "followups", "todos", "sessions"):
        cur.execute(f"DELETE FROM {t} WHERE customer_id=?", (cid,))
    cur.execute("DELETE FROM projects WHERE customer_id=?", (cid,))
    cur.execute("DELETE FROM customers WHERE id=?", (cid,))
    print("已清理客户", cid, "及关联消息/待办/会话/项目")
conn.commit()
conn.close()
print("剩余线索数:", end=" ")
conn = sqlite3.connect(DB)
print(conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0])
conn.close()
