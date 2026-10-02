# -*- coding: utf-8 -*-
"""契约线 3 Agent HTTP smoke（Step 6 外层集成验证）"""
import json
import sqlite3
import sys
import urllib.request

sys.path.insert(0, r"H:\AgentProjects\HomeDesignGroup\src")
from models.core import connect

BASE = "http://127.0.0.1:8000"
fails = []


def check(name, cond, msg):
    if not cond:
        fails.append(name)
        print(f"[FAIL] {name}: {msg}")
    else:
        print(f"[PASS] {name}")


def http(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


# 前置 seed：1 业主 + 1 工艺 + 1 材料（清理用精确 ID，避免误删 B 阶段 demo_owner_001）
conn = connect()
conn.execute("DELETE FROM craft_knowledge WHERE title='demo-轻钢龙骨双层石膏板'")
conn.execute("DELETE FROM materials WHERE name='demo-龙牌石膏板'")
conn.execute("DELETE FROM owners WHERE wechat_id='demo_wx_1'")
conn.execute("INSERT INTO craft_knowledge (category,title,content,source_file,embedding_id) "
             "VALUES ('降噪隔墙','demo-轻钢龙骨双层石膏板','轻钢龙骨+岩棉+双层石膏板，隔声45dB',"
             "'knowledge/02-工艺-隐蔽工程验收.md','')")
conn.execute("INSERT INTO materials (category,name,spec,supplier,price,moq,tags) "
             "VALUES ('石膏板','demo-龙牌石膏板','1200x2400mm','龙牌',35,50,'隔墙')")
conn.execute("INSERT INTO owners (wechat_id,nickname,community,house_area,layout_json,"
             "budget_total,budget_used,style_preference) "
             "VALUES ('demo_wx_1','演示业主','保利和光尘樾',189,'{\"rooms\":4}',800000,120000,'新中式')")
conn.commit()
oid = conn.execute("SELECT id FROM owners WHERE wechat_id='demo_wx_1'").fetchone()["id"]
conn.close()

# 1. 工艺问答
r = http("POST", "/api/agents/craft-qa", {"question": "降噪隔墙怎么做", "user": "客服"})
check("HTTP 工艺问答命中", len(r.get("craft", [])) >= 1, f"resp={r}")

# 2. 报价单
r2 = http("POST", "/api/agents/quote", {"owner_id": oid, "requirements": "全屋硬装",
                                        "category": "石膏板", "user": "销售"})
check("HTTP 报价单草稿", r2.get("status") == "draft" and r2.get("row_count", 0) >= 1,
      f"resp={r2}")

# 3. 工地日报
r3 = http("POST", "/api/agents/site-report", {"project": "保利和光尘樾-189", "user": "监理"})
check("HTTP 工地日报 pending", r3.get("status") == "pending_human", f"resp={r3}")

# 清理（精确 ID，不碰 B 阶段 demo_owner_001）
conn = connect()
conn.execute("DELETE FROM craft_knowledge WHERE title='demo-轻钢龙骨双层石膏板'")
conn.execute("DELETE FROM materials WHERE name='demo-龙牌石膏板'")
conn.execute("DELETE FROM owners WHERE wechat_id='demo_wx_1'")
conn.commit()
conn.close()

print("\n" + ("全部通过" if not fails else f"{len(fails)} 项失败"))
sys.exit(1 if fails else 0)
