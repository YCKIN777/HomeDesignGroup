# -*- coding: utf-8 -*-
"""verify_mcp_contract.py — D 阶段：契约线三 Agent 经 MCP 出口暴露验证"""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"
fails = []


def check(name, cond, msg):
    if not cond:
        fails.append(name)
        print(f"[FAIL] {name}: {msg}")
    else:
        print(f"[PASS] {name}")


def mcp(method, params=None, rid=1, user="admin"):
    body = {"jsonrpc": "2.0", "id": rid, "method": method}
    if params is not None:
        body["params"] = params
    req = urllib.request.Request(BASE + "/mcp", data=json.dumps(body).encode(),
                                 method="POST",
                                 headers={"Content-Type": "application/json",
                                          "X-Agent-User": user})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


# 1. 协议握手
r = mcp("initialize", {"protocolVersion": "2025-03-26"})
check("MCP initialize", r.get("result", {}).get("serverInfo", {}).get("name"),
      f"resp={r}")

# 2. 工具清单含契约线三个工具
r = mcp("tools/list")
names = [t["name"] for t in r["result"]["tools"]]
check("tools/list 含 contract_craft_qa",
      "contract_craft_qa" in names, f"names={names}")
check("tools/list 含 contract_build_quote", "contract_build_quote" in names, "")
check("tools/list 含 contract_site_report", "contract_site_report" in names, "")

# 3. 工艺问答（读工具，任意账号）
r = mcp("tools/call", {"name": "contract_craft_qa",
                       "arguments": {"question": "轻钢龙骨吊顶怎么做", "user": "客服"}})
txt = r["result"]["content"][0]["text"]
d = json.loads(txt)
check("contract_craft_qa 命中真实工艺", d.get("craft_total", 0) >= 1,
      f"total={d.get('craft_total')}")

# 4. 报价单（draft 写工具，admin=主管含 draft；owner_id 动态取）
r_own = mcp("tools/call", {"name": "leads_search",
                           "arguments": {"q": "demo", "limit": 5}}, rid=99)
with urllib.request.urlopen(BASE + "/api/core/owners", timeout=10) as rr:
    owners = json.loads(rr.read().decode()).get("items", [])
oid = owners[0]["id"] if owners else None
r = mcp("tools/call", {"name": "contract_build_quote",
                       "arguments": {"owner_id": oid, "requirements": "全屋硬装",
                                     "category": "瓷砖", "user": "admin"}})
txt = r["result"]["content"][0]["text"]
d = json.loads(txt)
check("contract_build_quote 生成草稿", d.get("row_count", 0) >= 1 and
      d.get("status") == "draft", f"d={d.get('row_count')}")

# 5. 工地日报（draft 写工具）
r = mcp("tools/call", {"name": "contract_site_report",
                       "arguments": {"project": "保利和光尘樾-189",
                                     "photo_desc": "木工吊顶龙骨完成", "user": "admin"}})
txt = r["result"]["content"][0]["text"]
d = json.loads(txt)
check("contract_site_report pending", d.get("status") == "pending_human",
      f"status={d.get('status')}")

# 6. 权限校验：只读账号（设计总监）调写工具被拒
r = mcp("tools/call", {"name": "contract_build_quote",
                       "arguments": {"owner_id": oid, "user": "黄旭"}})
check("设计总监调报价单被拒", r.get("error", {}).get("code") == -32001,
      f"resp={r}")

print("\n" + ("全部通过" if not fails else f"{len(fails)} 项失败"))
sys.exit(1 if fails else 0)
