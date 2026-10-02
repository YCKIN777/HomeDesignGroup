# -*- coding: utf-8 -*-
"""check_decisions.py — Step 4.10 自检：业务钩子自动捕获 + API 查询/回填 + 匿名化"""
import json
import os
import sqlite3
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

ROOT = r"H:\AgentProjects\HomeDesignGroup"
DB_PATH = os.path.join(ROOT, "db", "壹城精工.db")
URL = "http://127.0.0.1:8000"
TEST_USER = "渠道:自检-4.10"
TEST_PHONE = "13800000010"

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
    check("服务健康", False, f"{e}")
    print("\n先重启服务再跑本脚本")
    raise SystemExit(1)

# 1. 建测试线索 → 评分 → 迁移 → 邀约 → 派单（真实业务钩子路径）
created = http("POST", "/api/leads", {
    "phone": TEST_PHONE, "name": "自检4.10客户", "estate": "自检楼盘",
    "channel": "MCP", "user": TEST_USER})
cid = created["id"]
check("测试线索创建", cid > 0, f"id={cid}")

sc = http("POST", f"/api/leads/{cid}/score", {"user": TEST_USER})
check("评分触发捕获", sc.get("score") is not None, f"score={sc}")

tr = http("POST", f"/api/leads/{cid}/status", {"user": TEST_USER, "to": "跟进"})
check("迁移触发捕获", tr.get("to") == "跟进", f"tr={tr}")

inv = http("POST", f"/api/leads/{cid}/invite", {"user": TEST_USER, "when": "本周末"})
check("邀约触发捕获", inv.get("id", 0) > 0, f"inv={inv}")

dp = http("POST", "/api/dispatch", {"user": TEST_USER, "customer_id": cid, "designer": "苏巍"})
check("派单触发捕获", dp.get("dup") is False and dp.get("id", 0) > 0, f"dp={dp}")

# 2. 决策表落库核对（kind 覆盖 + context 匿名）
conn = sqlite3.connect(DB_PATH)
rows = conn.execute(
    "SELECT kind, user, context FROM decisions WHERE customer_id=? ORDER BY id", (cid,)).fetchall()
kinds = [r[0] for r in rows]
check("5 种决策已捕获", kinds == ["score", "transition", "invite", "dispatch"],
      f"实际={kinds}")
conn.close()
ctx_all = "".join(r[2] for r in rows)
check("context 无手机号/姓名", TEST_PHONE not in ctx_all and "自检4.10客户" not in ctx_all,
      "决策 context 泄露隐私")

# 3. API 查询
lst = http("GET", "/api/decisions?kind=score&customer_id=" + str(cid))
check("API 按 kind 过滤", lst["items"] and all(i["kind"] == "score" for i in lst["items"]),
      f"实际={lst['total']}")

# 4. 结果回填
first = lst["items"][0]["id"]
rb = http("POST", f"/api/decisions/{first}/outcome", {"user": "admin", "outcome": "邀约到店"})
check("结果回填", rb.get("outcome") == "邀约到店", f"rb={rb}")

# 5. 沉淀证据引用（匿名 evidence 通路）
sed = http("POST", "/api/sedimentation", {
    "user": "admin", "category": "最佳实践", "title": "4.10 自检沉淀",
    "description": "决策捕获验证", "evidence": f"决策记录#{first}（匿名）"})
check("沉淀可引用决策记录", sed.get("ok") is True and sed.get("id", 0) > 0, f"sed={sed}")

# 6. 清理全部测试数据
conn = sqlite3.connect(DB_PATH)
conn.execute("DELETE FROM decisions WHERE customer_id=?", (cid,))
conn.execute("DELETE FROM projects WHERE customer_id=?", (cid,))
conn.execute("DELETE FROM followups WHERE customer_id=?", (cid,))
conn.execute("DELETE FROM messages WHERE customer_id=?", (cid,))
conn.execute("DELETE FROM customers WHERE id=?", (cid,))
conn.execute("DELETE FROM sedimentation_items WHERE title='4.10 自检沉淀'")
conn.execute("DELETE FROM audit_log WHERE user=?", (TEST_USER,))
conn.commit()
conn.close()

print("\n" + ("全部通过" if not fails else f"{len(fails)} 项失败"))
raise SystemExit(1 if fails else 0)
