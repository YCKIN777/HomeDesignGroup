# -*- coding: utf-8 -*-
"""Step 1.2 自检：有效配置加载通过 + 坏配置当场报错"""
import importlib.util
import os
import sys
import tempfile

sys.path.insert(0, r"H:\AgentProjects\HomeDesignGroup\src")
import kernel.config_loader as cl

ok = True

print("== 1) 有效配置包加载 ==")
try:
    cfg = cl.load_profile("壹城精工")
    print(f"  OK   terms={len(cfg['terms'])} rules={list(cfg['rules'].keys())} "
          f"workflow={len(cfg['workflow']['backbone'])} locked={cfg['workflow']['locked_nodes']}")
except cl.ConfigError as e:
    ok = False
    print(f"  FAIL {e}")

print("== 2) 坏配置当场报错（locked 节点不在 backbone）==")
bad_dir = os.path.join(cl.PROFILE_DIR, "_test_bad")
os.makedirs(bad_dir, exist_ok=True)
with open(os.path.join(bad_dir, "workflow.yaml"), "w", encoding="utf-8") as f:
    f.write("workflow:\n  backbone: [量房, 设计]\n  locked_nodes: [水电]\n  transitions: []\n")
try:
    cl.load_workflow("_test_bad")
    ok = False
    print("  FAIL 坏配置未被拦截（应报错）")
except cl.ConfigError as e:
    print(f"  OK   已拦截: {e}")

print("== 3) 坏配置当场报错（术语缺 definition）==")
with open(os.path.join(bad_dir, "terms.yaml"), "w", encoding="utf-8") as f:
    f.write("terms:\n  - {id: 'x', label: '测试', parent: 'root'}\n")
try:
    cl.load_terms("_test_bad")
    ok = False
    print("  FAIL 缺 definition 未被拦截")
except cl.ConfigError as e:
    print(f"  OK   已拦截: {e}")

# 清理测试目录
import shutil
shutil.rmtree(bad_dir, ignore_errors=True)

print("\n== 自检结论 ==")
print("  PASS — Step 1.2 产物完整，可进入 Step 1.3" if ok else "  FAIL — 请检查上述 FAIL 项")
