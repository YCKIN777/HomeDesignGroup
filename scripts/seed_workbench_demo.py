# -*- coding: utf-8 -*-
"""_seed_workbench_demo.py — 造一份可演示的承接数据（客户+派单+报价325条明细）"""
import json
import sqlite3
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
DB = r"H:\AgentProjects\HomeDesignGroup\db\壹城精工.db"
PHONE = "19900005555"


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "_body": e.read().decode()[:200]}
    except Exception as e:
        return {"_err": repr(e)}


# 幂等清理
conn = sqlite3.connect(DB)
conn.execute("DELETE FROM quote_items WHERE quote_id IN (SELECT id FROM quotes WHERE project_id IN "
             "(SELECT id FROM projects WHERE customer_id IN (SELECT id FROM customers WHERE phone=?)))", (PHONE,))
conn.execute("DELETE FROM quotes WHERE project_id IN (SELECT id FROM projects WHERE customer_id IN "
             "(SELECT id FROM customers WHERE phone=?))", (PHONE,))
conn.execute("DELETE FROM projects WHERE customer_id IN (SELECT id FROM customers WHERE phone=?)", (PHONE,))
conn.execute("DELETE FROM customers WHERE phone=?", (PHONE,))
conn.execute("INSERT INTO customers(phone,name,estate,area,budget_range,status,channel,tags) "
             "VALUES(?,'王女士','保利和光尘樾',189,'80-100万','到店','转介绍','新中式|全屋整装')", (PHONE,))
cid = conn.execute("SELECT id FROM customers WHERE phone=?", (PHONE,)).fetchone()[0]
conn.commit()
conn.close()

r = post("/api/dispatch", {"user": "admin", "customer_id": cid, "designer": "黄旭"})
pid = r.get("id")
print("project:", pid, r.get("dup"))
r = post(f"/api/projects/{pid}/plans", {"user": "黄旭", "style": "新中式",
                                        "points": "客餐厅一体、玄关端景、主卧套房、全屋收纳"})
print("plan:", r.get("id"), r.get("_http_error", ""))
r = post(f"/api/projects/{pid}/quote", {"user": "admin"})
qid = r.get("id")
print(f"quote: #{qid} total=¥{r.get('total'):,.0f} items={r.get('items')} est={r.get('est_items')}")
# 修正 2 条明细模拟量房复核
items = post(f"/api/quotes/{qid}/items", {})
rows = [x for sec in items.get("groups", {}).values() for x in sec]
est_rows = [x for x in rows if x.get("est")][:2]
for i, x in enumerate(est_rows):
    r2 = post(f"/api/quotes/{qid}/items/{x['id']}", {"user": "admin", "qty": round(x["qty"] * 0.82, 1)})
    print(f"fix {x['item'][:16]}: qty {x['qty']} -> {r2.get('qty')} amount=¥{r2.get('amount'):,.0f}")
with urllib.request.urlopen(BASE + f"/api/projects/{pid}/detail", timeout=30) as rr:
    d = json.loads(rr.read().decode())
print("detail ok, quote total:", d.get("quote", {}).get("total"), "plans:", len(d.get("plans") or []))
print(f"DEMO_PID={pid}  DEMO_QID={qid}")
