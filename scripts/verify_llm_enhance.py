# -*- coding: utf-8 -*-
"""verify_llm_enhance.py — LLM 增强层验证

两项断言：
  1. mock 模式（未配 key）：三 Agent 输出含 llm_* 字段且 enabled=False（优雅降级，主链路照常）
  2. 若 .env 已配真实 key：同一次调用 enabled=True 且 text 非空（真实验证，可选）
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))

from providers.factory import get_providers            # noqa: E402
from agents.craft_qa_agent import CraftQaAgent         # noqa: E402
from agents.quote_agent import QuoteAgent              # noqa: E402
from agents.site_report_agent import SiteReportAgent   # noqa: E402

fails = []


def check(name, cond, detail=""):
    if not cond:
        fails.append(name)
        print(f"[FAIL] {name}: {detail}")
    else:
        print(f"[PASS] {name}")


p = get_providers()
print("providers:", p.summary())
print("=" * 50)

# 1. 工艺问答：命中真实条目 + LLM 增强字段
qa = CraftQaAgent().answer("轻钢龙骨吊顶怎么做", user="客服")
check("工艺问答命中", len(qa["craft"]) >= 1, f"craft={len(qa.get('craft', []))}")
check("工艺问答含 llm_summary", "llm_summary" in qa, f"keys={list(qa.keys())}")
if qa["llm_summary"]["enabled"]:
    check("工艺问答 llm 已启用且有文本", bool(qa["llm_summary"]["text"]),
          qa["llm_summary"].get("error", ""))
else:
    check("工艺问答 mock 降级 enabled=False", qa["llm_summary"]["enabled"] is False, "未配 key，符合预期")

# 2. 报价单：行项完整 + 合计 + LLM 字段（owner_id 动态取 demo_owner_001）
import sqlite3
_db = sqlite3.connect(r"H:\AgentProjects\HomeDesignGroup\db\homeagent.db")
_oid = _db.execute("SELECT id FROM owners WHERE wechat_id='demo_owner_001'").fetchone()[0]
_db.close()
qu = QuoteAgent("销售").build_quote(_oid, "全屋硬装", "瓷砖")
check("报价单行数", qu["row_count"] >= 1, f"rows={qu['row_count']}")
check("报价单列项", qu["columns"] == ["项目", "规格", "单位", "数量", "单价", "合价", "备注"],
      f"cols={qu['columns']}")
check("报价单合计=行合价之和", abs(qu["total"] - sum(r[5] for r in qu["rows"])) < 0.01,
      f"total={qu['total']}")
check("报价单含 llm_note", "llm_note" in qu, f"keys={list(qu.keys())}")
if qu["llm_note"]["enabled"]:
    check("报价单 llm 已启用且有文本", bool(qu["llm_note"]["text"]), qu["llm_note"].get("error", ""))
else:
    check("报价单 mock 降级 enabled=False", qu["llm_note"]["enabled"] is False, "未配 key，符合预期")

# 3. 工地日报：模板摘要 + LLM 字段 + pending 状态
rep = SiteReportAgent().build_report("保利和光尘樾-189", "木工吊顶龙骨完成")
check("日报 pending_human", rep["status"] == "pending_human", f"status={rep['status']}")
check("日报含 llm_note", "llm_note" in rep, f"keys={list(rep.keys())}")
if rep["llm_note"]["enabled"]:
    check("日报 llm 已启用且有文本", bool(rep["llm_note"]["text"]), rep["llm_note"].get("error", ""))
else:
    check("日报 mock 降级 enabled=False", rep["llm_note"]["enabled"] is False, "未配 key，符合预期")

# 4. 语义缺失（工艺无命中）：跳过 LLM、不报错
qa2 = CraftQaAgent().answer("完全不存在的工艺XYZ", user="客服")
check("无命中时不报错", "llm_summary" in qa2 and qa2["llm_summary"]["enabled"] is False,
      f"llm={qa2.get('llm_summary')}")

print("\n" + ("全部通过" if not fails else f"{len(fails)} 项失败"))
sys.exit(1 if fails else 0)
