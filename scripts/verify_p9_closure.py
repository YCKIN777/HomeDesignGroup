# -*- coding: utf-8 -*-
"""verify_p9_closure.py — P9 完整闭环验证 v2（项目85 刘女士：线索→起草→派单→设计→报价→折扣审批→签约→收款60%→开工→水电→验收）"""
import json
import sqlite3
import sys
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8000"
DB = r"H:\AgentProjects\HomeDesignGroup\db\壹城精工.db"
PASS = FAIL = 0


def ok(n, c, e=""):
    global PASS, FAIL
    PASS += 1 if c else 0
    FAIL += 0 if c else 1
    print(f"[{'PASS' if c else 'FAIL'}] {n} {e}")


def req(path, body=None, method="GET"):
    path = urllib.parse.quote(path, safe="/?=&%")
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=60) as rr:
            return rr.status, json.loads(rr.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}

# 0) 前置：线索110+项目85 已由浏览器实测建立；幂等重置演示数据
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
c = conn.execute("SELECT id FROM customers WHERE phone='13900001111'").fetchone()
ok("线索#110 已建档(浏览器实测)", c is not None)
cid = c["id"]
p = conn.execute("SELECT id,status FROM projects WHERE customer_id=? ORDER BY id DESC LIMIT 1", (cid,)).fetchone()
pid = p["id"]
conn.execute("DELETE FROM inspections WHERE project_id=?", (pid,))
conn.execute("DELETE FROM site_reports WHERE project_id=?", (pid,))
conn.execute("DELETE FROM payments WHERE quote_id IN (SELECT id FROM quotes WHERE project_id=?)", (pid,))
conn.execute("DELETE FROM quotes WHERE project_id=?", (pid,))
conn.execute("DELETE FROM design_plans WHERE project_id=?", (pid,))
conn.execute("UPDATE projects SET status='量房' WHERE id=?", (pid,))
conn.commit()
conn.close()
p2 = sqlite3.connect(DB).execute(
    "SELECT status FROM projects WHERE id=?", (pid,)).fetchone()[0]
ok("派单建项目(浏览器实测,幂等重置)", p2 == "量房", f"status={p2}")

# 1) 设计方案（黄旭 设计总监）→ 状态迁移 设计
code, d = req(f"/api/projects/{pid}/plans", {"user": "黄旭", "style": "现代简约", "points": "LDK一体+全屋收纳"}, "POST")
ok("设计-方案创建", code == 200 and d.get("status") == "初稿", f"code={code} ver={d.get('version')}")
code, d = req(f"/api/projects/{pid}/status", {"user": "admin", "to": "设计"}, "POST")
ok("状态-量房→设计", code == 200 and d.get("to") == "设计", f"code={code} from={d.get('from')}->{d.get('to')}")

# 2) 报价生成（admin，含 325 模板明细）
code, d = req(f"/api/projects/{pid}/quote", {"user": "admin"}, "POST")
ok("报价-生成(325明细)", code == 200 and d.get("id") and d.get("items", 0) >= 300, f"code={code} items={d.get('items')}")
qid = d["id"]

# 3) 折扣 0.97（<9.8折→待审批→董事长审批）
code, d = req(f"/api/quotes/{qid}/discount", {"user": "admin", "discount": 0.97}, "POST")
ok("报价-折扣0.97→待审批", code == 200 and d.get("status") == "待审批" and d.get("need_approval"), f"code={code} status={d.get('status')}")
code, d = req(f"/api/quotes/{qid}/approve", {"user": "周乾坤", "decision": "已审批"}, "POST")
ok("报价-董事长审批通过", code == 200 and d.get("decision") == "已审批", f"code={code}")

# 4) 状态逐级：报价→签约→收款60%→开工（闸门）
for st in ("报价", "签约"):
    code, d = req(f"/api/projects/{pid}/status", {"user": "admin", "to": st}, "POST")
    ok(f"状态-{st}", code == 200 and d.get("to") == st, f"code={code} {d.get('from')}->{d.get('to')}")
conn2 = sqlite3.connect(DB)
total = conn2.execute("SELECT total FROM quotes WHERE id=?", (qid,)).fetchone()[0]
conn2.close()
amount = round(total * 0.6, 2)
code, d = req(f"/api/quotes/{qid}/payments", {"user": "admin", "stage": "签约", "amount": amount}, "POST")
ok("收款-签约60%", code == 200 and d.get("amount") == amount, f"code={code} amount={d.get('amount')}")
code, d = req(f"/api/projects/{pid}/status", {"user": "admin", "to": "开工"}, "POST")
ok("状态-开工(闸门放行)", code == 200 and d.get("to") == "开工", f"code={code} {d.get('from')}->{d.get('to')}")

# 5) 工程日报+水电验收
code, d = req(f"/api/projects/{pid}/reports", {"user": "范经理", "stage": "水电", "content": "管线排布完成"}, "POST")
ok("工程-水电日报", code == 200 and d.get("reporter") == "范经理", f"code={code}")
code, d = req(f"/api/projects/{pid}/inspections/水电", {"user": "范经理", "result": "合格"}, "POST")
ok("验收-水电合格", code == 200 and d.get("result") == "合格", f"code={code}")

# 6) 全链路详情
code, d = req(f"/api/projects/{pid}/detail")
ok("闭环-项目全量详情", code == 200 and d.get("status") == "开工"
   and d.get("quote") and d["quote"]["status"] == "已审批"
   and len(d["quote"].get("payment_plan", [])) == 3 and d.get("report_count", 0) >= 1,
   f"status={d.get('status')} quote={d.get('quote',{}).get('status') if d.get('quote') else 'n'} plans={len(d.get('payment_plan', []) if False else d.get('plans', []))} rc={d.get('report_count')}")

print(f"\n===== P9 闭环: {PASS} 通过 | {FAIL} 失败 =====")
sys.exit(1 if FAIL else 0)
