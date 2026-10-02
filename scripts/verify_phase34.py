# -*- coding: utf-8 -*-
"""阶段3/4 自检：M6评分 / M7 SOP / M8邀约 / M9知识库 / L4记忆 / M3b渠道 / 指标 / 沉淀"""
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request
import urllib.error

PORT = 8769
BASE = f"http://127.0.0.1:{PORT}"
ROOT = r"H:\AgentProjects\HomeDesignGroup"
SRC = r"H:\AgentProjects\HomeDesignGroup\src"
DB = r"H:\AgentProjects\HomeDesignGroup\db\壹城精工.db"
ok = True


def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


from urllib.parse import quote


def get(path):
    with urllib.request.urlopen(BASE + quote(path, safe="/?=&"), timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


# 前置清理
conn = sqlite3.connect(DB)
for p in ("13888888888", "13999999999"):
    for cid in [r[0] for r in conn.execute("SELECT id FROM customers WHERE phone=?", (p,))]:
        for t in ("messages", "followups", "projects", "todos", "sessions"):
            conn.execute(f"DELETE FROM {t} WHERE customer_id=?", (cid,))
        conn.execute("DELETE FROM customers WHERE id=?", (cid,))
conn.commit()
conn.close()

server = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "api_server:app", "--port", str(PORT)],
    cwd=SRC, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(30):
        try:
            get("/health")
            break
        except Exception:
            time.sleep(1)

    # 建测试客户（信息齐全，便于评分/邀约/派单）
    r = post("/api/leads", {"user": "admin", "phone": "13888888888", "name": "阶段3测试",
                            "estate": "测试楼盘", "area": 128, "budget_range": "40-60万",
                            "style": "奶油风", "intent_time": "1个月内", "tags": "改善,全包",
                            "channel": "社群"})
    cid = r["id"]
    print(f"== 测试客户 #{cid} ==")

    print("== Step3.1 M6 评分分级 ==")
    s = post(f"/api/leads/{cid}/score", {"user": "admin"})
    print(f"  {s}")
    ok = ok and 0 <= s["score"] <= 100 and s["grade"] in ("A", "B", "C")

    print("== Step3.2 M7 SOP 提醒（到期跟进→待办）==")
    conn = sqlite3.connect(DB)
    conn.execute("INSERT INTO followups(customer_id, channel, content, next_at) "
                 "VALUES(?,?,?,?)", (cid, "电话", "约定周末到店", "2020-01-01 00:00:00"))
    conn.commit()
    conn.close()
    todos = get("/api/todos")["items"]
    print(f"  待办: {[(t['id'], t['task'][:20]) for t in todos[:5]]}")
    ok = ok and any("SOP跟进" in t["task"] for t in todos)
    if todos:
        d = post(f"/api/todos/{todos[0]['id']}/done", {"user": "admin"})
        print(f"  完成待办: {d}")
        ok = ok and d["done"] is True

    print("== Step3.3 M8 邀约到店 ==")
    inv = post(f"/api/leads/{cid}/invite", {"user": "admin", "when": "2026-10-05 14:00"})
    print(f"  邀约#{inv['id']}: {inv['content'][:50]} 状态={inv['status'] if 'status' in inv else '邀约'}")
    ok = ok and inv["id"] > 0

    print("== Step3.4 M9 知识库检索 ==")
    kb = get("/api/kb/search?q=隐蔽工程&top_k=3")
    print(f"  {[(h['title'], h['source']) for h in kb['hits']]}")
    ok = ok and len(kb["hits"]) >= 1 and kb["hits"][0]["source"].endswith(".md")

    print("== Step3.5 L4 记忆文件写入/检索 ==")
    w = post("/api/memory", {"concept_id": "concept.channel", "relation": "derived_from",
                             "state": "观察", "source": "自检", "content": "测试记忆：渠道占比待补充。"})
    print(f"  写入: {w}")
    ok = ok and w.get("file") and not w.get("error")
    lst = get("/api/memory/list")
    print(f"  记忆文件列表: {lst['files']}")
    ok = ok and lst["total"] >= 1

    print("== Step3.6 M3b 渠道 webhook（企微转发器模拟）==")
    wh = post("/api/webhook/wecom", {"channel": "wecom", "phone": "13999999999",
                                     "name": "企微客户", "estate": "保利和光尘樾",
                                     "message": "请问你们全包怎么收费"})
    print(f"  {wh}")
    ok = ok and wh["ok"] and wh["message_recorded"] is True

    print("== Step4 业务指标 ==")
    st = get("/api/stats")
    print(f"  {st}")
    ok = ok and "24h首联率" in st and "线索转化率(派单/线索)" in st

    print("== Step4 沉淀中心（准入4条）==")
    sd = post("/api/sedimentation", {"user": "admin", "category": "最佳实践", "title": "首联黄金24小时",
                                     "description": "线索24h内首联转化显著更高",
                                     "condition": "新线索", "evidence": "内部统计(匿名)"})
    print(f"  提交: {sd}")
    ok = ok and sd["ok"] and sd["status"] == "候选"
    sid = sd["id"]
    bad = post("/api/sedimentation", {"user": "admin", "title": "无实例", "description": "无证据的条目",
                                      "has_instance": False})
    print(f"  准入拦截: {bad}")
    ok = ok and bad["ok"] is False
    rv = post(f"/api/sedimentation/{sid}/review", {"user": "admin", "to": "已入内核"})
    print(f"  评审: {rv}")
    ok = ok and rv["status"] == "已入内核"

    # 清理（保留记忆文件与知识库——它们是资产）
    mat = rv.get("materialized")
    if mat:
        mp = os.path.join(ROOT, mat.replace("/", os.sep))
        if os.path.exists(mp):
            os.remove(mp)
    conn = sqlite3.connect(DB)
    for p in ("13888888888", "13999999999"):
        for cid2 in [r[0] for r in conn.execute("SELECT id FROM customers WHERE phone=?", (p,))]:
            for t in ("messages", "followups", "projects", "todos", "sessions"):
                conn.execute(f"DELETE FROM {t} WHERE customer_id=?", (cid2,))
            conn.execute("DELETE FROM customers WHERE id=?", (cid2,))
    conn.commit()
    conn.close()
    print("== 测试数据已清理 ==")
finally:
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()

print("\n== 自检结论 ==")
print("  PASS — 阶段3(M6-M9+L4+M3b)与阶段4(指标+沉淀)全部通过" if ok else "  FAIL — 请检查上述失败项")
