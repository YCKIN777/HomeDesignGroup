# -*- coding: utf-8 -*-
"""verify_carrier.py — 5.5 项目承接端到端验证

链路：派单→方案→报价→签约→开工→日报→五节点验收 → GET /projects/{pid}/detail 汇总
另查工作台 HTML 含 s-carrier 面板与 loadProjectDetail 函数。
"""
import json
import re
import sqlite3
import sys
import urllib.request
from urllib.parse import quote

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
    with urllib.request.urlopen(BASE + quote(path, safe="/:?=&"), timeout=10) as r:
        return json.loads(r.read().decode())


# 前置：造测试客户+项目
conn = sqlite3.connect(DB)
for t in ("site_reports", "inspections", "quotes", "design_plans"):
    conn.execute(f"DELETE FROM {t} WHERE project_id IN "
                 "(SELECT id FROM projects WHERE customer_id IN "
                 "(SELECT id FROM customers WHERE phone='19900005555'))")
conn.execute("DELETE FROM projects WHERE customer_id IN "
             "(SELECT id FROM customers WHERE phone='19900005555')")
conn.execute("DELETE FROM customers WHERE phone='19900005555'")
conn.execute("INSERT INTO customers(phone,name,estate,area,budget_range,status,channel,tags) "
             "VALUES('19900005555','承接测试','卓越中环',118,'60-80万','派单','小红书','测试')")
cid = conn.execute("SELECT id FROM customers WHERE phone='19900005555'").fetchone()[0]
conn.commit()
conn.close()

# 1. 全链路走通
r = post("/api/dispatch", {"user": "admin", "customer_id": cid, "designer": "黄旭"})
pid = r["id"]
check("派单建项目", bool(pid), f"r={r}")

r = post(f"/api/projects/{pid}/plans", {"user": "黄旭", "style": "现代简约", "points": "LDK一体"})
check("建方案", r.get("version") == 1, f"r={r}")

r = post(f"/api/projects/{pid}/quote", {"user": "admin"})
qid = r.get("id")
check("生成报价", r.get("items") == 325 and r.get("total") != 118 * 3300.0,
      f"items={r.get('items')} total={r.get('total')}")
post(f"/api/quotes/{qid}/discount", {"user": "admin", "discount": 0.97})
r = post(f"/api/quotes/{qid}/approve", {"user": "周乾坤", "decision": "已审批"})
check("折扣报价审批", r.get("decision") == "已审批", f"r={r}")

for st in ("设计", "报价", "签约"):
    post(f"/api/projects/{pid}/status", {"user": "admin", "to": st})
# 6.4 开工闸门：签约款收足 60% 才放行
import sqlite3 as _sq
_c = _sq.connect(r"H:\AgentProjects\HomeDesignGroup\db\壹城精工.db")
_t = _c.execute("SELECT total FROM quotes WHERE id=?", (qid,)).fetchone()[0]
_c.close()
post(f"/api/quotes/{qid}/payments",
     {"user": "admin", "stage": "签约", "amount": round(_t * 0.6, 2)})
post(f"/api/projects/{pid}/status", {"user": "admin", "to": "开工"})

r = post(f"/api/projects/{pid}/reports", {"user": "范经理", "stage": "水电", "content": "管线完成"})
check("工地日报", r.get("reporter") == "范经理", f"r={r}")

for node in ("水电", "防水", "泥木", "油漆", "竣工"):
    post(f"/api/projects/{pid}/inspections/{node}", {"user": "范经理", "result": "合格"})

# 2. detail 汇总
d = get(f"/api/projects/{pid}/detail")
check("detail 客户信息", d.get("estate") == "卓越中环", f"estate={d.get('estate')}")
check("detail 项目状态", d.get("status") == "开工", f"status={d.get('status')}")
check("detail 方案列表", len(d.get("plans", [])) == 1, f"plans={len(d.get('plans', []))}")
check("detail 报价+付款计划",
      d.get("quote") and d["quote"]["status"] == "已审批"
      and len(d["quote"]["payment_plan"]) == 3,
      f"quote={json.dumps(d.get('quote'), ensure_ascii=False)[:200]}")
check("detail 验收五节点全合格",
      all(v == "合格" for v in d.get("inspections", {}).values())
      and len(d.get("inspections", {})) == 5,
      f"insp={d.get('inspections')}")
check("detail 日报计数", d.get("report_count") == 1, f"reports={d.get('report_count')}")

# 3. 工作台 HTML 含承接面板
html = urllib.request.urlopen(BASE + "/app", timeout=10).read().decode("utf-8")
check("工作台含承接面板", 'id="s-carrier"' in html and "loadProjectDetail" in html,
      f"len={len(html)}")

# 清理
conn = sqlite3.connect(DB)
for t in ("site_reports", "inspections", "quotes", "design_plans"):
    conn.execute(f"DELETE FROM {t} WHERE project_id=?", (pid,))
conn.execute("DELETE FROM projects WHERE id=?", (pid,))
conn.execute("DELETE FROM customers WHERE id=?", (cid,))
conn.execute("DELETE FROM audit_log WHERE target LIKE '%' || ? || '%'", (f"#{pid}",))
conn.commit()
conn.close()

print("\n" + ("全部通过" if not fails else f"{len(fails)} 项失败"))
sys.exit(1 if fails else 0)
