# -*- coding: utf-8 -*-
import sqlite3, os
p = r"H:\AgentProjects\HomeDesignGroup\db\壹城精工.db"
print("db exists:", os.path.exists(p))
conn = sqlite3.connect(p)
rows = conn.execute(
    "SELECT id, estate, area, layout, style, budget_range, channel, source, status, created_at "
    "FROM customers WHERE source='AI获客' ORDER BY id DESC LIMIT 5"
).fetchall()
print("AI获客建档记录（最近5条）:")
for r in rows:
    print(r)
conn.close()
