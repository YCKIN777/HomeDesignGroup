# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"H:\AgentProjects\HomeDesignGroup\src")
from agents.kb_agent import KbAgent
kb = KbAgent()
hits = kb.search("120平房子全包大概要多少钱？你们报价怎么算的？", top_k=3)
print("命中数:", len(hits))
for h in hits:
    print(f"- [{h['title']}] score={h['score']}  {h['snippet']}")
print("---")
hits2 = kb.search("水电验收标准 防水 闭水试验", top_k=3)
print("工艺检索命中数:", len(hits2))
for h in hits2:
    print(f"- [{h['title']}] score={h['score']}  {h['snippet']}")
