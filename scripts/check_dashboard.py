# -*- coding: utf-8 -*-
"""登录跳转+工作台页快速验证（临时）"""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"

h = urllib.request.urlopen(BASE + "/health", timeout=5)
print("health:", h.status, json.loads(h.read().decode())["status"])

root = urllib.request.urlopen(BASE + "/", timeout=5).read().decode()
print("login page has redirect:", "window.location.href='/app'" in root)

app = urllib.request.urlopen(BASE + "/app", timeout=5).read().decode()
print("/app OK:", all(k in app for k in ("工作台", "客户线索", "收件箱", "SOP 待办", "业务指标", "知识库")))

req = urllib.request.Request(
    BASE + "/login",
    data=json.dumps({"account": "admin", "password": "12345678"}).encode(),
    headers={"Content-Type": "application/json"},
)
print("login resp:", urllib.request.urlopen(req, timeout=5).read().decode())
