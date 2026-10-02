# -*- coding: utf-8 -*-
"""after_sales_agent.py — 售后部 Agent（编队计划 v3 · P7）

职责：质保登记（整体2年/防水10年）+ 售后工单 + 回访 SOP。
数据：after_sales 表。
对外闸门：质保认定/赔付动作人工确认（CLI 演示通道不设，Web/API 强制）。
"""
from datetime import datetime, timedelta

from db import get_conn, audit
from kernel import config_loader
from agents.base import BaseAgent

AS_KINDS = ["质保登记", "售后工单", "回访"]
AS_STATUS = ["待处理", "处理中", "已关闭"]


class AfterSalesAgent(BaseAgent):
    name = "after_sales"
    role = "售后部（质保/工单/回访）"
    capabilities = [
        "质保登记（整体2年/防水10年，按竣工日期算截止）",
        "售后工单创建/处理/关闭",
        "回访 SOP（竣工后 30/90/365 天节点待办）",
        "质保到期前提醒",
    ]

    def __init__(self):
        self.cfg = config_loader.load_profile("壹城精工")
        w = self.cfg["rules"].get("warranty", {"years": 2, "waterproof_years": 10})
        self.years = w["years"]
        self.waterproof_years = w["waterproof_years"]

    # ---------- 质保登记 ----------
    def register_warranty(self, user, project_id, base_date=""):
        """竣工日 + 年限 → 质保截止。未给竣工日则用今天。登记整体+防水两条。"""
        with get_conn() as conn:
            p = conn.execute(
                "SELECT id, customer_id, status FROM projects WHERE id=?", (project_id,)).fetchone()
            if not p:
                raise ValueError("项目 %d 不存在" % project_id)
        base = datetime.strptime(base_date, "%Y-%m-%d") if base_date else datetime.now()
        rows = []
        for wt, years in (("整体", self.years), ("防水", self.waterproof_years)):
            try:
                until_d = base.replace(year=base.year + years)
            except ValueError:  # 2/29 落在非闰年 → 取 2/28
                until_d = base.replace(year=base.year + years, month=2, day=28)
            until = until_d.strftime("%Y-%m-%d")
            with get_conn() as conn:
                cur = conn.execute(
                    "INSERT INTO after_sales(project_id, customer_id, kind, title, content, "
                    "status, warranty_type, warranty_until, created_by) "
                    "VALUES(?,?,?,?,?,?,?,?,?)",
                    (project_id, p["customer_id"], "质保登记",
                     "质保登记-" + wt, "整体%d年/防水%d年配置" % (self.years, self.waterproof_years),
                     "已关闭", wt, until, user))
                rid = cur.lastrowid
                audit(user, "质保登记", "after_sales#%d" % rid,
                      after="project=%d %s→%s" % (project_id, wt, until))
            rows.append({"id": rid, "warranty_type": wt, "warranty_until": until})
        return {"project_id": project_id, "base_date": base.strftime("%Y-%m-%d"), "rows": rows}

    # ---------- 售后工单 ----------
    def create_ticket(self, user, project_id, title, content="", assignee=""):
        with get_conn() as conn:
            p = conn.execute(
                "SELECT id, customer_id FROM projects WHERE id=?", (project_id,)).fetchone()
            if not p:
                raise ValueError("项目 %d 不存在" % project_id)
            cur = conn.execute(
                "INSERT INTO after_sales(project_id, customer_id, kind, title, content, "
                "status, assignee, created_by) VALUES(?,?,?,?,?,?,?,?)",
                (project_id, p["customer_id"], "售后工单", title, content, "待处理", assignee, user))
            tid = cur.lastrowid
            audit(user, "售后工单", "after_sales#%d" % tid, after=title[:60])
        return {"id": tid, "project_id": project_id, "title": title, "status": "待处理"}

    def list(self, project_id=None, kind=""):
        with get_conn() as conn:
            sql = "SELECT * FROM after_sales WHERE 1=1"
            params = []
            if project_id:
                sql += " AND project_id=?"
                params.append(project_id)
            if kind:
                sql += " AND kind=?"
                params.append(kind)
            sql += " ORDER BY id DESC LIMIT 50"
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def update_status(self, user, ticket_id, status, result=""):
        if status not in AS_STATUS:
            raise ValueError("状态须为 " + "/".join(AS_STATUS) + "（收到 " + status + "）")
        with get_conn() as conn:
            row = conn.execute("SELECT status FROM after_sales WHERE id=?", (ticket_id,)).fetchone()
            if not row:
                raise ValueError("售后记录 %d 不存在" % ticket_id)
            conn.execute("UPDATE after_sales SET status=?, result=? WHERE id=?",
                         (status, result, ticket_id))
            audit(user, "售后状态", "after_sales#%d" % ticket_id,
                  before=row["status"], after=status + (":" + result if result else ""))
        return {"id": ticket_id, "status": status, "result": result}

    # ---------- 回访 SOP ----------
    def check_due(self):
        """回访节点：竣工（项目到'竣工'）后 30/90/365 天待办；质保到期前 90 天提醒。
        幂等：同项目同类未完成待办不重复。"""
        with get_conn() as conn:
            projects = conn.execute(
                "SELECT p.id, p.customer_id, p.status FROM projects p "
                "WHERE p.status IN ('竣工','售后')").fetchall()
            created = []
            for p in projects:
                visits = [(30, "回访-竣工30天"), (90, "回访-竣工90天"), (365, "回访-竣工365天")]
                for days, task in visits:
                    exists = conn.execute(
                        "SELECT id FROM todos WHERE customer_id=? AND task=? AND done=0",
                        (p["customer_id"], task)).fetchone()
                    if not exists:
                        conn.execute(
                            "INSERT INTO todos(customer_id, task, due_at) VALUES(?,?,"
                            "datetime('now','localtime','+%d days'))" % days,
                            (p["customer_id"], task))
                        created.append(task)
            # 质保到期前 90 天提醒（防水 10 年不设提醒，只提醒整体质保）
            warns = conn.execute(
                "SELECT project_id, customer_id, warranty_until FROM after_sales "
                "WHERE kind='质保登记' AND warranty_type='整体' AND warranty_until != '' "
                "AND warranty_until <= date('now','localtime','+90 days')").fetchall()
            for w in warns:
                exists = conn.execute(
                    "SELECT id FROM todos WHERE customer_id=? AND task=? AND done=0",
                    (w["customer_id"], "质保到期提醒:" + w["warranty_until"])).fetchone()
                if not exists:
                    conn.execute(
                        "INSERT INTO todos(customer_id, task) VALUES(?,?)",
                        (w["customer_id"], "质保到期提醒:" + w["warranty_until"]))
                    created.append("质保到期提醒")
        return created

    def handle(self, ctx, message):
        return self.todo("售后 Agent：register_warranty/create_ticket/list/update_status/check_due")
