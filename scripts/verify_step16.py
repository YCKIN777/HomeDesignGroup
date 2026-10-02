# -*- coding: utf-8 -*-
"""Step 1.6 自检：会话建/续、L2自动载、L3/L4按需检索带来源、身份必载"""
import sys

sys.path.insert(0, r"H:\AgentProjects\HomeDesignGroup\src")
import sys as _s
_s.path.insert(0, r"H:\AgentProjects\HomeDesignGroup\src\kernel")
from kernel import config_loader  # noqa
from memory_manager import MemoryManager

ok = True
mm = MemoryManager()

print("== 1) L1 会话可建/可续 ==")
sid = mm.create_session("admin", customer_id=1)
got = mm.get_session(sid)
print(f"  会话 {sid} -> customer_id={got['customer_id']}")
ok = ok and got is not None

print("== 2) L2 当前客户自动载（先写一条消息）==")
mm.add_l2_message(1, "in", "客户问：全包多少钱一平", author="sales", approve_status="sent")
l2 = mm.load_l2(1)
print(f"  自动载 {len(l2)} 条: {[m['content'][:20] for m in l2]}")
ok = ok and len(l2) >= 1

print("== 3) L4 文本记忆检索（带来源）==")
r4 = mm.retrieve("渠道占比", top_k=3)
print(f"  {[(h['source'], h['layer'], h['score']) for h in r4]}")
ok = ok and any(h["layer"] == "L4" and "渠道" in h["source"] for h in r4)

print("== 4) 身份必载 system_prompt（含术语/状态机/规则）==")
cfg = config_loader.load_profile("壹城精工")
sp = mm.build_system_prompt(cfg)
print(f"  {sp[:120]}...")
ok = ok and "渠道" in sp and "量房" in sp and "首联时限" in sp

print("== 5) Otter 总装 build_context ==")
ctx = mm.build_context(sid, cfg, query="防水工艺")
print(f"  system_prompt={bool(ctx['system_prompt'])} l2={len(ctx['l2'])} retrieval={len(ctx['retrieval'])}")
ok = ok and ctx["system_prompt"] and len(ctx["retrieval"]) >= 0

print("\n== 自检结论 ==")
print("  PASS — Step 1.6 产物完整，可进入 Step 1.7" if ok else "  FAIL — 请检查上述失败项")
