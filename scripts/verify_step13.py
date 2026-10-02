# -*- coding: utf-8 -*-
"""Step 1.3 自检：指令路由、暂停/恢复、未知指令、帮助"""
import sys

sys.path.insert(0, r"H:\AgentProjects\HomeDesignGroup\src")
from kernel.bus import Bus

ok = True

print("== 1) 总线装载 + 默认指令注册 ==")
bus = Bus()
bus.register_defaults()
cmds = bus.commands()
print(f"  OK  指令集: {cmds}")
ok = ok and {"pause", "resume", "reject", "approve", "dispatch", "help"} <= set(cmds)

print("== 2) 路由 /pause /resume ==")
r1 = bus.route("/pause 3")
r2 = bus.route("/resume 3")
print(f"  {r1}")
print(f"  {r2}")
ok = ok and "暂停" in r1 and "恢复" in r2 and bus.is_paused(3) is False

print("== 3) 路由 /reject /approve /dispatch ==")
for cmd in ["/reject 11", "/approve 12", "/dispatch 3 王设计", "/dispatch 3"]:
    print(f"  {bus.route(cmd)}")
ok = ok and "驳回" in bus.route("/reject 11") and "派单" in bus.route("/dispatch 3")

print("== 4) 未知指令与空消息 ==")
r = bus.route("/nonsense xx")
print(f"  {r}")
ok = ok and "未知指令" in r
ok = ok and "空消息" in bus.route("   ")

print("== 5) 普通消息走默认通道 ==")
print(f"  {bus.route('你好，咨询装修')}")

print("== 6) 幂等：重复注册覆盖不报错 ==")
bus.register("pause", lambda ctx, *a: "[pause] 已覆盖")
print(f"  {bus.route('/pause 9')}")
ok = ok and "已覆盖" in bus.route("/pause 9")

print("\n== 自检结论 ==")
print("  PASS — Step 1.3 产物完整，可进入 Step 1.4" if ok else "  FAIL — 请检查上述失败项")
