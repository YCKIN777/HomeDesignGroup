# -*- coding: utf-8 -*-
"""verify_data_loaded.py — B 阶段：真实数据灌入后验证
- owners：插入一条【示例-演示用】业主（真实业主由业务导入，不编造）
- 工艺问答：真实命中（轻钢龙骨吊顶 / 卫生间防水 / 贴砖工艺）
- 报价单：真实材料行（瓷砖类），列项严格
- 清理：示例业主保留（标注演示），其余测试数据清理
"""
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


# 1. 数据量核对（真实灌入：工艺 211 / 材料 68）
conn = connect()
n_c = conn.execute("SELECT COUNT(*) c FROM craft_knowledge").fetchone()["c"]
n_m = conn.execute("SELECT COUNT(*) c FROM materials").fetchone()["c"]
check("工艺知识≥200 条", n_c >= 200, f"实际={n_c}")
check("材料库≥60 条", n_m >= 60, f"实际={n_m}")

# 2. 示例业主（幂等 upsert，保留供报价演示；清理历史测试残留 wx_dbg）
conn.execute("DELETE FROM owners WHERE wechat_id IN ('wx_dbg','demo_wx_1','wx_test_core')")
conn.execute("INSERT OR REPLACE INTO owners (wechat_id,nickname,community,house_area,"
             "layout_json,budget_total,budget_used,style_preference) "
             "VALUES ('demo_owner_001','示例业主（演示用）','保利和光尘樾',189,"
             "'{\"rooms\":4}',800000,120000,'新中式')")
conn.commit()
oid = conn.execute("SELECT id FROM owners WHERE wechat_id='demo_owner_001'").fetchone()["id"]
conn.close()

# 3. 工艺问答：真实命中（轻钢龙骨吊顶 / 卫生间防水 / 瓷砖铺贴）
for q, kw in (("轻钢龙骨吊顶怎么做", "轻钢龙骨"),
              ("卫生间防水怎么做", "防水"),
              ("瓷砖铺贴工艺", "水泥砂浆")):
    r = http("POST", "/api/agents/craft-qa", {"question": q, "user": "客服"})
    hits = r.get("craft", [])
    check(f"工艺问答[{q}] 命中真实条目", len(hits) >= 1, f"hits={hits[:1]}")
    if hits:
        check(f"  条目含来源", bool(hits[0].get("source")), f"src={hits[0].get('source')}")
        check(f"  含关键词[{kw}]", any(kw in (h.get("title", "") + h.get("content", ""))
                                    for h in hits), f"titles={[h['title'] for h in hits[:3]]}")

# 4. 报价单：真实材料行（瓷砖类，列项严格+合价勾稽）
r2 = http("POST", "/api/agents/quote", {"owner_id": oid, "requirements": "全屋硬装",
                                        "category": "瓷砖", "user": "销售"})
check("报价单列项严格", r2.get("columns") == ["项目", "规格", "单位", "数量", "单价", "合价", "备注"],
      f"columns={r2.get('columns')}")
check("报价单含真实材料行", r2.get("row_count", 0) >= 1, f"rows={r2.get('row_count')}")
if r2.get("rows"):
    check("合价=数量×单价", all(row[5] == round(row[3] * row[4], 2) for row in r2["rows"]),
          f"rows[0]={r2['rows'][0]}")
    print(f"  示例行：{r2['rows'][0]}")

# 5. 材料库抽查（来源可追溯）
conn = connect()
m = conn.execute("SELECT name, price, source_file FROM materials "
                 "WHERE category LIKE '%瓷砖%' LIMIT 3").fetchall()
check("材料带来源标注", all(r["source_file"] for r in m), f"materials={[dict(r) for r in m]}")
conn.close()

print("\n" + ("全部通过" if not fails else f"{len(fails)} 项失败"))
sys.exit(1 if fails else 0)
