# -*- coding: utf-8 -*-
"""Step 2.x 自检（M1→M2→M3a→M4→M5 全链路）：启动服务 → 走通闭环 → 清理测试数据"""
import json
import subprocess
import sys
import time
import urllib.request

PORT = 8766
BASE = f"http://127.0.0.1:{PORT}"
SRC = r"H:\AgentProjects\HomeDesignGroup\src"
TEST_PHONE = "13888888888"
ok = True


def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def put(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="PUT")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


# 前置：清理可能残留的测试数据（幂等）
import os
import sqlite3
_db = sqlite3.connect(r"H:\AgentProjects\HomeDesignGroup\db\壹城精工.db")
for _p in ("13888888888",):
    for _cid in [r[0] for r in _db.execute("SELECT id FROM customers WHERE phone=?", (_p,))]:
        for _t in ("messages", "followups", "projects", "todos"):
            _db.execute(f"DELETE FROM {_t} WHERE customer_id=?", (_cid,))
        _db.execute("DELETE FROM customers WHERE id=?", (_cid,))
_db.commit()
_db.close()

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

    print("== Step2.1 M1 线索归集（录入+去重合并）==")
    r1 = post("/api/leads", {"user": "admin", "phone": TEST_PHONE, "name": "测试客户",
                             "estate": "测试楼盘", "channel": "社群"})
    print(f"  首次录入: {r1}")
    ok = ok and r1["deduped"] is False and r1["id"] > 0
    cid = r1["id"]
    r2 = post("/api/leads", {"user": "admin", "phone": TEST_PHONE, "name": "测试客户",
                             "budget_range": "40-60万", "style": "奶油风"})
    print(f"  重复录入: {r2}")
    ok = ok and r2["deduped"] is True and r2["id"] == cid

    print("== Step2.2 M2 建档打标+状态迁移 ==")
    r3 = post(f"/api/leads/{cid}/status", {"user": "admin", "to": "跟进"})
    print(f"  迁移 线索→跟进: {r3}")
    ok = ok and r3["to"] == "跟进"
    try:
        post(f"/api/leads/{cid}/status", {"user": "admin", "to": "签约"})
        ok = False
        print("  FAIL 非法迁移未被拦截")
    except urllib.error.HTTPError:
        print("  OK   非法迁移 线索→签约 被拦截（workflow 校验生效）")
    r4 = put(f"/api/leads/{cid}", {"user": "admin", "tags": "岳麓区,改善,全包"})
    print(f"  打标: {r4['tags']}")
    ok = ok and r4["tags"] == "岳麓区,改善,全包"

    print("== Step2.3 M3a 收件箱：AI起草→审批→发送 ==")
    d = post("/api/inbox/draft", {"user": "admin", "customer_id": cid, "kind": "first_contact"})
    print(f"  草稿#{d['id']}: {d['content'][:50]}")
    ok = ok and d["approve_status"] == "draft"
    mid = d["id"]
    ib = get("/api/inbox")
    print(f"  收件箱: {ib['total']} 条草稿")
    ok = ok and ib["total"] >= 1
    a = post(f"/api/inbox/{mid}/approve", {"user": "admin"})
    print(f"  审批: {a}")
    ok = ok and a["approve_status"] == "sent"
    try:
        post(f"/api/inbox/{mid}/approve", {"user": "admin"})
        ok = False
        print("  FAIL 重复审批未被拦截")
    except urllib.error.HTTPError:
        print("  OK   重复审批被拦截（状态机保护）")

    print("== Step2.4 M4 派单建项目 ==")
    p1 = post("/api/dispatch", {"user": "admin", "customer_id": cid, "designer": "王设计"})
    print(f"  派单: {p1}")
    ok = ok and p1["dup"] is False and p1["id"] > 0
    p2 = post("/api/dispatch", {"user": "admin", "customer_id": cid, "designer": "王设计"})
    print(f"  重复派单: {p2}")
    ok = ok and p2["dup"] is True
    pr = get("/api/projects")
    print(f"  项目列表: {pr['total']} 个")
    ok = ok and pr["total"] >= 1

    print("== Step2.5 M5 配置接通 ==")
    cfg = get("/api/config")
    print(f"  {cfg['company']} terms={len(cfg['terms'])} rules={list(cfg['rules'].keys())} "
          f"locked={cfg['workflow']['locked_nodes']}")
    ok = ok and cfg["company"] == "壹城精工" and "scoring" in cfg["rules"]

    print("== 审计核验 ==")
    import sqlite3
    conn = sqlite3.connect(r"H:\AgentProjects\HomeDesignGroup\db\壹城精工.db")
    acts = [r[0] for r in conn.execute(
        "SELECT action FROM audit_log WHERE target LIKE '%customers#" + str(cid) + "%' "
        "OR target LIKE '%messages#" + str(mid) + "%' ORDER BY id")]
    print(f"  该客户审计轨迹: {acts}")
    conn.close()
    ok = ok and "审批发送" in acts

    print("== 清理测试数据 ==")
    conn = sqlite3.connect(r"H:\AgentProjects\HomeDesignGroup\db\壹城精工.db")
    conn.execute("DELETE FROM messages WHERE customer_id=?", (cid,))
    conn.execute("DELETE FROM followups WHERE customer_id=?", (cid,))
    conn.execute("DELETE FROM projects WHERE customer_id=?", (cid,))
    conn.execute("DELETE FROM todos WHERE customer_id=?", (cid,))
    conn.execute("DELETE FROM customers WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    print("  已清理")
finally:
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()

print("\n== 自检结论 ==")
print("  PASS — 阶段2 MVP闭环(M1-M5)全部通过，可进入阶段3" if ok else "  FAIL — 请检查上述失败项")
