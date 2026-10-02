# -*- coding: utf-8 -*-
"""Step C 自检：批量导入 / 权限矩阵 / SOP 调度 / webhook 放行"""
import json
import sqlite3
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
DB = r"H:\AgentProjects\HomeDesignGroup\db\壹城精工.db"
ok = True


def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


# 1. 批量导入：2 新建 + 1 重复 + 1 缺手机号
st, d = post("/api/leads/import", {"user": "admin", "rows": [
    {"phone": "13600000001", "name": "批量甲", "estate": "卓越中环", "budget_range": "50-80万", "channel": "抖音"},
    {"phone": "13600000002", "name": "批量乙", "estate": "保利和光尘樾", "channel": "小红书"},
    {"phone": "13600000001", "name": "批量甲-改", "budget_range": "80-120万"},
    {"phone": "", "name": "无号"},
]})
print("1. 批量导入:", st, "created=", d["created"], "merged=", d["merged"], "error=", d["error"])
ok = ok and st == 200 and d["created"] == 2 and d["merged"] == 1 and d["error"] == 1

# 2. 权限矩阵：admin 全过；客服 龙晓玲(行政) 派单被拦；未知账号被拦
cid = get("/api/leads?limit=1")["items"][0]["id"]
st, d = post("/api/dispatch", {"user": "admin", "customer_id": cid, "designer": "苏巍"})
print("2a. admin 派单:", st)
st2, d2 = post("/api/dispatch", {"user": "龙晓玲", "customer_id": cid, "designer": "苏巍"})
print("2b. 行政派单被拦:", st2, d2.get("detail", d2))
ok = ok and st == 200 and st2 == 403
st3, d3 = post("/api/leads", {"user": "路人甲", "phone": "13600000009"})
print("2c. 未知账号录线索被拦:", st3, d3.get("detail", d3))
ok = ok and st3 == 403

# 3. SOP 调度：手动触发 /api/sop/run（后台线程每60s也会自动跑）
st, d = post("/api/sop/run", {})
print("3. SOP 手动扫描:", st, d)
ok = ok and st == 200 and "open_todos" in d

# 4. webhook（渠道: 前缀内部账号放行）
st, d = post("/api/webhook/wecom", {"channel": "wecom", "phone": "13600000003",
                                    "name": "渠道客户", "estate": "麓润栖湖", "message": "报价多少"})
print("4. webhook 渠道放行:", st, d.get("ok", d))
ok = ok and st == 200 and d.get("ok") is True

# 清理本次导入/渠道的测试数据
conn = sqlite3.connect(DB)
for p in ("13600000001", "13600000002", "13600000003"):
    for cid in [r[0] for r in conn.execute("SELECT id FROM customers WHERE phone=?", (p,))]:
        for t in ("messages", "followups", "projects", "todos", "sessions"):
            conn.execute(f"DELETE FROM {t} WHERE customer_id=?", (cid,))
        conn.execute("DELETE FROM customers WHERE id=?", (cid,))
conn.commit()
conn.close()
print("5. 测试数据已清理")

# 清理本次派单给现有测试线索创建的项目（幂等）
conn = sqlite3.connect(DB)
conn.execute("DELETE FROM projects WHERE customer_id=? AND designer='苏巍'", (cid,))
conn.commit()
conn.close()
print("6. 派单测试项目已清理")

print("== 自检结论 ==")
print("  PASS — 批量导入/权限矩阵/SOP调度/webhook放行 全部通过" if ok else "  FAIL — 请检查上述失败项")
