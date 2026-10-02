# -*- coding: utf-8 -*-
"""run_regression.py — 全套件回归（P12 收口）：批量跑核心+契约线验证，汇总结果"""
import os
import subprocess
import sys

ROOT = r"H:\AgentProjects\HomeDesignGroup"
PY = sys.executable

# (脚本名, 预期通过数, 说明)
CORE = [
    ("verify_main.py", 22, "P2 聚合类+中控"),
    ("verify_main_v3.py", 17, "九Agent集成中控"),
    ("verify_agents_v3.py", 20, "九Agent行为"),
    ("verify_payments.py", 16, "6.1 收款闭环"),
    ("verify_team_web.py", 19, "P8 九部门Web"),
    ("verify_p9_closure.py", 14, "P9 全链路闭环"),
    ("verify_phase2.py", 0, "阶段2 获客"),
    ("verify_phase34.py", 0, "阶段3-4 邀约沉淀"),
    ("verify_carrier.py", 0, "承接全链路"),
    ("verify_gates.py", 0, "6.4 开工闸门"),
    ("verify_quotes.py", 0, "报价模板"),
    ("verify_engineering.py", 0, "工程日报验收"),
    ("verify_project_status.py", 0, "状态机"),
    ("verify_plans.py", 0, "设计方案"),
]
CONTRACT = [
    ("verify_providers.py", 0, "Provider抽象"),
    ("verify_core_tables.py", 0, "契约三表"),
    ("verify_sentinel.py", 0, "Sentinel闸门"),
    ("verify_planner.py", 0, "Planner"),
    ("verify_data_loaded.py", 0, "数据灌装"),
    ("verify_memory_search.py", 0, "记忆检索"),
    ("verify_llm_enhance.py", 0, "LLM增强"),
]

results = []


def run_one(name, expect, group):
    path = os.path.join(ROOT, "scripts", name)
    try:
        r = subprocess.run([PY, "-u", path], cwd=ROOT, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=300)
        out = (r.stdout or "") + (r.stderr or "")
        tail = [l for l in out.splitlines() if ("通过" in l and "失败" in l) or "=====" in l or "PASS" in l]
        tail_txt = " | ".join(tail[-2:])[:220]
        ok = r.returncode == 0
        results.append((group, name, ok, r.returncode, tail_txt))
        print(f"[{'PASS' if ok else 'FAIL'}] [{group}] {name} exit={r.returncode} {tail_txt}")
    except Exception as e:
        results.append((group, name, False, -1, repr(e)[:120]))
        print(f"[FAIL] [{group}] {name} 异常 {e}")


print("=== 核心回归组 ===")
for name, expect, desc in CORE:
    run_one(name, expect, "核心")

print("\n=== 契约线回归组 ===")
for name, expect, desc in CONTRACT:
    run_one(name, expect, "契约")

p = sum(1 for r in results if r[2])
f = len(results) - p
print(f"\n===== 回归汇总: {p}/{len(results)} 通过 | {f} 失败 =====")
for r in results:
    if not r[2]:
        print(f"  FAILED: [{r[0]}] {r[1]} exit={r[3]} {r[4]}")
sys.exit(1 if f else 0)
