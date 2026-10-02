# -*- coding: utf-8 -*-
"""Step 1.4 自检：六 Agent 装载、协议字段、handle 占位"""
import sys

sys.path.insert(0, r"H:\AgentProjects\HomeDesignGroup\src")
from agents import load_agents

ok = True

print("== 1) 装载全部 Agent ==")
agents = load_agents()
names = list(agents.keys())
print(f"  OK  装载 {len(agents)} 个: {names}")
ok = ok and len(agents) == 6
ok = ok and len(names) == len(set(names))

print("== 2) 协议字段（name/role/capabilities/handle）==")
for name, inst in agents.items():
    has_proto = inst.name and inst.role and isinstance(inst.capabilities, list) and callable(inst.handle)
    print(f"  {'OK ' if has_proto else 'MISS'} {name}: {inst.role} | 能力 {len(inst.capabilities)} 项")
    ok = ok and has_proto

print("== 3) handle 占位返回（Step 自检协议：未实现→标记 todo）==")
r = agents["lead"].handle({}, "客户想咨询")
print(f"  {r}")
ok = ok and r.get("implemented") is False and r.get("todo")

print("== 4) 中控可装载（名称->实例映射）==")
for name in ["lead", "dispatch", "scoring", "sop", "invite", "kb"]:
    ok = ok and name in agents

print("\n== 自检结论 ==")
print("  PASS — Step 1.4 产物完整，可进入 Step 1.5" if ok else "  FAIL — 请检查上述失败项")
