# -*- coding: utf-8 -*-
"""verify_team_web.py — P8 九部门视图 Web API 端到端（总经办/材料/软装/售后 + 权限）"""
import json
import sqlite3
import subprocess
import sys
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8000"
DB = r"H:\AgentProjects\HomeDesignGroup\db\壹城精工.db"
PASS = 0
FAIL = 0


def ok(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name} {extra}")
    else:
        FAIL += 1
        print(f"[FAIL] {name} {extra}")


def req(path, body=None, method="GET", user=None):
    """user 传给 GET 拼 query（quote 中文），POST/PUT 放 body（json utf-8）。"""
    if user is not None and body is None:
        sep = "&" if "?" in path else "?"
        path = path + sep + "user=" + urllib.parse.quote(user)
    headers = {"Content-Type": "application/json"}
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(r, timeout=60) as rr:
            return rr.status, json.loads(rr.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {"detail": "?"}


# 0) 造数（王女士项目+报价，幂等）
subprocess.run([sys.executable, r"H:\AgentProjects\HomeDesignGroup\scripts\seed_workbench_demo.py"],
               cwd=r"H:\AgentProjects\HomeDesignGroup", check=True, capture_output=True)
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cid = conn.execute("SELECT id FROM customers WHERE phone='19900005555'").fetchone()[0]
pid = conn.execute("SELECT id FROM projects WHERE customer_id=? ORDER BY id DESC LIMIT 1", (cid,)).fetchone()[0]
qid = conn.execute("SELECT id FROM quotes WHERE project_id=? ORDER BY id DESC LIMIT 1", (pid,)).fetchone()[0]
conn.close()

# 1) 总经办（admin=主管 有 audit）
code, d = req("/api/team/ceo/approvals")
ok("CEO 审批汇总", code == 200 and "pending_messages" in d and "pending_quote_approvals" in d, f"code={code}")
code, d = req("/api/team/ceo/dashboard")
ok("CEO 数据看板", code == 200 and "customers_by_status" in d and "payments_collected" in d, f"code={code}")
code, d = req("/api/team/ceo/audit?limit=10")
ok("CEO 审计追溯", code == 200 and "rows" in d, f"code={code}")
code, d = req("/api/team/ceo/coord", {"user": "admin", "note": "P8 验证协调留痕"}, "POST")
ok("CEO 协调留痕", code == 200 and "note" in d, f"code={code}")

# 2) 总经办权限：行政无 audit → 403；财务（杨美华）→ 200
code, d = req("/api/team/ceo/dashboard", user="龙晓玲")
ok("行政无权审计 403", code == 403, f"code={code}")
code, d = req("/api/team/ceo/dashboard", user="杨美华")
ok("财务(创意总监/财务)可审计", code == 200, f"code={code}")

# 3) 材料
code, d = req(f"/api/team/quotes/{qid}/materials")
ok("材料-主材清单", code == 200 and d.get("items_count", 0) > 0 and "material_total" in d,
   f"code={code} count={d.get('items_count')}")
code, d = req("/api/team/materials")
ok("材料-材料库检索", code == 200 and "rows" in d, f"code={code}")

# 4) 软装（黄旭=设计总监 有 soft.write）
code, d = req("/api/team/soft", {"user": "黄旭", "project_id": pid, "category": "家具",
                                 "name": "P8测试沙发", "spec": "2m", "qty": 1, "unit_price": 8888}, "POST")
ok("软装-录入(设计总监)", code == 200 and d.get("amount") == 8888, f"code={code}")
sid = d.get("id")
code, d = req(f"/api/team/soft?project_id={pid}")
ok("软装-清单", code == 200 and d.get("items_count", 0) >= 1, f"code={code}")
code, d = req(f"/api/team/soft/{sid}", {"user": "黄旭", "status": "已确认"}, "PUT")
ok("软装-确认", code == 200 and d.get("status") == "已确认", f"code={code}")
code, d = req(f"/api/team/soft/{sid}", None, "DELETE", user="黄旭")
ok("软装-删除", code == 200 and d.get("id") == sid, f"code={code}")
code, d = req("/api/team/soft", {"user": "admin", "project_id": pid, "category": "灯具",
                                 "name": "主管越权灯", "qty": 1, "unit_price": 1}, "POST")
ok("软装-写权限(主管可)", code == 200, f"code={code}")

# 5) 售后（admin=主管 有 aftersales.write）
code, d = req("/api/team/aftersales/warranty", {"user": "admin", "project_id": pid}, "POST")
ok("售后-质保登记", code == 200 and len(d.get("rows", [])) >= 1, f"code={code}")
code, d = req("/api/team/aftersales/ticket", {"user": "admin", "project_id": pid,
                                             "title": "P8测试工单", "content": "验证"}, "POST")
ok("售后-工单创建", code == 200 and d.get("title") == "P8测试工单", f"code={code}")
tid = d.get("id")
code, d = req(f"/api/team/aftersales?project_id={pid}")
ok("售后-列表", code == 200 and len(d.get("rows", [])) >= 2, f"code={code}")
code, d = req(f"/api/team/aftersales/{tid}/status", {"user": "admin", "status": "处理中"}, "PUT")
ok("售后-状态流转", code == 200 and d.get("status") == "处理中", f"code={code}")
code, d = req("/api/team/aftersales/due", {"user": "admin"}, "POST")
ok("售后-回访SOP", code == 200 and "created" in d, f"code={code}")

# 6) 工作台含九部门面板
try:
    with urllib.request.urlopen(BASE + "/app", timeout=15) as rr:
        html = rr.read().decode("utf-8", "ignore")
    ok("工作台含九部门面板", "s-team" in html and "loadCeo" in html and "asWarranty" in html)
except Exception as e:
    ok("工作台含九部门面板", False, repr(e))

print(f"\n===== {PASS} 通过 | {FAIL} 失败 =====")
sys.exit(1 if FAIL else 0)
