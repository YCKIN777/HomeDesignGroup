# -*- coding: utf-8 -*-
"""修复：AI 面板插入时吞掉了 s-team 的 </section>，导致 s-ai 嵌套进 s-team。
在 <section id="s-ai" 前补回 </section>，让 s-ai 成为 main 直接子元素。"""
import io

PATH = r"H:\AgentProjects\HomeDesignGroup\src\api_server.py"
s = io.open(PATH, encoding="utf-8").read()

anchor = '  <section id="s-ai" style="display:none"><h2>AI 顾问'
fix = "  </section>\n" + anchor

if anchor in s and s.count(anchor) == 1:
    s = s.replace(anchor, fix, 1)
    io.open(PATH, "w", encoding="utf-8", newline="").write(s)
    print("FIX OK: 补回 s-team 闭合 </section>")
else:
    print("anchor count:", s.count(anchor))
