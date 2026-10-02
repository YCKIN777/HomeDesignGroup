# -*- coding: utf-8 -*-
"""verify_core_tables.py — Step 3 自检：三张核心表 API 读写"""
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = r"H:\AgentProjects\HomeDesignGroup"
BASE = "http://127.0.0.1:8000"
CORE_DB = os.path.join(ROOT, "db", "homeagent.db")
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
        BASE + path, data=data, method=method,
        headers={"Content-Type": "application/json", "X-Agent-User": user})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def q(url):
    with urllib.request.urlopen(BASE + url, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


# 1. 健康
try:
    q("/health")
    check("服务健康", True, "")
except Exception as e:
    print("[FAIL] 服务健康:", e)
    sys.exit(1)

# 0. 前置清理（可重入：上次崩溃残留清理）
_conn = sqlite3.connect(CORE_DB)
_conn.execute("DELETE FROM owners WHERE wechat_id='wx_test_core'")
_conn.execute("DELETE FROM craft_knowledge WHERE title IN ('轻钢龙骨双层石膏板','权限验证')")
_conn.execute("DELETE FROM materials WHERE name='佛山白岩板'")
_conn.commit()
_conn.close()
_main = sqlite3.connect(os.path.join(ROOT, "db", "壹城精工.db"))
_main.execute("DELETE FROM users WHERE account='客服' AND role='客服'")  # 清理历史测试账号
_main.commit()
_main.close()

# 2. owners：建 + 查（含 style 过滤）
o = http("POST", "/api/core/owners", {"wechat_id": "wx_test_core",
                                      "nickname": "测试业主", "community": "保利和光尘樾",
                                      "house_area": 189, "layout_json": '{"rooms":4}',
                                      "budget_total": 800000, "budget_used": 120000,
                                      "style_preference": "新中式"})
oid = o.get("id")
check("owners 新建", o.get("ok") is True and oid, f"实际={o}")
got = q("/api/core/owners?q=%E4%BF%9D%E5%88%A9&style=%E6%96%B0%E4%B8%AD%E5%BC%8F")
check("owners 按社区+风格检索", any(i["wechat_id"] == "wx_test_core" for i in got["items"]),
      f"items={got['items']}")
one = q(f"/api/core/owners/{oid}")
check("owners 单查含预算字段", one.get("budget_total") == 800000 and "layout_json" in one,
      f"实际={one}")

# 3. craft_knowledge：建 + 查
c = http("POST", "/api/core/craft", {"category": "降噪隔墙", "title": "轻钢龙骨双层石膏板",
                                     "content": "轻钢龙骨+岩棉+双层石膏板，隔声 45dB",
                                     "source_file": "knowledge/02-工艺-隐蔽工程验收.md",
                                     "embedding_id": "emb_smoke_1"})
cid = c.get("id")
check("craft 新建", c.get("ok") is True and cid, f"实际={c}")
cg = q("/api/core/craft?category=%E9%99%8D%E5%99%AA%E9%9A%94%E5%A2%99")
check("craft 按分类检索", any(i["id"] == cid for i in cg["items"]), f"items={cg['items']}")

# 4. materials：建 + 查
m = http("POST", "/api/core/materials", {"category": "岩板", "name": "佛山白岩板",
                                         "spec": "1200x2700mm", "supplier": "佛山厂商A",
                                         "price": 260, "moq": 10, "tags": "台面,岩板"})
mid = m.get("id")
check("materials 新建", m.get("ok") is True and mid, f"实际={m}")
mg = q("/api/core/materials?category=%E5%B2%A9%E6%9D%BF&q=%E7%99%BD%E5%B2%A9%E6%9D%BF")
check("materials 检索命中", any(i["id"] == mid for i in mg["items"]), f"items={mg['items']}")

# 5. 权限：客服账号写 craft（lead.write 属于客服）→ 临时插入客服账号验证后清理
_tmp = sqlite3.connect(os.path.join(ROOT, "db", "壹城精工.db"))
_tmp.execute("INSERT INTO users (account, role, pwd_hash) VALUES ('客服','客服','x')")
_tmp.commit()
_tmp.close()
try:
    ck = http("POST", "/api/core/craft", {"user": "客服", "category": "测试",
                                          "title": "权限验证", "content": "x"})
    check("客服可写 craft（lead.write）", ck.get("ok") is True, f"实际={ck}")
except urllib.error.HTTPError as e:
    check("客服可写 craft（lead.write）", False, f"HTTP {e.code} {e.read().decode()[:100]}")
ck_id = ck.get("id") if ck.get("ok") else None

# 6. 清理测试数据（owners/craft/materials 三表 + 审计）
conn = sqlite3.connect(CORE_DB)
conn.execute("DELETE FROM owners WHERE wechat_id='wx_test_core'")
conn.execute("DELETE FROM craft_knowledge WHERE title IN ('轻钢龙骨双层石膏板','权限验证')")
conn.execute("DELETE FROM materials WHERE name='佛山白岩板'")
conn.commit()
conn.close()
conn2 = sqlite3.connect(os.path.join(ROOT, "db", "壹城精工.db"))
conn2.execute("DELETE FROM users WHERE account='客服' AND role='客服'")  # 删除临时测试账号
conn2.execute("DELETE FROM audit_log WHERE target IN (?,?,?) OR target LIKE ?",
              (f"owners#{oid}", f"craft_knowledge#{cid}", f"materials#{mid}",
               "craft_knowledge%"))
conn2.commit()
conn2.close()
print("清理完成")

print("\n" + ("全部通过" if not fails else f"{len(fails)} 项失败"))
sys.exit(1 if fails else 0)
