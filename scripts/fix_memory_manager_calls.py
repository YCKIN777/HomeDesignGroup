# -*- coding: utf-8 -*-
"""修复 MemoryManager 多余参数调用：MemoryManager(参数) -> MemoryManager()"""
import io

FILES = [
    r"H:\AgentProjects\HomeDesignGroup\src\api_server.py",
    r"H:\AgentProjects\HomeDesignGroup\src\memory_retrieval.py",
    r"H:\AgentProjects\HomeDesignGroup\src\agents\invite_agent.py",
    r"H:\AgentProjects\HomeDesignGroup\src\agents\lead_agent.py",
    r"H:\AgentProjects\HomeDesignGroup\src\routers\leads.py",
    r"H:\AgentProjects\HomeDesignGroup\src\routers\memory_api.py",
]

for path in FILES:
    s = io.open(path, encoding="utf-8").read()
    before = s
    s = s.replace('MemoryManager("壹城精工")', "MemoryManager()")
    s = s.replace("MemoryManager(COMPANY)", "MemoryManager()")
    s = s.replace("MemoryManager(company)", "MemoryManager()")
    if s != before:
        io.open(path, "w", encoding="utf-8", newline="").write(s)
        print("FIXED:", path)
    else:
        print("NO-CHANGE:", path)

# 校验无残留
import subprocess
r = subprocess.run(
    ["grep", "-rn", "MemoryManager(", r"H:\AgentProjects\HomeDesignGroup\src"],
    capture_output=True, text=True
) if False else None
