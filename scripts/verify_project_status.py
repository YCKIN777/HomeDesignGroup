# -*- coding: utf-8 -*-
"""verify_project_status.py — 5.1 项目状态迁移 API 验证

覆盖：合法迁移链（量房→设计→报价→签约→开工→水电→防水→泥木→油漆→安装→验收交付）、
非法跳级拦截、锁节点不可跳过、迁移落库+审计、权限校验。
"""
import json
import sqlite3
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"
DB = r"H:\AgentProjects\HomeDesignGroup\db\壹城精工.db"
fails = []


def check(name, cond, detail=""):
    if not cond:
        fails.append(name)
        print(f"[FAIL] {name}: {detail}")
    else:
        print(f"[PASS] {name}")


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "_body": e.read().decode()[:200]}
    except urllib.error.URLError as e:
        return {"_http_error": "URL", "_body": str(e)}


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return json.loads(r.read().decode())


# 前置：造一条测试客户+项目（自清理）
conn = sqlite3.connect(DB)
conn.execute("DELETE FROM projects WHERE customer_id IN "
             "(SELECT id FROM customers WHERE phone='19900009999')")
conn.execute("DELETE FROM customers WHERE phone='19900009999'")
conn.execute("INSERT INTO customers(phone,name,estate,status,channel,tags) "
             "VALUES('19900009999','迁移测试','测试楼盘','派单','转介绍','测试')")
cid = conn.execute("SELECT id FROM customers WHERE phone='19900009999'").fetchone()[0]
conn.commit()
conn.close()

# 建项目（量房）
r = post("/api/dispatch", {"user": "admin", "customer_id": cid, "designer": "黄旭"})
check("派单建项目", r.get("id") and not r.get("dup"), f"r={r}")
pid = r["id"]

# 合法迁移链：量房→设计→报价→签约→开工→水电→防水→泥木→油漆→安装→验收交付
# 6.4 开工闸门适配：报价在"签约"前生成（项目签约后不可再生成报价）；
# 签约后收足 60% 首款，闸门（报价有效+签约款收足）放行开工。
chain = ["设计", "报价"]
ok = True
for st in chain:
    r = post(f"/api/projects/{pid}/status", {"user": "admin", "to": st})
    if r.get("to") != st:
        ok = False
        print(f"  [chain] {st} -> {r}")
        break
if ok:
    r = post(f"/api/projects/{pid}/quote", {"user": "admin", "requirements": "迁移链测试"})
    qid = r.get("id")
    if not qid:
        ok = False
        print(f"  [chain] 报价生成失败 -> {r}")
    else:
        tail = ["签约", "开工", "水电", "防水", "泥木", "油漆", "安装", "验收交付"]
        for i, st in enumerate(tail):
            if not ok:
                break
            if st == "开工":
                conn = sqlite3.connect(DB)
                total = conn.execute("SELECT total FROM quotes WHERE id=?", (qid,)).fetchone()[0]
                conn.close()
                post(f"/api/quotes/{qid}/payments",
                     {"user": "admin", "stage": "签约", "amount": round(total * 0.6, 2)})
            r = post(f"/api/projects/{pid}/status", {"user": "admin", "to": st})
            if r.get("to") != st:
                ok = False
                print(f"  [chain] {st} -> {r}")
check("合法迁移链 11 节点走通(含开工闸门)", ok, "断在 " + st if not ok else "")

# 落库确认
conn = sqlite3.connect(DB)
cur = conn.execute("SELECT status FROM projects WHERE id=?", (pid,)).fetchone()[0]
conn.close()
check("迁移落库", cur == "验收交付", f"cur={cur}")

# 非法跳级拦截：验收交付→泥木（无迁移规则）
r = post(f"/api/projects/{pid}/status", {"user": "admin", "to": "泥木"})
check("非法跳级拦截", "不合法" in str(r.get("_body") or r), f"r={r}")

# 未知状态拦截
r = post(f"/api/projects/{pid}/status", {"user": "admin", "to": "不存在"})
check("未知状态拦截", "不合法" in str(r.get("_body") or r), f"r={r}")

# 锁节点：新建项目直接跳 设计 校验——量房→设计 合法；从初始验证 水电 不可直达
r = post("/api/dispatch", {"user": "admin", "customer_id": cid, "designer": "黄旭"})
pid2 = r["id"]
r2 = post(f"/api/projects/{pid2}/status", {"user": "admin", "to": "水电"})
check("锁节点不可跳过（量房→水电 拦截）", "不合法" in str(r2.get("_body") or r2), f"r={r2}")

# 权限：设计总监（只读）不可迁移
r3 = post(f"/api/projects/{pid}/status", {"user": "黄旭", "to": "量房"})
check("只读角色迁移被拒", r3.get("_http_error") == 403 or "权限" in str(r3), f"r={r3}")

# 审计落库
conn = sqlite3.connect(DB)
n = conn.execute("SELECT COUNT(*) FROM audit_log WHERE target=?", (f"projects#{pid}",)).fetchone()[0]
conn.close()
check("审计留痕", n >= 10, f"audit={n}")

# 清理测试数据
conn = sqlite3.connect(DB)
conn.execute("DELETE FROM projects WHERE customer_id=?", (cid,))
conn.execute("DELETE FROM customers WHERE id=?", (cid,))
conn.execute("DELETE FROM audit_log WHERE target LIKE 'projects#%' "
             "AND (after='迁移测试' OR 1=0)")
conn.execute("DELETE FROM audit_log WHERE target IN (SELECT 'projects#'||id FROM projects WHERE customer_id=?)", (cid,))
conn.commit()
conn.close()

print("\n" + ("全部通过" if not fails else f"{len(fails)} 项失败"))
sys.exit(1 if fails else 0)
