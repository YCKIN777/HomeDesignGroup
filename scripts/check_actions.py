# -*- coding: utf-8 -*-
"""check_actions.py — Step 4.7 自检：动作注册表完整性 + 角色可执行 + 审计记账"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kernel import actions

ROOT = r"H:\AgentProjects\HomeDesignGroup"
DB_PATH = os.path.join(ROOT, "db", "壹城精工.db")
TEST_USER = "渠道:自检-4.7"

fails = []


def check(name, cond, msg):
    if not cond:
        fails.append(f"[FAIL] {name}: {msg}")
        print(f"[FAIL] {name}: {msg}")
    else:
        print(f"[PASS] {name}")


# 0. 准备测试账号（真实账号优先，无则临时插入，测后清理）
conn = sqlite3.connect(DB_PATH)
kefu_acct = conn.execute(
    "SELECT account FROM users WHERE role='客服' LIMIT 1").fetchone()
xiaoshou_acct = conn.execute(
    "SELECT account FROM users WHERE role='销售' LIMIT 1").fetchone()
tmp_created = []
if not kefu_acct:
    conn.execute("INSERT INTO users(account, pwd_hash, role, company) VALUES(?,?,?,?)",
                 ("自检:客服", "x", "客服", "壹城精工"))
    tmp_created.append("自检:客服")
    kefu_acct = ("自检:客服",)
if not xiaoshou_acct:
    conn.execute("INSERT INTO users(account, pwd_hash, role, company) VALUES(?,?,?,?)",
                 ("自检:销售", "x", "销售", "壹城精工"))
    tmp_created.append("自检:销售")
    xiaoshou_acct = ("自检:销售",)
conn.commit()
KEFU, XIAO = kefu_acct[0], xiaoshou_acct[0]

# 1. 注册表完整性
check("注册表非空", len(actions.REGISTRY) >= 14, f"动作数={len(actions.REGISTRY)}")
bad = [n for n, a in actions.REGISTRY.items()
       if not all(a.get(k) for k in ("label", "roles", "guard", "side_effects"))]
check("字段完整", not bad, f"缺字段: {bad}")

# 2. 角色可执行（webhook.ingest 仅内部账号放行，不出现在主管清单）
boss = {a["name"] for a in actions.describe_actions("admin")}
kefu = {a["name"] for a in actions.describe_actions(KEFU)}
xiao = {a["name"] for a in actions.describe_actions(XIAO)}
check("主管全量(除渠道接入)", boss == set(actions.REGISTRY) - {"webhook.ingest"},
      f"主管缺: {set(actions.REGISTRY) - {'webhook.ingest'} - boss}, 多: {boss - set(actions.REGISTRY)}")
kefu_expected = {"lead.write", "lead.import", "lead.csv", "transition",
                 "draft", "score", "todo.done", "memory.write"}
check("客服=WRITE集(不含渠道接入)", kefu == kefu_expected, f"客服实际={sorted(kefu)}")
check("销售=WRITE+邀约审批", xiao == kefu_expected | {"invite", "approve", "noshow", "reject"},
      f"销售实际={sorted(xiao)}")
ch = {a["name"] for a in actions.describe_actions("渠道:自检")}
check("内部账号含渠道接入", "webhook.ingest" in ch, f"渠道账号实际={sorted(ch)}")

# 3. 校验
ok, _ = actions.check_action("admin", "dispatch")
check("主管可派单", ok, "dispatch 应放行")
ok, _ = actions.check_action(KEFU, "dispatch")
check("客服不可派单", not ok, "客服 dispatch 应拒绝")
ok, _ = actions.check_action("admin", "不存在.动作")
check("未知动作拒绝", not ok, "未知动作应拒绝")

# 4. execute 审计记账（内部账号放行；测试标记，测后清理）
r_ok, _ = actions.execute("dispatch", TEST_USER, "customers#0", before="线索", after="派单")
check("execute 内部账号放行", r_ok, "渠道: 前缀应放行")
r_ok, _ = actions.execute("dispatch", KEFU, "customers#0")
check("execute 客服拒绝", not r_ok, "客服 dispatch 应拒绝")

n = conn.execute("SELECT COUNT(*) FROM audit_log WHERE user=? AND action='dispatch'",
                 (TEST_USER,)).fetchone()[0]
check("审计记账落库", n == 1, f"audit_log 应有1条 dispatch 记录, 实际={n}")

# 5. 清理测试数据
conn.execute("DELETE FROM audit_log WHERE user=?", (TEST_USER,))
for t in tmp_created:
    conn.execute("DELETE FROM users WHERE account=?", (t,))
conn.commit()
conn.close()

print("\n" + ("全部通过" if not fails else f"{len(fails)} 项失败"))
raise SystemExit(1 if fails else 0)
