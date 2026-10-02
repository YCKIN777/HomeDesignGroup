# -*- coding: utf-8 -*-
"""verify_plans.py — 5.2 设计方案沉淀 API 验证

覆盖：方案创建（版本递增）、列表、状态流转（初稿→评审中→已定稿）、
非法流转拦截、只读角色权限、审计留痕。
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
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "_body": e.read().decode()[:200]}


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return json.loads(r.read().decode())


# 前置：造测试客户+项目（自清理）
conn = sqlite3.connect(DB)
conn.execute("DELETE FROM design_plans WHERE project_id IN "
             "(SELECT id FROM projects WHERE customer_id IN "
             "(SELECT id FROM customers WHERE phone='19900008888'))")
conn.execute("DELETE FROM projects WHERE customer_id IN "
             "(SELECT id FROM customers WHERE phone='19900008888')")
conn.execute("DELETE FROM customers WHERE phone='19900008888'")
conn.execute("INSERT INTO customers(phone,name,estate,status,channel,tags) "
             "VALUES('19900008888','方案测试','测试楼盘','派单','转介绍','测试')")
cid = conn.execute("SELECT id FROM customers WHERE phone='19900008888'").fetchone()[0]
conn.commit()
conn.close()

r = post("/api/dispatch", {"user": "admin", "customer_id": cid, "designer": "黄旭"})
pid = r["id"]
check("派单建项目", bool(pid), f"r={r}")

# 1. 建方案 v1
r = post(f"/api/projects/{pid}/plans", {"user": "黄旭", "style": "新中式", "points": "客餐厅一体化"})
check("建方案 v1", r.get("version") == 1 and r.get("status") == "初稿", f"r={r}")

# 2. 建方案 v2（版本递增）
r2 = post(f"/api/projects/{pid}/plans", {"user": "黄旭", "style": "新中式", "points": "v2 加岛台"})
check("建方案 v2 版本递增", r2.get("version") == 2, f"r={r2}")

# 3. 列表
lst = get(f"/api/projects/{pid}/plans")
check("方案列表", lst.get("total") == 2, f"total={lst.get('total')}")

# 4. 状态流转：v1 初稿→评审中→已定稿（设计总监黄旭，有 design_plan）
pl1 = lst["items"][1]["id"]
r = post(f"/api/projects/plans/{pl1}/status", {"user": "黄旭", "status": "评审中"})
check("初稿→评审中", r.get("to") == "评审中", f"r={r}")
r = post(f"/api/projects/plans/{pl1}/status", {"user": "黄旭", "status": "已定稿"})
check("评审中→已定稿", r.get("to") == "已定稿", f"r={r}")

# 5. 非法流转：已定稿→初稿 拦截
r = post(f"/api/projects/plans/{pl1}/status", {"user": "黄旭", "status": "初稿"})
check("已定稿不可回退", r.get("_http_error") == 400, f"r={r}")

# 6. 主管（无 design_plan）不可流转方案
r = post(f"/api/projects/plans/{pl1}/status", {"user": "admin", "status": "初稿"})
check("主管不可流转方案", r.get("_http_error") == 403, f"r={r}")

# 7. 审计
conn = sqlite3.connect(DB)
n = conn.execute("SELECT COUNT(*) FROM audit_log WHERE target LIKE 'design_plans#%'").fetchone()[0]
conn.close()
check("审计留痕", n >= 4, f"audit={n}")

# 清理
conn = sqlite3.connect(DB)
conn.execute("DELETE FROM design_plans WHERE project_id=?", (pid,))
conn.execute("DELETE FROM projects WHERE id=?", (pid,))
conn.execute("DELETE FROM customers WHERE id=?", (cid,))
conn.execute("DELETE FROM audit_log WHERE target LIKE 'design_plans#%'")
conn.commit()
conn.close()

print("\n" + ("全部通过" if not fails else f"{len(fails)} 项失败"))
sys.exit(1 if fails else 0)
