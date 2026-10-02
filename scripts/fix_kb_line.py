# -*- coding: utf-8 -*-
import io

P = r"H:\AgentProjects\HomeDesignGroup\knowledge\01-报价-壹城估算书.md"
s = io.open(P, encoding="utf-8").read()
old = "（工程造价： 元示例造价）"
new = "（封面示例造价 1540 元为占位）"
assert old in s, "目标串未找到"
s = s.replace(old, new)
io.open(P, "w", encoding="utf-8", newline="\n").write(s)
print("已替换:", new)
