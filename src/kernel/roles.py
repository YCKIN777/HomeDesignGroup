# -*- coding: utf-8 -*-
"""
roles.py — 组织分工权限矩阵（Step C）
按 users 表角色限制写操作；读取全开放。
内部账号（system / 渠道:*）放行（webhook、调度器等机器入口）。
"""
import os
import sqlite3

ROOT = r"H:\AgentProjects\HomeDesignGroup"
DB_PATH = os.path.join(ROOT, "db", "壹城精工.db")

VIEW = set()
WRITE = {"lead.write", "transition", "draft", "score", "todo.done", "memory.write",
         "aftersales.write"}                     # 售后工单/质保：客服+销售+主管+董事长
SALES = WRITE | {"invite", "approve", "quote", "soft.write"}   # 软装：销售级+设计类
AUDIT = {"audit"}                       # 审计追溯（总经办：董事长/主管/财务）
BOSS = SALES | {"dispatch", "sediment", "review", "quote.approve", "audit"}
DESIGN = VIEW | {"design_plan", "soft.write"}   # 设计类角色：设计方案沉淀/软装选配
PROJECT = VIEW | {"site_report", "inspection"}   # 项目经理：工地日报/节点验收

ROLE_ACTIONS = {
    "客服": WRITE,
    "销售": SALES,
    "主管": BOSS,
    "董事长": BOSS,
    "设计总监": DESIGN,
    "创意总监": DESIGN,
    "创意总监/财务": DESIGN | AUDIT,
    "首席设计": DESIGN,
    "行政": VIEW,
    "项目经理": PROJECT,
}


def role_of(user: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT role FROM users WHERE account=?", (user,)).fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


def allowed(user: str, action: str) -> tuple:
    """返回 (是否允许, 说明)。内部账号放行。"""
    if user == "system" or user.startswith("渠道:"):
        return True, "内部操作"
    role = role_of(user)
    if role is None:
        return False, f"账号不存在或无权操作: {user}"
    if action in ROLE_ACTIONS.get(role, VIEW):
        return True, role
    return False, f"角色[{role}]无权执行[{action}]"


def require(user: str, action: str):
    ok, msg = allowed(user, action)
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(403, msg)
