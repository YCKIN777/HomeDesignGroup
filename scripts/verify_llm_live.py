# -*- coding: utf-8 -*-
"""verify_llm_live.py — DeepSeek 真实 LLM 验证（一次性）"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))

from providers.factory import get_providers            # noqa: E402
from agents.craft_qa_agent import CraftQaAgent         # noqa: E402
from agents.quote_agent import QuoteAgent              # noqa: E402
from agents.site_report_agent import SiteReportAgent   # noqa: E402

p = get_providers()
print("providers:", p.summary())

# 1. LLM 直连
r = p.llm.chat([{"role": "user", "content": "用一句话回答：家装隐蔽工程指哪些？"}])
print("LLM 直连:", r.provider, "|", (r.text or "")[:60])

# 2. 工艺问答增强
qa = CraftQaAgent().answer("轻钢龙骨吊顶怎么做")
ls = qa.get("llm_summary", {})
print("\n工艺问答 llm_summary:", json.dumps(ls, ensure_ascii=False)[:200])

# 3. 报价单增强
import sqlite3
_db = sqlite3.connect(r"H:\AgentProjects\HomeDesignGroup\db\homeagent.db")
oid = _db.execute("SELECT id FROM owners WHERE wechat_id='demo_owner_001'").fetchone()[0]
_db.close()
qu = QuoteAgent("销售").build_quote(oid, "全屋硬装", "瓷砖")
print("报价单 llm_note:", json.dumps(qu.get("llm_note", {}), ensure_ascii=False)[:200])

# 4. 工地日报增强
rep = SiteReportAgent().build_report("保利和光尘樾-189", "木工吊顶龙骨完成")
print("日报 llm_note:", json.dumps(rep.get("llm_note", {}), ensure_ascii=False)[:200])

ok = all((x.get("enabled") for x in (qa.get("llm_summary", {}),
                                     qu.get("llm_note", {}), rep.get("llm_note", {}))))
print("\n" + ("真实 LLM 全部生效" if ok else "部分未生效（检查 key/网络/配额）"))
sys.exit(0 if ok else 1)
