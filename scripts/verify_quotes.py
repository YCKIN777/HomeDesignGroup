# -*- coding: utf-8 -*-
"""verify_quotes.py — 5.3 报价承接（模板明细版）API 验证

覆盖：报价生成（模板 325 条明细+面积估算）、明细分组、明细修正重算总额、
折扣≥9.8 免审批、折扣<9.8 转待审批、董事长审批、已审批不可再改、
付款计划 60/35/5 勾稽、已签约不可再报价。
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


# 前置：造测试客户(面积189)+项目
conn = sqlite3.connect(DB)
conn.execute("DELETE FROM quote_items WHERE quote_id IN "
             "(SELECT id FROM quotes WHERE project_id IN "
             "(SELECT id FROM projects WHERE customer_id IN "
             "(SELECT id FROM customers WHERE phone='19900007777')))")
conn.execute("DELETE FROM quotes WHERE project_id IN "
             "(SELECT id FROM projects WHERE customer_id IN "
             "(SELECT id FROM customers WHERE phone='19900007777'))")
conn.execute("DELETE FROM projects WHERE customer_id IN "
             "(SELECT id FROM customers WHERE phone='19900007777')")
conn.execute("DELETE FROM customers WHERE phone='19900007777'")
conn.execute("INSERT INTO customers(phone,name,estate,area,budget_range,status,channel,tags) "
             "VALUES('19900007777','报价测试','保利和光尘樾',189,'80-100万','派单','转介绍','测试')")
cid = conn.execute("SELECT id FROM customers WHERE phone='19900007777'").fetchone()[0]
conn.commit()
conn.close()

r = post("/api/dispatch", {"user": "admin", "customer_id": cid, "designer": "黄旭"})
pid = r["id"]
check("派单建项目", bool(pid), f"r={r}")

# 1. 生成报价 A：模板明细 + 面积估算
r = post(f"/api/projects/{pid}/quote", {"user": "admin", "requirements": "全屋整装"})
qid = r.get("id")
check("报价生成 模板明细", r.get("items") == 325 and r.get("est_items", 0) > 0,
      f"items={r.get('items')} est={r.get('est_items')}")
check("报价总额非面积套算", r.get("total") != 189 * 3300.0 and r.get("total", 0) > 0,
      f"total={r.get('total')}")

# 2. 明细分组与总额勾稽
lst = get(f"/api/quotes/{qid}/items")
check("明细 325 条", lst.get("items_count") == 325, f"n={lst.get('items_count')}")
check("明细按分类分组", len(lst.get("groups", {})) >= 10, f"groups={len(lst.get('groups', {}))}")
conn = sqlite3.connect(DB)
db_sum = conn.execute("SELECT COALESCE(SUM(amount),0) FROM quote_items "
                      "WHERE quote_id=?", (qid,)).fetchone()[0]
m2 = conn.execute("SELECT COUNT(*) FROM quote_items WHERE quote_id=? AND "
                  "unit LIKE '%㎡%' AND qty=189", (qid,)).fetchone()[0]
conn.close()
check("总额=明细Σ勾稽", abs(db_sum - lst["total"]) < 0.01,
      f"db={db_sum} api={lst['total']}")
check("㎡项目按面积估算", m2 >= 10, f"m2={m2}")

# 3. 明细修正：改第一条 qty → 总额重算
first = None
for sec, items in lst["groups"].items():
    for it in items:
        if it["est"]:
            first = it
            break
    if first:
        break
r = post(f"/api/quotes/{qid}/items/{first['id']}", {"user": "admin", "qty": 99.0})
check("明细修正重算", r.get("new_total") == round(lst["total"] - first["amount"] + 99.0 * first["unit_price"], 2),
      f"new_total={r.get('new_total')} expect={round(lst['total'] - first['amount'] + 99.0 * first['unit_price'], 2)}")

# 3b. 重估接口：人工修正过的行不覆盖，其余按新面积重估
r = post(f"/api/quotes/{qid}/estimate", {"user": "admin", "qty": 200.0})
check("重估-修正行不覆盖", r.get("kept_manual", 0) >= 1 and
      r.get("re_estimated") == 325 - r.get("kept_manual", 0),
      f"kept={r.get('kept_manual')} re={r.get('re_estimated')}")
lst2 = get(f"/api/quotes/{qid}/items")
still_99 = any(it["id"] == first["id"] and abs(it["qty"] - 99.0) < 0.001
              for sec2 in lst2["groups"].values() for it in sec2)
check("重估后修正行保留99", still_99, "修正行被覆盖")
conn = sqlite3.connect(DB)
m2 = conn.execute("SELECT COUNT(*) FROM quote_items WHERE quote_id=? AND "
                  "unit LIKE '%㎡%' AND qty=200", (qid,)).fetchone()[0]
conn.close()
check("重估后㎡项目按200", m2 >= 10, f"m2={m2}")

# 4. 折扣 9.9 折（≥0.98）免审批
r = post(f"/api/quotes/{qid}/discount", {"user": "admin", "discount": 0.99})
check("9.9折免审批", r.get("status") == "已审批" and r.get("need_approval") is False, f"r={r}")

# 5. 报价 B：9.7 折转待审批
r = post(f"/api/projects/{pid}/quote", {"user": "admin"})
qid2 = r["id"]
r = post(f"/api/quotes/{qid2}/discount", {"user": "admin", "discount": 0.97})
check("9.7折转待审批", r.get("status") == "待审批" and r.get("approver") == "董事长", f"r={r}")

# 6. 非审批人审批被拒
r = post(f"/api/quotes/{qid2}/approve", {"user": "苏巍", "decision": "已审批"})
check("非审批人审批被拒", r.get("_http_error") == 403, f"r={r}")

# 7. 董事长审批
r = post(f"/api/quotes/{qid2}/approve", {"user": "周乾坤", "decision": "已审批"})
check("董事长审批通过", r.get("decision") == "已审批", f"r={r}")

# 8. 已审批后再提交折扣 → 400
r = post(f"/api/quotes/{qid2}/discount", {"user": "admin", "discount": 0.95})
check("已审批不可再提交", r.get("_http_error") == 400, f"r={r}")

# 9. 付款计划 60/35/5 勾稽（用报价 A）
r = get(f"/api/quotes/{qid}/payment-plan")
s = r.get("stages", [])
ratios = [x["ratio"] for x in s]
amounts = [x["amount"] for x in s]
check("付款计划 60/35/5", ratios == [0.6, 0.35, 0.05], f"ratios={ratios}")
check("付款计划金额勾稽", abs(sum(amounts) - r["total"]) < 0.01,
      f"sum={sum(amounts)} total={r['total']}")

# 10. 已签约项目不能再生成报价（先走合法链）
post(f"/api/projects/{pid}/status", {"user": "admin", "to": "设计"})
post(f"/api/projects/{pid}/status", {"user": "admin", "to": "报价"})
r = post(f"/api/projects/{pid}/status", {"user": "admin", "to": "签约"})
check("迁移到签约", r.get("to") == "签约", f"r={r}")
r2 = post(f"/api/projects/{pid}/quote", {"user": "admin"})
check("已签约不可再报价", r2.get("_http_error") == 400, f"r={r2}")

# 清理
conn = sqlite3.connect(DB)
conn.execute("DELETE FROM quote_items WHERE quote_id IN (SELECT id FROM quotes WHERE project_id=?)", (pid,))
conn.execute("DELETE FROM quotes WHERE project_id=?", (pid,))
conn.execute("DELETE FROM projects WHERE id=?", (pid,))
conn.execute("DELETE FROM customers WHERE id=?", (cid,))
conn.execute("DELETE FROM audit_log WHERE target LIKE 'quotes#%' OR target LIKE 'quote_items#%'")
conn.commit()
conn.close()

# 配置驱动断言：_est_qty 行为跟随 rules.quote_est（免服务调用）
import sys
sys.path.insert(0, r"H:\AgentProjects\HomeDesignGroup\src")
from routers.dispatch import _est_qty

est_cfg = {"area_units": ["㎡"], "area_coef": 1.0, "perimeter_units": ["m"],
           "perimeter_coef": 4.0, "unit_units": ["套"], "unit_default_qty": 1.0,
           "fallback_qty": 0.0, "section_coefs": {}}
check("配置-面积系数", _est_qty(189, "㎡", est_cfg) == (189.0, 1),
      f"got={_est_qty(189, '㎡', est_cfg)}")
check("配置-周长系数", _est_qty(189, "m", est_cfg)[0] == round((189 ** 0.5) * 4, 1),
      f"got={_est_qty(189, 'm', est_cfg)[0]}")
check("配置-单项默认", _est_qty(189, "套", est_cfg) == (1.0, 1))
check("配置-兜底0", _est_qty(189, "级", est_cfg) == (0.0, 0))
est_cfg2 = {**est_cfg, "section_coefs": {"客餐厅": 0.9}}
check("配置-分类覆盖系数",
      _est_qty(189, "㎡", est_cfg2, "一、客餐厅门厅过道")[0] == round(189 * 0.9, 1),
      f"got={_est_qty(189, '㎡', est_cfg2, '一、客餐厅门厅过道')[0]}")
check("配置-分类未命中回退", _est_qty(189, "㎡", est_cfg2, "二、卧室")[0] == 189.0)

print("\n" + ("全部通过" if not fails else f"{len(fails)} 项失败"))
sys.exit(1 if fails else 0)
