# -*- coding: utf-8 -*-
"""verify_gates.py — 6.4 开工闸门验证：签约款收足才放行开工"""
import json
import sqlite3
import urllib.request

BASE = "http://127.0.0.1:8000"
DB = r"H:\AgentProjects\HomeDesignGroup\db\壹城精工.db"
PASS = 0


def ok(name, cond, extra=""):
    global PASS
    if cond:
        PASS += 1
        print(f"[PASS] {name} {extra}")
    else:
        print(f"[FAIL] {name} {extra}")


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "_body": e.read().decode()[:400]}


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.loads(r.read().decode())


# ---- 建测试数据：客户 + 项目（走合法链到签约）----
# 先清理上一轮可能残留的测试数据
conn0 = sqlite3.connect(DB)
conn0.execute("DELETE FROM payments WHERE quote_id IN "
              "(SELECT id FROM quotes WHERE project_id IN "
              "(SELECT id FROM projects WHERE summary LIKE '%闸门测试%'))")
conn0.execute("DELETE FROM quote_items WHERE quote_id IN "
              "(SELECT id FROM quotes WHERE project_id IN "
              "(SELECT id FROM projects WHERE summary LIKE '%闸门测试%'))")
conn0.execute("DELETE FROM quotes WHERE project_id IN "
              "(SELECT id FROM projects WHERE summary LIKE '%闸门测试%')")
conn0.execute("DELETE FROM projects WHERE summary LIKE '%闸门测试%'")
conn0.execute("DELETE FROM customers WHERE name='闸门测试'")
conn0.execute("DELETE FROM audit_log WHERE target LIKE 'projects#%' AND after LIKE '%闸门%'")
conn0.commit()
conn0.close()

c = post("/api/leads", {"phone": "18800009999", "name": "闸门测试",
                        "estate": "测试楼盘", "budget_range": "60万",
                        "channel": "转介绍", "note": "verify_gates"})
cid = c.get("id")
assert cid, f"建客户失败 {c}"
d = post("/api/dispatch", {"user": "admin", "customer_id": cid, "designer": "黄旭"})
pid = d.get("project_id") or d.get("id")
assert pid, f"派单失败 {d}"
for to in ("量房", "设计", "报价"):
    r = post(f"/api/projects/{pid}/status", {"user": "admin", "to": to})
    ok(f"迁移到 {to}", r.get("to") == to, f"r={r}")

# 报价（10 折免审批 → 草稿 → 项目已签约视为报价已签约）
q = post(f"/api/projects/{pid}/quote", {"user": "admin", "requirements": "闸门测试"})
qid = q.get("id")
ok("生成报价", qid is not None, f"qid={qid}")
total = q.get("total", 0)
due_sign = round(total * 0.6, 2)
r0 = post(f"/api/projects/{pid}/status", {"user": "admin", "to": "签约"})
ok("迁移到 签约", r0.get("to") == "签约", f"r={r0}")

# ---- 闸门测试 1：未收款开工 → 拦截 ----
r1 = post(f"/api/projects/{pid}/status", {"user": "admin", "to": "开工"})
ok("未收款开工拦截", r1.get("_http_error") == 400 and "开工闸门" in r1.get("_body", ""),
   f"http={r1.get('_http_error')} body={r1.get('_body', '')[:60]}")

# ---- 闸门测试 2：收一半 → 仍拦截 ----
r2 = post("/api/quotes/%d/payments" % qid,
          {"user": "admin", "stage": "签约", "amount": round(due_sign / 2, 2)})
ok("收一半成功", r2.get("id") is not None, f"id={r2.get('id')}")
r3 = post(f"/api/projects/{pid}/status", {"user": "admin", "to": "开工"})
ok("半款仍拦截", r3.get("_http_error") == 400, f"http={r3.get('_http_error')}")

# ---- 闸门测试 3：收足 60% → 放行 ----
r4 = post("/api/quotes/%d/payments" % qid,
          {"user": "admin", "stage": "签约", "amount": round(due_sign - round(due_sign / 2, 2), 2)})
ok("补足签约款", r4.get("id") is not None)
r5 = post(f"/api/projects/{pid}/status", {"user": "admin", "to": "开工"})
ok("收足后开工放行", r5.get("to") == "开工", f"r={r5}")

# 后续迁移不受闸门影响
r6 = post(f"/api/projects/{pid}/status", {"user": "admin", "to": "水电"})
ok("开工→水电 正常", r6.get("to") == "水电", f"r={r6}")

# ---- 清理 ----
conn = sqlite3.connect(DB)
conn.execute("DELETE FROM payments WHERE quote_id=?", (qid,))
conn.execute("DELETE FROM quote_items WHERE quote_id=?", (qid,))
conn.execute("DELETE FROM quotes WHERE id=?", (qid,))
conn.execute("DELETE FROM projects WHERE id=?", (pid,))
conn.execute("DELETE FROM customers WHERE id=?", (cid,))
conn.execute("DELETE FROM audit_log WHERE target LIKE 'payments#%'")
conn.commit()
conn.close()
print(f"\n===== {PASS} 项通过 =====")
