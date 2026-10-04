# -*- coding: utf-8 -*-
"""修复：DASHBOARD_PAGE（Python 三引号字符串）内 JS 的 '\n\n' 被 Python 转义为真实换行，
需要写成 '\\\\n\\\\n'（文本层双反斜杠），运行时才生成 JS 的 \n\n 转义序列。"""
import io

PATH = r"H:\AgentProjects\HomeDesignGroup\src\api_server.py"
s = io.open(PATH, encoding="utf-8").read()

# 文件当前文本：split('\n\n')（单反斜杠 n 单反斜杠 n）
old = "var lines = buf.split('\\n\\n'); buf = lines.pop();"
# 目标文本：split('\\n\\n')（双反斜杠 n 双反斜杠 n）——Python 执行后生成单反斜杠序列
new = "var lines = buf.split('\\\\n\\\\n'); buf = lines.pop();"

if old in s:
    s = s.replace(old, new, 1)
    io.open(PATH, "w", encoding="utf-8", newline="").write(s)
    print("FIX OK: split('\\n\\n') -> split('\\\\n\\\\n')")
else:
    print("not found, check current text")
    idx = s.find("buf.split")
    print(s[idx-40:idx+60] if idx >= 0 else "no buf.split at all")
