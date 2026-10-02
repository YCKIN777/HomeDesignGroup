# -*- coding: utf-8 -*-
"""验证 /app 页面含契约线面板 + 三个 Agent 端点可用"""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"


def get_html(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return r.read().decode("utf-8")


def get_json(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


html = get_html("/app")
print("页面长度:", len(html))
print("含 s-contract:", "s-contract" in html)
print("含 runQa/runQuote/runReport:", all(k in html for k in ("runQa", "runQuote", "runReport")))
print("含 loadOwners:", "loadOwners" in html)

# 三个端点冒烟（真实数据）
r = post("/api/agents/craft-qa", {"question": "轻钢龙骨吊顶怎么做", "user": "客服"})
print("工艺问答命中:", len(r.get("craft", [])), "条，首条:", r["craft"][0]["title"][:24] if r.get("craft") else "-")

r2 = get_json("/api/core/owners")
owners = r2.get("items", [])
print("业主列表:", len(owners), "条")
if owners:
    oid = owners[0]["id"]
    r3 = post("/api/agents/quote", {"owner_id": oid, "requirements": "全屋硬装", "category": "瓷砖", "user": "销售"})
    print("报价单行数:", r3.get("row_count"), "，列项:", r3.get("columns")[0] + "/" + r3["columns"][-1])

r4 = post("/api/agents/site-report", {"project": "保利和光尘樾-189", "photo_desc": "木工吊顶龙骨完成", "user": "监理"})
print("工地日报:", r4.get("status"), "|", r4.get("progress_summary", "")[:36])
