# -*- coding: utf-8 -*-
"""material_agent.py — 材料 Agent（编队计划 v3 · P5，硬装主材）

职责：主材/硬装材料选型 + 材料清单生成（浅版，不做采购/比价）。
数据：materials 材料库（homeagent.db，契约线共享）+ 报价单主材 section（壹城精工.db）。
对外闸门：首版只读 + 出清单，无对外动作。
"""
from db import get_conn
from agents.base import BaseAgent


class MaterialAgent(BaseAgent):
    name = "material"
    role = "材料（主材选型+清单）"
    capabilities = [
        "材料库检索（materials：规格/单价/供应商/标签）",
        "从报价单主材 section 生成材料清单",
        "按分类汇总材料清单（小计+合计）",
    ]

    # ---------- 材料库检索（homeagent.db materials） ----------
    def list_materials(self, category: str = "", keyword: str = "", limit: int = 20) -> list:
        from models.core import connect
        with connect() as conn:
            sql = ("SELECT name, category, spec, price, supplier, tags FROM materials WHERE 1=1")
            params = []
            if category:
                sql += " AND category LIKE ?"
                params.append(f"%{category}%")
            if keyword:
                sql += " AND (name LIKE ? OR spec LIKE ? OR tags LIKE ?)"
                params += [f"%{keyword}%"] * 3
            sql += " ORDER BY category, name LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # ---------- 报价单主材清单（壹城精工.db quote_items 主材类 section） ----------
    # 预算范本 section 按品类命名（大理石类/瓷砖类/木地板/定制橱柜/洁具/铝合金玻璃门/铝扣板/开关插座/暂未估价项目），
    # 主材口径 = 上述品类的并集（对应客户主材 800-1500 元/㎡ 的自购/含装口径）。
    MAIN_MATERIAL_SECTIONS = [
        "大理石", "瓷砖", "木地板", "金属踢脚线", "定制橱柜", "洁具",
        "铝合金", "铝扣板", "开关插座", "暂未估价",
    ]

    def build_material_list(self, quote_id: int) -> dict:
        """从报价单提取主材类 section 明细，按项小计 + 合计"""
        with get_conn() as conn:
            q = conn.execute("SELECT id, project_id, total FROM quotes WHERE id=?",
                             (quote_id,)).fetchone()
            if not q:
                raise ValueError(f"报价 {quote_id} 不存在")
            where = " OR ".join(["section LIKE ?"] * len(self.MAIN_MATERIAL_SECTIONS))
            items = conn.execute(
                f"SELECT id, item AS name, spec, unit, qty, unit_price, amount, est "
                f"FROM quote_items WHERE quote_id=? AND ({where}) ORDER BY section, sort, id",
                [quote_id] + [f"%{k}%" for k in self.MAIN_MATERIAL_SECTIONS]).fetchall()
        rows = [dict(r) for r in items]
        total = sum(r["amount"] or 0 for r in rows)
        return {"quote_id": quote_id, "project_id": q["project_id"],
                "items_count": len(rows), "est_items": sum(1 for r in rows if r["est"]),
                "material_total": round(total, 2), "items": rows}

    def handle(self, ctx, message: str):
        return self.todo("材料 Agent：list_materials/build_material_list")
