# -*- coding: utf-8 -*-
"""清理验证脚本产生的合成沉淀条目（保留真实沉淀）"""
import sqlite3

DB = r"H:\AgentProjects\HomeDesignGroup\db\壹城精工.db"
conn = sqlite3.connect(DB)
cur = conn.execute("DELETE FROM sedimentation_items WHERE title IN ('首联黄金24小时','无实例')")
print("已清理合成沉淀条目:", cur.rowcount, "条")
conn.commit()
left = conn.execute("SELECT id,title,status FROM sedimentation_items").fetchall()
print("沉淀中心现存:", left)
conn.close()
