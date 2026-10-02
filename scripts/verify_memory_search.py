# -*- coding: utf-8 -*-
"""verify_memory_search.py — 4.11 API 面验证：/api/memory/search"""
import json
import sys
import urllib.parse
import urllib.request

URL = "http://127.0.0.1:8000"
fails = []


def check(name, cond, msg):
    if not cond:
        fails.append(name)
        print(f"[FAIL] {name}: {msg}")
    else:
        print(f"[PASS] {name}")


def get(path):
    with urllib.request.urlopen(URL + path, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def search(q, top_k=5):
    return get("/api/memory/search?" + urllib.parse.urlencode({"q": q, "top_k": top_k}))


# 1. 健康
try:
    get("/health")
    check("服务健康", True, "")
except Exception as e:
    print("[FAIL] 服务健康:", e)
    sys.exit(1)

# 2. 检索命中 L3 知识库（带来源）
r = search("防水", 5)
items = r.get("items", [])
check("检索返回带来源条目", r.get("total", 0) >= 1 and all("source" in i for i in items),
      f"实际 total={r.get('total')} items={items[:2]}")
check("命中 L3 知识库来源", any("knowledge" in i["source"] for i in items),
      f"来源={[i['source'] for i in items]}")

# 3. 检索 L4 文本记忆
r4 = search("渠道", 5)
check("命中 L4 文本记忆", any("memory" in i["source"] for i in r4.get("items", [])),
      f"来源={[i['source'] for i in r4.get('items', [])]}")

# 4. 空查询防御
r0 = search("", 5)
check("空查询返回 total=0", r0.get("total") == 0, f"实际={r0}")

print("\n" + ("全部通过" if not fails else f"{len(fails)} 项失败"))
sys.exit(1 if fails else 0)
