# -*- coding: utf-8 -*-
"""Step 1.5 自检：工厂装配、mock 可用、未配置 key 清晰报错、非法 provider"""
import os
import sys

sys.path.insert(0, r"H:\AgentProjects\HomeDesignGroup\src")
import llm

ok = True

print("== 1) 默认工厂装配（provider=mock）==")
client = llm.get_llm()
print(f"  OK  provider={client.provider} ({type(client).__name__})")
ok = ok and isinstance(client, llm.MockLLM)

print("== 2) chat 可用 ==")
r = client.chat([{"role": "user", "content": "客户想了解全包套餐"}])
print(f"  {r}")
ok = ok and r.startswith("[mock]")

print("== 3) summarize 可用 ==")
s = client.summarize("客户岳麓区 189 平，预算 60 万，意向现代风，希望三个月内开工")
print(f"  {s}")
ok = ok and s.startswith("[mock]")

print("== 4) 强制 doubao 且无 key → 清晰报错 ==")
os.environ.pop("DOUBAO_API_KEY", None)
try:
    llm.get_llm(force="doubao").chat([{"role": "user", "content": "hi"}])
    ok = False
    print("  FAIL 未配置 key 竟然成功调用")
except llm.LLMError as e:
    print(f"  OK   {e}")

print("== 5) 非法 provider → 报错 ==")
try:
    llm.get_llm(force="nonsense")
    ok = False
    print("  FAIL 非法 provider 未拦截")
except llm.LLMError as e:
    print(f"  OK   {e}")

print("\n== 自检结论 ==")
print("  PASS — Step 1.5 产物完整，可进入 Step 1.6" if ok else "  FAIL — 请检查上述失败项")
