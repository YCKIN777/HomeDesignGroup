# -*- coding: utf-8 -*-
"""Step 2.8 + 4.6 自检：CSV 文本导入（含BOM/空行）+ 页面角色化元素"""
import json
import sqlite3
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
DB = r"H:\AgentProjects\HomeDesignGroup\db\壹城精工.db"
ok = True

def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print("HTTP", e.code, body)
        raise

# 1. CSV 文本导入：表头含 BOM、带空行、2新建+1重复+1缺号
csv_text = ('\ufeffphone,name,estate,layout,area,budget_range,style,intent_time,channel,tags,source\r\n'
            '13500000001,CSV甲,卓越中环,四房,140,50-80万,现代简约,1个月内,抖音,改善,批量\r\n'
            '13500000002,CSV乙,保利和光尘樾,,,,,2个月内,小红书,,批量\r\n'
            '13500000001,CSV甲改,,,,,,,,,\r\n'
            ',,缺号行,,,,,,,,\r\n'
            '\r\n')
d = post("/api/leads/import/csv", {"user": "admin", "csv_text": csv_text})
print("1. CSV导入:", "created=", d["created"], "merged=", d["merged"], "error=", d["error"])
ok = ok and d["created"] == 2 and d["merged"] == 1 and d["error"] == 1

# 2. 页面角色化元素存在
html = urllib.request.urlopen(BASE + "/app", timeout=10).read().decode()
for k in ("CAN(", "importCsv", "platform_role", "批量导入CSV"):
    print("2. 页面含", k, ":", k in html)
    ok = ok and (k in html)

# 清理本次 CSV 导入数据
conn = sqlite3.connect(DB)
for p in ("13500000001", "13500000002"):
    for cid in [r[0] for r in conn.execute("SELECT id FROM customers WHERE phone=?", (p,))]:
        for t in ("messages", "followups", "projects", "todos", "sessions"):
            conn.execute(f"DELETE FROM {t} WHERE customer_id=?", (cid,))
        conn.execute("DELETE FROM customers WHERE id=?", (cid,))
conn.commit()
conn.close()
print("3. 测试数据已清理")

print("== 自检结论 ==")
print("  PASS — CSV导入(含BOM/空行) 与 角色化工作台 全部通过" if ok else "  FAIL — 请检查上述失败项")
