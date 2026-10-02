# -*- coding: utf-8 -*-
"""verify_planner.py — Step 5 自检：Planner + Tool dispatch 骨架"""
import sys

sys.path.insert(0, r"H:\AgentProjects\HomeDesignGroup\src")

from kernel.planner import Planner, ToolRegistry
from kernel.sentinel import DRAFT, READ, PendingHuman

fails = []


def check(name, cond, msg):
    if not cond:
        fails.append(name)
        print(f"[FAIL] {name}: {msg}")
    else:
        print(f"[PASS] {name}")


# ---- 注册六个骨架工具（Step 6 将替换为真实 Agent 实现） ----
registry = ToolRegistry()
registry.register("craft_search", lambda user, q="": {"q": q, "hits": ["降噪隔墙构造"]},
                  "查工艺知识库", READ)
registry.register("material_search", lambda user, cat="": {"cat": cat, "items": 2},
                  "拉建材参考价", READ)
registry.register("answer_draft", lambda user, **kw: {"draft_id": "A1", "status": "draft"},
                  "生成结构化答案草稿", DRAFT)
registry.register("owner_get", lambda user, oid=0: {"owner": f"owner#{oid}", "area": 189},
                  "查业主档案", READ)
registry.register("quote_draft", lambda user, **kw: {"draft_id": "Q1", "rows": 5,
                                                     "status": "draft"},
                  "生成报价单草稿", DRAFT)
registry.register("site_ocr", lambda user, img=b"": "[ocr] 木工吊顶施工中", "现场 OCR", READ)
registry.register("report_draft", lambda user, **kw: {"draft_id": "R1", "status": "pending"},
                  "生成工地日报草稿", DRAFT)

planner = Planner(registry)

# 1. 工具清单
lst = registry.list()
check("工具注册清单", len(lst) == 7 and all(t["sentinel_type"] in (READ, DRAFT) for t in lst),
      f"tools={lst}")

# 2. 报价单目标：3 步链
r = planner.run("报价单", user="admin", context={"owner_get": {"oid": 7}})
check("报价单 3 步执行", r["steps"] == 3 and [s["tool"] for s in r["chain"]] ==
      ["owner_get", "material_search", "quote_draft"], f"chain={[s['tool'] for s in r['chain']]}")

# 3. 工艺问答目标：3 步（答案草稿 DRAFT 放行）
r2 = planner.run("工艺问答", user="客服")
check("工艺问答 3 步执行", r2["steps"] == 3 and r2["chain"][-1]["result"].get("status") == "draft",
      f"chain={[s['tool'] for s in r2['chain']]}")

# 4. 工地日报目标：2 步（报告草稿 pending）
r3 = planner.run("工地日报", user="监理")
check("工地日报 2 步执行", r3["steps"] == 2 and r3["chain"][-1]["result"].get("status") == "pending",
      f"chain={[s['tool'] for s in r3['chain']]}")

# 5. Sentinel 联动：payment 类型工具被拒绝
registry.register("pay", lambda user, **kw: "扣款", "支付", "payment")
try:
    registry.call("pay", user="admin")
    check("payment 工具被 Sentinel 拒绝", False, "应抛 PermissionError")
except PermissionError:
    check("payment 工具被 Sentinel 拒绝", True, "")

# 6. 未知工具/未知目标防御
try:
    registry.call("no_such", user="admin")
    check("未知工具防御", False, "应抛 KeyError")
except KeyError:
    check("未知工具防御", True, "")
try:
    planner.plan("不存在的目标")
    check("未知目标防御", False, "应抛 KeyError")
except KeyError:
    check("未知目标防御", True, "")

print("\n" + ("全部通过" if not fails else f"{len(fails)} 项失败"))
sys.exit(1 if fails else 0)
