# -*- coding: utf-8 -*-
"""soft_furnishing_agent.py — 软装部 Agent（编队计划 v3 · P6）

职责：家具/灯具/窗帘/布艺/装饰等软装细项配置 + 软装清单生成。
数据：soft_furnishings 表（项目维度，分类小计+合计）。
对外闸门：软装清单出给客户前人工确认（CLI 演示通道不设，Web/API 强制）。
"""
from db import get_conn, audit
from agents.base import BaseAgent

SOFT_CATEGORIES = ["家具", "灯具", "窗帘", "布艺", "装饰", "其他"]
SOFT_STATUS = ["待确认", "已确认", "已下单"]


class SoftFurnishingAgent(BaseAgent):
    name = "soft_furnishing"
    role = "软装部（家具/灯具/窗帘/布艺）"
    capabilities = [
        "软装细项录入（分类/品名/规格/数量/单价）",
        "软装清单按分类汇总（小计+合计）",
        "状态流转（待确认→已确认→已下单）",
    ]

    @staticmethod
    def _validate(category: str):
        if category not in SOFT_CATEGORIES:
            raise ValueError("软装分类须为 " + "/".join(SOFT_CATEGORIES) + "（收到 " + category + "）")

    def add_item(self, user, project_id, category, name, spec="", qty=1.0,
                 unit_price=0.0, note=""):
        self._validate(category)
        with get_conn() as conn:
            if not conn.execute("SELECT id FROM projects WHERE id=?", (project_id,)).fetchone():
                raise ValueError("项目 %d 不存在" % project_id)
            amount = round(qty * unit_price, 2)
            cur = conn.execute(
                "INSERT INTO soft_furnishings(project_id,category,name,spec,qty,unit_price,"
                "amount,note,created_by) VALUES(?,?,?,?,?,?,?,?,?)",
                (project_id, category, name, spec, qty, unit_price, amount, note, user))
            sid = cur.lastrowid
            audit(user, "软装录入", "soft_furnishings#%d" % sid,
                  after="project=%d %s %s" % (project_id, category, name))
        return {"id": sid, "project_id": project_id, "category": category, "name": name,
                "qty": qty, "unit_price": unit_price, "amount": amount}

    def update_item(self, user, item_id, **fields):
        allowed = {"category", "name", "spec", "qty", "unit_price", "status", "note"}
        upd = {k: v for k, v in fields.items() if k in allowed and v not in (None, "")}
        if "category" in upd:
            self._validate(upd["category"])
        if "status" in upd and upd["status"] not in SOFT_STATUS:
            raise ValueError("状态须为 " + "/".join(SOFT_STATUS) + "（收到 " + upd["status"] + "）")
        with get_conn() as conn:
            row = conn.execute("SELECT * FROM soft_furnishings WHERE id=?", (item_id,)).fetchone()
            if not row:
                raise ValueError("软装项 %d 不存在" % item_id)
            if not upd:
                return dict(row)
            sets, vals = [], []
            for k, v in upd.items():
                sets.append(k + "=?")
                vals.append(v)
            if {"qty", "unit_price"} & set(upd):
                cur = dict(row)
                sets.append("amount=?")
                vals.append(round((upd.get("qty", cur["qty"])) * (upd.get("unit_price", cur["unit_price"])), 2))
            conn.execute("UPDATE soft_furnishings SET " + ",".join(sets) + " WHERE id=?",
                         vals + [item_id])
            audit(user, "软装更新", "soft_furnishings#%d" % item_id,
                  after=";".join(k + "=" + str(v) for k, v in upd.items()))
            fresh = conn.execute("SELECT * FROM soft_furnishings WHERE id=?", (item_id,)).fetchone()
        return dict(fresh)

    def remove_item(self, user, item_id):
        with get_conn() as conn:
            row = conn.execute("SELECT id FROM soft_furnishings WHERE id=?", (item_id,)).fetchone()
            if not row:
                raise ValueError("软装项 %d 不存在" % item_id)
            conn.execute("DELETE FROM soft_furnishings WHERE id=?", (item_id,))
            audit(user, "软装删除", "soft_furnishings#%d" % item_id)
        return {"id": item_id, "deleted": True}

    def list_items(self, project_id):
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT id,category,name,spec,qty,unit_price,amount,status,note,created_by "
                "FROM soft_furnishings WHERE project_id=? ORDER BY category, id",
                (project_id,)).fetchall()
        return [dict(r) for r in rows]

    def build_soft_list(self, project_id):
        rows = self.list_items(project_id)
        groups = {}
        for r in rows:
            groups.setdefault(r["category"], []).append(r)
        sections = []
        for cat in SOFT_CATEGORIES:
            if cat not in groups:
                continue
            sub = round(sum(x["amount"] or 0 for x in groups[cat]), 2)
            sections.append({"category": cat, "count": len(groups[cat]),
                             "subtotal": sub, "items": groups[cat]})
        total = round(sum(x["amount"] or 0 for x in rows), 2)
        return {"project_id": project_id, "items_count": len(rows),
                "total": total, "sections": sections}

    def handle(self, ctx, message):
        return self.todo("软装 Agent：add_item/update_item/remove_item/list_items/build_soft_list")
