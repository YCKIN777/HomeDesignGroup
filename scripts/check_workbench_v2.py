# -*- coding: utf-8 -*-
"""工作台v2 链路 e2e 验证（临时）：起草→审批→状态迁移→项目"""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"
U = "验证员"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return json.loads(r.read().decode())


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


# 0. 页面包含新元素
app_html = urllib.request.urlopen(BASE + "/app", timeout=10).read().decode()
print("0. /app 含 起草/状态下拉/详情/项目:", all(k in app_html for k in ("draftLead", "setStatus", "toggleDetail", "loadProjects")))

# 1. 建测试线索（工作台"新建线索"同款）
st, d = post("/api/leads", {"phone": "13707770001", "name": "工作台验证", "estate": "麓润栖湖",
                            "budget_range": "50-80万", "channel": "转介绍", "user": U})
print("1. 建线索:", st, d.get("id", d))
cid = d["id"]

# 2. AI 起草（工作台"起草"按钮同款）
st, d = post("/api/inbox/draft", {"customer_id": cid, "user": U})
print("2. 起草:", st, d.get("id", d))
mid = d.get("id")

# 3. 收件箱出现 + 审批发送
inbox = get("/api/inbox")
print("3. 收件箱含起草消息:", any(m.get("id") == mid for m in inbox["items"]))
st, d = post(f"/api/inbox/{mid}/approve", {"user": U})
print("   审批发送:", st, d)

# 4. 状态迁移：合法(线索→跟进) 与 非法(线索→派单 跳过邀约/到店)
st, d = post(f"/api/leads/{cid}/status", {"to": "跟进", "user": U})
print("4. 合法迁移 线索→跟进:", st, d)
st2, d2 = post(f"/api/leads/{cid}/status", {"to": "派单", "user": U})
print("   非法迁移 跟进→派单:", st2, d2.get("error", d2))

# 5. 详情接口（工作台"详情"按钮同款）
d = get(f"/api/leads/{cid}")
print("5. 详情: l2消息数=", len(d.get("l2", [])), "tags=", d.get("tags"))

# 6. 项目列表（工作台项目区块）
d = get("/api/projects")
print("6. 项目列表 total:", d.get("total", len(d.get("items", []))))

# 清理测试数据
st, d = post("/api/leads/" + str(cid) + "/noshow", {"user": U})  # 仅触发一次清理占位
print("7. 测试完成（线索保留待人工清理或走 clean_test_data）")
