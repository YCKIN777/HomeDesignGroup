# -*- coding: utf-8 -*-
"""提取 DASHBOARD_PAGE 的 script 内容（从 DASHBOARD_PAGE 定义之后开始匹配）"""
import io
import re

PATH = r"H:\AgentProjects\HomeDesignGroup\src\api_server.py"
s = io.open(PATH, encoding="utf-8").read()
start = s.find("DASHBOARD_PAGE")
seg = s[start:]
m = re.search(r"<script>(.*?)</script>", seg, re.S)
if m:
    out = m.group(1)
    io.open(r"H:\AgentProjects\HomeDesignGroup\logs\dashboard_script.js", "w", encoding="utf-8", newline="").write(out)
    print("extracted", len(out), "chars")
    idx = out.find("AI 顾问")
    if idx >= 0:
        print("--- AI 顾问段 ---")
        print(out[max(0,idx-300):idx+1500])
