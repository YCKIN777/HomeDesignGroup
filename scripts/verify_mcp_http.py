# -*- coding: utf-8 -*-
"""verify_mcp_http.py — Step 4.8 端到端：真实 HTTP POST /mcp 验证"""
import json
import urllib.request

URL = "http://127.0.0.1:8000/mcp"
fails = []


def check(name, cond, msg):
    if not cond:
        fails.append(name)
        print(f"[FAIL] {name}: {msg}")
    else:
        print(f"[PASS] {name}")


def rpc(method, params=None, user="admin"):
    body = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params:
        body["params"] = params
    req = urllib.request.Request(
        URL, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Agent-User": user})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


# 健康检查先行
try:
    with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=10) as r:
        health = json.loads(r.read().decode("utf-8"))
    check("服务健康", health.get("status") == "ok", f"health={health}")
except Exception as e:
    check("服务健康", False, f"无法连接: {e}")

init = rpc("initialize", {"protocolVersion": "2025-03-26"})
check("HTTP initialize 握手", init.get("result", {}).get("serverInfo", {}).get("name") == "壹城精工-MCP",
      f"实际={init}")

lst = rpc("tools/list")
tools = lst.get("result", {}).get("tools", [])
check("HTTP tools/list 10 工具", len(tools) == 10, f"实际={len(tools)}")

kb = rpc("tools/call", {"name": "kb_search", "arguments": {"query": "防水", "top_k": 2}})
txt = kb.get("result", {}).get("content", [{}])[0].get("text", "")
check("HTTP kb_search 有结果", kb.get("result", {}).get("isError") is False and '"total"' in txt,
      f"实际={kb}")

print("\n" + ("全部通过" if not fails else f"{len(fails)} 项失败"))
raise SystemExit(1 if fails else 0)
