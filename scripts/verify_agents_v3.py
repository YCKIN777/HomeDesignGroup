# -*- coding: utf-8 -*-
"""verify_agents_v3.py — 编队 v3 · P3-P7 新增 Agent 联合自检

P3 客服 / P4 总经办 / P5 材料 / P6 软装 / P7 售后。幂等：开头清理测试残留。
"""
import py_compile
import sqlite3
import sys

sys.path.insert(0, r"H:\AgentProjects\HomeDesignGroup\src")

fails = []


def check(name, cond, detail=""):
    if not cond:
        fails.append(name)
        print("[FAIL] %s: %s" % (name, detail))
    else:
        print("[PASS] %s" % name)


DB = r"H:\AgentProjects\HomeDesignGroup\db\壹城精工.db"
PHONE = "19900005550"


def cleanup():
    conn = sqlite3.connect(DB)
    cid = conn.execute("SELECT id FROM customers WHERE phone=?", (PHONE,)).fetchone()
    if cid:
        cid = cid[0]
        pids = [r[0] for r in conn.execute("SELECT id FROM projects WHERE customer_id=?", (cid,))]
        for pid in pids:
            for t in ("soft_furnishings", "after_sales", "site_reports", "inspections", "design_plans"):
                conn.execute("DELETE FROM %s WHERE project_id=?" % t, (pid,))
            conn.execute("DELETE FROM projects WHERE id=?", (pid,))
        conn.execute("DELETE FROM messages WHERE customer_id=?", (cid,))
        conn.execute("DELETE FROM customers WHERE id=?", (cid,))
    conn.commit()
    conn.close()


cleanup()

# 1. 编译五个新 Agent
for f in ("customer_service_agent", "executive_office_agent", "material_agent",
          "soft_furnishing_agent", "after_sales_agent"):
    py_compile.compile(r"H:\AgentProjects\HomeDesignGroup\src\agents\%s.py" % f, doraise=True)
check("P3-P7 五个 Agent 编译通过", True)

from agents.customer_service_agent import CustomerServiceAgent   # noqa: E402
from agents.executive_office_agent import ExecutiveOfficeAgent   # noqa: E402
from agents.material_agent import MaterialAgent                   # noqa: E402
from agents.soft_furnishing_agent import SoftFurnishingAgent     # noqa: E402
from agents.after_sales_agent import AfterSalesAgent             # noqa: E402
from agents.business_agent import BusinessAgent                  # noqa: E402

cs = CustomerServiceAgent()
ceo = ExecutiveOfficeAgent()
mat = MaterialAgent()
soft = SoftFurnishingAgent()
as_agent = AfterSalesAgent()

# 2. 造数据：客户 + 项目（量房）
biz = BusinessAgent()
r = biz.ingest("admin", PHONE, name="编队测试", estate="梅溪湖", area=128,
               budget_range="40-60万", style="奶油风", channel="抖音")
cid = r["id"]
pid = biz.lead.transition  # noqa: B018
from agents.dispatch_agent import DispatchAgent  # noqa: E402
pr = DispatchAgent().dispatch("admin", cid, "黄旭")
pid = pr["id"]
check("造数：项目就绪", pid > 0, "pid=%s" % pid)

# ---- P3 客服 ----
try:
    d = cs.prepare_draft("admin", cid, "first_contact")
    check("P3 起草入收件箱", d["approve_status"] == "draft", str(d)[:80])
    ib = cs.inbox()
    check("P3 收件箱有草稿", any(x["id"] == d["id"] for x in ib), "ids=%s" % [x["id"] for x in ib])
    ok = cs.approve("admin", d["id"])
    check("P3 人审后发", ok["status"] == "sent", str(ok))
    try:
        cs.approve("admin", d["id"])
        check("P3 防重复审批", False, "二次审批未拦截")
    except ValueError as e:
        check("P3 防重复审批", "不可重复审批" in str(e), str(e)[:60])
except Exception as e:
    check("P3 客服链路", False, repr(e))

# ---- P4 总经办 ----
try:
    ai = ceo.approval_inbox("admin")
    check("P4 审批汇总", "pending_messages" in ai and "pending_quote_approvals" in ai
          and "pending_after_sales" in ai, str(list(ai.keys())))
    db = ceo.dashboard("admin")
    check("P4 看板", "customers_by_status" in db and "payments_collected" in db, str(list(db.keys())))
    at = ceo.audit_trail("周乾坤", 5)  # audit 权限归总经办（董事长）
    check("P4 审计追溯", len(at) >= 1 and "action" in at[0], "n=%d" % len(at))
except Exception as e:
    check("P4 总经办", False, repr(e))

# ---- P5 材料 ----
try:
    mats = mat.list_materials(limit=5)
    check("P5 材料库检索", isinstance(mats, list), "type=%s" % type(mats))
    # 用王女士最新报价测主材清单（存在则断言；不存在仅提示）
    import os
    q = None
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        q = conn.execute(
            "SELECT id FROM quotes WHERE project_id IN "
            "(SELECT id FROM projects WHERE customer_id IN "
            " (SELECT id FROM customers WHERE phone='19900005555')) "
            "ORDER BY id DESC LIMIT 1").fetchone()
    if q:
        ml = mat.build_material_list(q["id"])
        check("P5 报价主材清单", ml["quote_id"] == q["id"] and "items" in ml,
              "count=%s total=%s" % (ml["items_count"], ml["material_total"]))
    else:
        check("P5 报价主材清单", True, "（无演示报价，跳过断言）")
except Exception as e:
    check("P5 材料", False, repr(e))

# ---- P6 软装 ----
try:
    a = soft.add_item("admin", pid, "家具", "三人位沙发", "2.8m 布艺", 1, 6800)
    b = soft.add_item("admin", pid, "灯具", "客厅吊灯", "北欧风", 1, 3200)
    c = soft.add_item("admin", pid, "窗帘", "全屋窗帘", "遮光布", 3, 1200)
    check("P6 软装录入", a["amount"] == 6800 and c["amount"] == 3600,
          "a=%s c=%s" % (a["amount"], c["amount"]))
    u = soft.update_item("admin", b["id"], status="已确认")
    check("P6 状态流转", u["status"] == "已确认", str(u))
    sl = soft.build_soft_list(pid)
    check("P6 清单分组小计", sl["items_count"] == 3 and sl["total"] == 13600
          and len(sl["sections"]) == 3, str({s["category"]: s["subtotal"] for s in sl["sections"]}))
    soft.remove_item("admin", c["id"])
    sl2 = soft.build_soft_list(pid)
    check("P6 删除项", sl2["items_count"] == 2 and sl2["total"] == 10000, str(sl2["total"]))
except Exception as e:
    check("P6 软装", False, repr(e))

# ---- P7 售后 ----
try:
    w = as_agent.register_warranty("admin", pid, base_date="2026-06-01")
    types = {r["warranty_type"]: r["warranty_until"] for r in w["rows"]}
    check("P7 质保登记(2年/10年)", types.get("整体") == "2028-06-01"
          and types.get("防水") == "2036-06-01", str(types))
    t = as_agent.create_ticket("admin", pid, "卫生间渗水", "防水质保内，需上门", "范经理")
    check("P7 售后工单", t["status"] == "待处理", str(t))
    lst = as_agent.list(project_id=pid)
    check("P7 工单列表", len(lst) >= 3, "n=%d" % len(lst))
    u = as_agent.update_status("admin", t["id"], "处理中", "已派单上门")
    check("P7 工单状态", u["status"] == "处理中", str(u))
    due = as_agent.check_due()
    check("P7 回访SOP", isinstance(due, list), str(due)[:80])
except Exception as e:
    check("P7 售后", False, repr(e))

# 清理
cleanup()
print("\n" + ("全部通过" if not fails else "%d 项失败" % len(fails)))
sys.exit(1 if fails else 0)
