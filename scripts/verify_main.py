# -*- coding: utf-8 -*-
"""verify_main.py — main.py 完整重写版自检（v2：模板报价 + 收款 + 开工闸门）

非交互验证：编译 + register_all 后经 bus.route 走通承接指令链路。
"""
import py_compile
import sqlite3
import sys

sys.path.insert(0, r"H:\AgentProjects\HomeDesignGroup\src")

fails = []


def check(name, cond, detail=""):
    if not cond:
        fails.append(name)
        print(f"[FAIL] {name}: {detail}")
    else:
        print(f"[PASS] {name}")


# 1. 编译
py_compile.compile(r"H:\AgentProjects\HomeDesignGroup\src\main.py", doraise=True)
check("main.py 编译通过", True)

# 2. 导入并注册
import main as m  # noqa: E402
m.register_all()
check("指令注册", all(m.bus.route("/help").count(x) for x in ("/plan", "/quote", "/pay", "/proj", "/detail")))

# 3. 承接链路（造测试数据）
DB = r"H:\AgentProjects\HomeDesignGroup\db\壹城精工.db"
conn = sqlite3.connect(DB)
# 清理残留
for t in ("payments", "site_reports", "inspections", "quotes", "design_plans"):
    conn.execute(f"DELETE FROM {t} WHERE quote_id IN (SELECT id FROM quotes WHERE project_id IN "
                 f"(SELECT id FROM projects WHERE customer_id IN "
                 f"(SELECT id FROM customers WHERE phone='19900004444')))"
                 if t == "payments" else
                 f"DELETE FROM {t} WHERE project_id IN "
                 f"(SELECT id FROM projects WHERE customer_id IN "
                 f"(SELECT id FROM customers WHERE phone='19900004444'))")
conn.execute("DELETE FROM projects WHERE customer_id IN "
             "(SELECT id FROM customers WHERE phone='19900004444')")
conn.execute("DELETE FROM customers WHERE phone='19900004444'")
conn.execute("INSERT INTO customers(phone,name,estate,area,status,channel,tags) "
             "VALUES('19900004444','中控测试','梅溪湖',160,'派单','抖音','测试')")
cid = conn.execute("SELECT id FROM customers WHERE phone='19900004444'").fetchone()[0]
conn.commit()
conn.close()

r = m.bus.route(f"/dispatch {cid} 黄旭")
pid = int(r.split("#")[1].split(" ")[0])
check("派单", pid > 0, r)

r = m.bus.route(f"/plan add {pid} 现代简约 LDK一体")
check("建方案", "v1" in r and "初稿" in r, r)
r = m.bus.route(f"/plan list {pid}")
check("方案列表", "v1" in r, r)
plid = int(r.split("#")[1].split(" ")[0])
r = m.bus.route(f"/plan status {plid} 已定稿")
check("方案流转到已定稿", "已定稿" in r, r)

# ---- 报价：模板驱动（不再面积套算）----
r = m.bus.route(f"/quote gen {pid} 全屋整装")
qid = int(r.split("#")[1].split(" ")[0])
check("模板驱动报价", "项明细" in r and "估算待复核" in r, r)
r = m.bus.route(f"/quote items {qid}")
check("报价明细分组", "项" in r and "合计" in r, r)

# ---- 项目状态迁移链（到签约）----
for to in ("量房", "设计", "报价", "签约"):
    r = m.bus.route(f"/proj {pid} {to}")
    check(f"项目迁移到 {to}", to in r, r)

# ---- 开工闸门：未收款拦截 ----
try:
    m.bus.route(f"/proj {pid} 开工")
    check("未收款开工被拦截", False, "未被拦截")
except Exception as e:
    check("未收款开工被拦截", "开工闸门" in str(e), str(e)[:80])

# ---- 收款 + 进度 ----
q = conn = None
with sqlite3.connect(DB) as conn:
    total = conn.execute("SELECT total FROM quotes WHERE id=?", (qid,)).fetchone()[0]
due = round(total * 0.6, 2)
r = m.bus.route(f"/pay add {qid} 签约 {due}")
check("收款登记", "已登记" in r and "签约" in r, r)
r = m.bus.route(f"/pay plan {qid}")
check("收款进度", "应缴" in r and "已收" in r and "待收" in r, r)

# ---- 收足后开工放行 ----
r = m.bus.route(f"/proj {pid} 开工")
check("收足后开工放行", "开工" in r and "→" in r, r)

# ---- 报价折扣/审批/付款计划（沿用）----
r = m.bus.route(f"/quote discount {qid} 0.97")
check("折扣转待审批", "待审批" in r and "董事长" in r, r)
r = m.bus.route(f"/quote approve {qid} 已审批")
check("报价审批", "已审批" in r, r)
r = m.bus.route(f"/quote plan {qid}")
check("付款计划", "签约" in r and "35%" in r and "5%" in r, r)

r = m.bus.route(f"/report {pid} 水电 开槽完成")
check("工地日报", "已记录" in r, r)
r = m.bus.route(f"/inspect {pid} 水电 合格")
check("水电验收", "合格" in r, r)
r = m.bus.route(f"/inspect {pid} 吊顶 合格")
check("非法节点拦截", "须为" in r, r)

r = m.bus.route(f"/detail {pid}")
check("项目详情含收款", all(x in r for x in ("状态", "报价", "验收", "日报 1 条", "应缴", "已收")), r)

# 清理
conn = sqlite3.connect(DB)
for t in ("payments", "site_reports", "inspections", "quotes", "design_plans"):
    conn.execute(f"DELETE FROM {t} WHERE quote_id IN (SELECT id FROM quotes WHERE project_id=?)"
                 if t == "payments" else f"DELETE FROM {t} WHERE project_id=?", (pid,))
conn.execute("DELETE FROM projects WHERE id=?", (pid,))
conn.execute("DELETE FROM customers WHERE id=?", (cid,))
conn.commit()
conn.close()

print("\n" + ("全部通过" if not fails else f"{len(fails)} 项失败"))
sys.exit(1 if fails else 0)
