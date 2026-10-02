# -*- coding: utf-8 -*-
"""Step 1.7 自检：启动 uvicorn → /health、登录页、登录成功/失败 → 关闭"""
import json
import subprocess
import sys
import time
import urllib.request

PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"
SRC = r"H:\AgentProjects\HomeDesignGroup\src"
ok = True


def get(path: str):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return r.status, r.read().decode("utf-8")


def post(path: str, payload: dict):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


server = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "api_server:app", "--port", str(PORT)],
    cwd=SRC, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

try:
    # 等就绪（最多 30s）
    ready = False
    for _ in range(30):
        try:
            get("/health")
            ready = True
            break
        except Exception:
            time.sleep(1)
    print(f"== 0) 服务就绪: {ready} ==")
    ok = ok and ready

    print("== 1) /health ==")
    st, body = get("/health")
    h = json.loads(body)
    print(f"  {st} {h}")
    ok = ok and st == 200 and h["status"] == "ok" and h["db"] and h["config"] and h["llm"]

    print("== 2) 登录页 ==")
    st, body = get("/")
    print(f"  {st} 标题包含: {'家装 AI 智能体平台' in body}")
    ok = ok and st == 200 and "家装 AI 智能体平台" in body

    print("== 3) 登录成功 admin/12345678 ==")
    st, d = post("/login", {"account": "admin", "password": "12345678"})
    print(f"  {st} {d}")
    ok = ok and st == 200 and d["ok"] and d["role"] == "主管"

    print("== 4) 登录失败（错误密码）==")
    st, d = post("/login", {"account": "admin", "password": "wrong"})
    print(f"  {st} {d}")
    ok = ok and st == 401 and not d["ok"]

    print("== 5) 登录失败（账号不存在）==")
    st, d = post("/login", {"account": "nobody", "password": "x"})
    print(f"  {st} {d}")
    ok = ok and st == 401
finally:
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()

print("\n== 自检结论 ==")
print("  PASS — Step 1.7 产物完整，阶段1骨架全部完成" if ok else "  FAIL — 请检查上述失败项")
