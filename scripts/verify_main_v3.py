# -*- coding: utf-8 -*-
"""verify_main_v3.py — 中控 main.py P3-P7 指令集成冒烟（编队 v3）"""
import os
import sys

sys.path.insert(0, r"H:\AgentProjects\HomeDesignGroup\src")

import main as M

M.register_all()  # import 不会执行 main()，需显式注册指令

# 灌入演示数据（幂等）：王女士保利和光尘樾189㎡，325条报价明细。
# API 返回 id 可能与落库漂移，直接以库内实际记录为准。
import subprocess
subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "seed_workbench_demo.py")],
               cwd=r"H:\AgentProjects\HomeDesignGroup", check=True, capture_output=True, text=True)
import sqlite3
_dbc = sqlite3.connect(r"H:\AgentProjects\HomeDesignGroup\db\壹城精工.db")
_cid = _dbc.execute("SELECT id FROM customers WHERE phone='19900005555'").fetchone()[0]
PID = str(_dbc.execute("SELECT id FROM projects WHERE customer_id=? ORDER BY id DESC LIMIT 1",
                       (_cid,)).fetchone()[0])
QID = str(_dbc.execute("SELECT id FROM quotes WHERE project_id=? ORDER BY id DESC LIMIT 1",
                       (int(PID),)).fetchone()[0])
_dbc.close()

PASS = 0
FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name} {extra}")


def route(text):
    return M.bus.route(text)


# 0) 编译与注册
check("main 指令注册（含 ceo/mat/soft/as）",
      all(k in M.bus._handlers for k in ("ceo", "mat", "soft", "as")))

# 1) 总经办
r = route("/ceo approvals")
check("CEO 审批汇总", "待审批报价" in r and "待处理售后" in r, r)
r = route("/ceo dashboard")
check("CEO 看板", "客户漏斗" in r and "累计收款" in r and "验收合格" in r, r)
r = route("/ceo audit")
check("CEO 审计追溯", "审计" in r or "#" in r, r)
r = route("/ceo coord 材料部与工程部确认主材进场时间")
check("CEO 协调留痕", "协调记录" in r, r)

# 2) 材料
r = route(f"/mat list4quote {QID}")
check("材料-主材清单(报价" + QID + ")", "主材清单" in r and "合计" in r, r)
r = route("/mat list")
check("材料-材料库检索", "(材料库无数据" in r or "¥" in r, r)

# 3) 软装
r = route(f"/soft add {PID} 家具 意式极简三人沙发 --spec 2.2m --qty 1 --price 12000")
check("软装-录入", "已录入" in r and "¥12,000" in r, r)
sid = r.split("#")[1].split(" ")[0]
r = route(f"/soft add {PID} 窗帘 电动梦幻帘 --spec 客厅 --qty 2 --price 3500")
check("软装-录入2", "已录入" in r, r)
r = route(f"/soft list {PID}")
check("软装-清单含小计合计", "【家具】" in r and "【窗帘】" in r and "合计" in r, r)
r = route(f"/soft up {sid} qty=2 note=含贵妃位")
check("软装-更新联动重算", "¥24,000" in r, r)
r = route("/soft rm " + sid)
check("软装-删除", "已删除" in r, r)

# 4) 售后
r = route(f"/as warranty {PID}")
check("售后-质保登记", "整体→" in r and "防水→" in r, r)
r = route(f"/as ticket {PID} 厨房水槽下水慢 业主反馈下水缓慢需检查")
check("售后-工单创建", "已创建" in r, r)
tid = r.split("#")[1].split(" ")[0]
r = route(f"/as list {PID}")
check("售后-列表", "质保登记" in r and "售后工单" in r, r)
r = route(f"/as status {tid} 处理中 已预约上门")
check("售后-工单状态", "→ 处理中" in r, r)
r = route("/as due")
check("售后-回访SOP", "提醒生成" in r, r)

print(f"\n{'-' * 30}\n{PASS} 通过 | {FAIL} 失败")
sys.exit(1 if FAIL else 0)
