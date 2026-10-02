# -*- coding: utf-8 -*-
"""check_materialize.py — Step 4.12 自检：沉淀入内核→物化 md + CHANGELOG 追加"""
import io
import json
import os
import sqlite3
import sys
import urllib.request

ROOT = r"H:\AgentProjects\HomeDesignGroup"
URL = "http://127.0.0.1:8000"
TEST_TITLE = "4.12 自检沉淀-物化验证"

fails = []


def check(name, cond, msg):
    if not cond:
        fails.append(name)
        print(f"[FAIL] {name}: {msg}")
    else:
        print(f"[PASS] {name}")


def http(method, path, payload=None, user="admin"):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        URL + path, data=data, method=method,
        headers={"Content-Type": "application/json", "X-Agent-User": user})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


# 0. 服务健康
try:
    with urllib.request.urlopen(URL + "/health", timeout=10) as r:
        json.loads(r.read().decode("utf-8"))
    check("服务健康", True, "")
except Exception as e:
    check("服务健康", False, f"{e}；需先重启服务加载新代码")
    raise SystemExit(1)

# 1. 提交沉淀 → 评审入内核
sed = http("POST", "/api/sedimentation", {
    "user": "admin", "category": "最佳实践", "title": TEST_TITLE,
    "description": "验证沉淀物化钩子", "condition": "前端线索处理",
    "evidence": "决策记录#0（匿名）", "has_instance": True,
    "reproducible": True, "anonymized": True, "respects_core": True})
sid = sed.get("id")
check("沉淀提交", sed.get("ok") is True and sid, f"实际={sed}")

rev = http("POST", f"/api/sedimentation/{sid}/review", {"user": "admin", "to": "已入内核"})
check("评审入内核返回物化路径", rev.get("status") == "已入内核" and rev.get("materialized"),
      f"实际={rev}")

# 2. 物化 md 存在且内容正确
md_rel = rev["materialized"]
md_path = os.path.join(ROOT, md_rel.replace("/", os.sep))
check("物化 md 存在", os.path.exists(md_path), f"{md_path}")
text = io.open(md_path, "r", encoding="utf-8").read()
check("物化 md 含标题", TEST_TITLE in text, "缺标题")
check("物化 md 含 frontmatter", text.startswith("---") and "category:" in text, "缺 frontmatter")
check("物化 md 含条件/描述/证据", all(k in text for k in ("适用条件", "描述", "证据")), "缺字段")

# 3. CHANGELOG 追加
cl = os.path.join(ROOT, "CHANGELOG.md")
cl_text = io.open(cl, "r", encoding="utf-8").read()
check("CHANGELOG 追加条目", f"沉淀入内核 #{sid}" in cl_text, "缺沉淀条目行")

# 4. 清理（物化 md + CHANGELOG 行 + 库记录 + 审计）
os.remove(md_path)
lines = io.open(cl, "r", encoding="utf-8").read().splitlines()
io.open(cl, "w", encoding="utf-8", newline="\n").write("\n".join(
    l for l in lines if f"沉淀入内核 #{sid}" not in l) + "\n")
conn = sqlite3.connect(os.path.join(ROOT, "db", "壹城精工.db"))
conn.execute("DELETE FROM sedimentation_items WHERE title=?", (TEST_TITLE,))
conn.execute("DELETE FROM audit_log WHERE target=?", (f"sedimentation_items#{sid}",))
conn.commit()
conn.close()
print("清理完成")

print("\n" + ("全部通过" if not fails else f"{len(fails)} 项失败"))
raise SystemExit(1 if fails else 0)
