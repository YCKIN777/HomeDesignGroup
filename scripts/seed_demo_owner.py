# -*- coding: utf-8 -*-
"""seed_demo_owner.py — 幂等重插示例业主 demo_owner_001

背景：verify_agents_http.py 早期清理语句用 LIKE 'demo_%' 误删过 B 阶段示例业主；
本脚本用 INSERT OR REPLACE 幂等恢复，可安全重复执行。
真实业主由业务导入，此条仅作演示（nickname 已标注）。
"""
import sqlite3

DB = r"H:\AgentProjects\HomeDesignGroup\db\homeagent.db"

conn = sqlite3.connect(DB)
conn.execute(
    "INSERT OR REPLACE INTO owners "
    "(wechat_id, nickname, community, house_area, layout_json, budget_total,"
    " budget_used, style_preference) VALUES (?,?,?,?,?,?,?,?)",
    ("demo_owner_001", "示例业主（演示用）", "保利和光尘樾", 189.0,
     '{"rooms":4}', 800000.0, 120000.0, "新中式"))
conn.commit()
oid = conn.execute(
    "SELECT id FROM owners WHERE wechat_id='demo_owner_001'").fetchone()[0]
conn.close()
print(f"demo_owner_001 就绪，id={oid}")
