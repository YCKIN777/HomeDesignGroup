# -*- coding: utf-8 -*-
"""壹城真实配置生效验证（临时）"""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"

h = urllib.request.urlopen(BASE + "/health", timeout=5)
print("health:", h.status, json.loads(h.read().decode())["status"])

cfg = json.loads(urllib.request.urlopen(BASE + "/api/config", timeout=5).read().decode())
rules = cfg.get("rules", {})
print("payment_stages:", rules.get("payment_stages"))
print("discount:", rules.get("discount"))
print("sop:", rules.get("sop"))
print("warranty:", rules.get("warranty"))

for acct in ("周乾坤", "苏巍", "王经理"):
    req = urllib.request.Request(
        BASE + "/login",
        data=json.dumps({"account": acct, "password": "12345678"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    print("login", acct, "->", urllib.request.urlopen(req, timeout=5).read().decode())
