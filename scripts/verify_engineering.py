# -*- coding: utf-8 -*-
"""verify_engineering.py — 5.4 工程承接 API 验证

覆盖：工地日报（项目经理写/查）、五节点验收（水电/防水/泥木/油漆/竣工）、
非法节点拦截、非项目经理无权限、整改→合格覆盖、验收看板。
"""
import json
import sqlite3
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"
DB = r"H:\AgentProjects\HomeDesignGroup\db\壹城精工.db"
fails = []


def check(name, cond, detail=""):
    if not cond:
        fails.append(name)
        print(f"[FAIL] {name}: {detail}")
    else:
        print(f"[PASS] {name}")


def post(path, body):
    from urllib.parse import quote
    req = urllib.request.Request(BASE + quote(path, safe="/:?=&"),
                                 data=json.dumps(body).encode(),
                                 method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "_body": e.read().decode()[:200]}


def get(path):
    from urllib.parse import quote
    with urllib.request.urlopen(BASE + quote(path, safe="/:?=&"), timeout=10) as r:
        return json.loads(r.read().decode())


# 前置：造测试客户+项目
conn = sqlite3.connect(DB)
conn.execute("DELETE FROM site_reports WHERE project_id IN "
             "(SELECT id FROM projects WHERE customer_id IN "
             "(SELECT id FROM customers WHERE phone='19900006666'))")
conn.execute("DELETE FROM inspections WHERE project_id IN "
             "(SELECT id FROM projects WHERE customer_id IN "
             "(SELECT id FROM customers WHERE phone='19900006666'))")
conn.execute("DELETE FROM projects WHERE customer_id IN "
             "(SELECT id FROM customers WHERE phone='19900006666')")
conn.execute("DELETE FROM customers WHERE phone='19900006666'")
conn.execute("INSERT INTO customers(phone,name,estate,area,status,channel,tags) "
             "VALUES('19900006666','工程测试','麓润栖湖',143,'派单','转介绍','测试')")
cid = conn.execute("SELECT id FROM customers WHERE phone='19900006666'").fetchone()[0]
conn.commit()
conn.close()

r = post("/api/dispatch", {"user": "admin", "customer_id": cid, "designer": "黄旭"})
pid = r["id"]
check("派单建项目", bool(pid), f"r={r}")

# 走合法链到开工（量房→设计→报价→签约→开工）
for st in ("设计", "报价", "签约", "开工"):
    post(f"/api/projects/{pid}/status", {"user": "admin", "to": st})

# 1. 项目经理写工地日报
r = post(f"/api/projects/{pid}/reports",
         {"user": "范经理", "stage": "水电", "content": "水电开槽完成，管线排布符合标准"})
check("项目经理写日报", r.get("reporter") == "范经理" and r.get("stage") == "水电", f"r={r}")

# 2. 非项目经理（设计总监黄旭）无日报权限
r = post(f"/api/projects/{pid}/reports", {"user": "黄旭", "stage": "水电", "content": "x"})
check("非项目经理无日报权限", r.get("_http_error") == 403, f"r={r}")

# 3. 日报列表
lst = get(f"/api/projects/{pid}/reports")
check("日报列表", lst.get("total") == 1, f"total={lst.get('total')}")

# 4. 非法验收节点
r = post(f"/api/projects/{pid}/inspections/吊顶", {"user": "范经理", "result": "合格"})
check("非法节点拦截", r.get("_http_error") == 400, f"r={r}")

# 5. 五节点验收：水电/防水/泥木/油漆/竣工
for node in ("水电", "防水", "泥木", "油漆", "竣工"):
    r = post(f"/api/projects/{pid}/inspections/{node}", {"user": "范经理", "result": "合格"})
    check(f"{node}验收合格", r.get("result") == "合格", f"r={r}")

# 6. 整改→覆盖（泥木先整改再合格）
r = post(f"/api/projects/{pid}/inspections/泥木", {"user": "廖经理", "result": "整改", "note": "瓷砖空鼓"})
check("泥木整改", r.get("result") == "整改", f"r={r}")
r = post(f"/api/projects/{pid}/inspections/泥木", {"user": "廖经理", "result": "合格"})
check("泥木复验合格", r.get("result") == "合格", f"r={r}")

# 7. 验收看板：5 节点全合格
board = get(f"/api/projects/{pid}/inspections")
nodes = {n["node"]: n["result"] for n in board["nodes"]}
check("看板五节点", set(nodes) == {"水电", "防水", "泥木", "油漆", "竣工"}, f"nodes={nodes}")
check("看板全合格", all(v == "合格" for v in nodes.values()), f"nodes={nodes}")

# 清理
conn = sqlite3.connect(DB)
conn.execute("DELETE FROM site_reports WHERE project_id=?", (pid,))
conn.execute("DELETE FROM inspections WHERE project_id=?", (pid,))
conn.execute("DELETE FROM projects WHERE id=?", (pid,))
conn.execute("DELETE FROM customers WHERE id=?", (cid,))
conn.execute("DELETE FROM audit_log WHERE target LIKE 'site_reports#%' OR target LIKE 'inspections#%'")
conn.commit()
conn.close()

print("\n" + ("全部通过" if not fails else f"{len(fails)} 项失败"))
sys.exit(1 if fails else 0)
