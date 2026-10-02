# -*- coding: utf-8 -*-
"""check_mcp.py — Step 4.8 自检：MCP 握手/工具清单/调用分发/权限拦截"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mcp_server import handle_mcp

ROOT = r"H:\AgentProjects\HomeDesignGroup"
DB_PATH = os.path.join(ROOT, "db", "壹城精工.db")
TEST_USER = "渠道:自检-4.8"
TEST_PHONE = "13800000048"

fails = []


def check(name, cond, msg):
    if not cond:
        fails.append(f"[FAIL] {name}: {msg}")
        print(f"[FAIL] {name}: {msg}")
    else:
        print(f"[PASS] {name}")


def rpc(method, params=None, user=""):
    body = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params:
        body["params"] = params
    return handle_mcp(body, header_user=user)


# 1. 握手
init = rpc("initialize", {"protocolVersion": "2025-03-26"}, "admin")
check("initialize 握手", init.get("result", {}).get("serverInfo", {}).get("name") == "壹城精工-MCP",
      f"实际={init}")

# 2. 工具清单
lst = rpc("tools/list", {}, "admin")
tools = lst.get("result", {}).get("tools", [])
check("tools/list 返回10个工具", len(tools) == 10, f"实际={len(tools)}")
names = [t["name"] for t in tools]
check("工具含 kb_search/stats_overview", {"kb_search", "stats_overview", "leads_create",
      "action_help", "inbox_draft"} <= set(names), f"实际={names}")
bad = [t["name"] for t in tools if not t.get("description") or not t.get("inputSchema")]
check("工具描述/schema 完整", not bad, f"缺字段: {bad}")

# 3. 读工具调用
kb = rpc("tools/call", {"name": "kb_search", "arguments": {"query": "报价", "top_k": 3}}, "admin")
res = kb.get("result", {}).get("content", [{}])[0].get("text", "")
check("kb_search 有结果", kb.get("result", {}).get("isError") is False and '"total"' in res,
      f"实际={kb}")
stats = rpc("tools/call", {"name": "stats_overview", "arguments": {}}, "admin")
check("stats_overview 返回", '"customers_total"' in stats.get("result", {}).get("content", [{}])[0].get("text", ""),
      f"实际={stats}")

# 4. 写工具：内部账号创建线索（测后清理）
created = rpc("tools/call", {"name": "leads_create", "arguments": {
    "phone": TEST_PHONE, "name": "自检4.8客户", "estate": "自检楼盘",
    "channel": "MCP", "source": "check_mcp.py"}}, TEST_USER)
txt = created.get("result", {}).get("content", [{}])[0].get("text", "")
data = json.loads(txt)
check("leads_create 创建成功", created.get("result", {}).get("isError") is False
      and data.get("id"), f"实际={txt}")
cid = data.get("id")

# 5. 权限拦截：客服无 lead.write 之外的写权限 → 用客服账号调 leads_create 应被拦
conn = sqlite3.connect(DB_PATH)
kefu = conn.execute("SELECT account FROM users WHERE role='客服' LIMIT 1").fetchone()
tmp = None
if not kefu:
    conn.execute("INSERT INTO users(account, pwd_hash, role, company) VALUES(?,?,?,?)",
                 ("自检:客服", "x", "客服", "壹城精工"))
    conn.commit()
    tmp = "自检:客服"
    kefu = (tmp,)
conn.close()
denied = rpc("tools/call", {"name": "sop_run", "arguments": {}}, kefu[0])
check("客服调用机器工具被拦(-32001)", denied.get("error", {}).get("code") == -32001,
      f"实际={denied}")
unknown = rpc("unknown_method", {}, "admin")
check("未知方法 -32601", unknown.get("error", {}).get("code") == -32601, f"实际={unknown}")

# 6. 清理测试数据
conn = sqlite3.connect(DB_PATH)
conn.execute("DELETE FROM customers WHERE id=?", (cid,))
if tmp:
    conn.execute("DELETE FROM users WHERE account=?", (tmp,))
conn.commit()
conn.close()

print("\n" + ("全部通过" if not fails else f"{len(fails)} 项失败"))
raise SystemExit(1 if fails else 0)
