# -*- coding: utf-8 -*-
"""quote_agent.py — MVP Sub-agent 2：报价单生成 Agent（架构契约 Step 6）

业主报户型+需求 → 拉 owners 档案（户型/预算）→ 按需拉 materials → 出 Excel 格式
清单（列项严格：项目/规格/单位/数量/单价/合价/备注）。不自动发送（Sentinel draft，
后续外部发送须人工点"发送"）。Excel 导出留接口（未来落 .xlsx）。
"""
from models.core import connect
from providers.factory import get_providers
from kernel.llm_enhance import llm_enhance


class QuoteAgent:
    # 报价清单列项（契约列项，顺序不可改）
    COLUMNS = ["项目", "规格", "单位", "数量", "单价", "合价", "备注"]

    def __init__(self, user: str = "销售"):
        self.user = user
        self.providers = get_providers()

    def get_owner(self, owner_id: int) -> dict:
        with connect() as conn:
            r = conn.execute("SELECT * FROM owners WHERE id=?", (owner_id,)).fetchone()
        if not r:
            raise ValueError(f"业主 {owner_id} 不存在")
        return dict(r)

    def pick_materials(self, category: str = "", budget_hint: float = 0.0) -> list:
        """按需求拉建材（materials 表；预算充足时优先高单价条目）"""
        with connect() as conn:
            rows = conn.execute(
                "SELECT * FROM materials WHERE 1=1"
                + (" AND category LIKE ?" if category else "")
                + " ORDER BY price DESC LIMIT 15",
                (f"%{category}%",) if category else ()).fetchall()
        return [dict(r) for r in rows]

    def build_quote(self, owner_id: int, requirements: str = "", category: str = "") -> dict:
        """生成报价清单草稿（严格按 COLUMNS 列项）"""
        owner = self.get_owner(owner_id)
        mats = self.pick_materials(category, owner.get("budget_total", 0.0))
        rows = []
        for m in mats[:8]:                       # 演示取前 8 条
            qty = 1.0
            price = m.get("price") or 0.0        # 未估价条目按 0 计并标注待估价
            total = round(price * qty, 2)
            remark = ("待估价" if not m.get("price") else (m["tags"] or ""))
            rows.append([m["name"], m["spec"], "项", qty, price, total, remark])
        total_all = round(sum(r[5] for r in rows), 2)
        # LLM 增强（可选层）：报价构成说明 + 预算提醒；未配 key 自动降级
        import json
        enhance = llm_enhance(
            self.providers,
            "你是家装报价顾问。基于业主预算与报价清单，给出 2-3 句专业说明："
            "报价构成、与预算的差距、需人工复核的价格项。不编造清单外的价格。",
            f"业主档案：{owner.get('nickname')} @ {owner.get('community')}，"
            f"户型 {owner.get('layout_json')}，预算 {owner.get('budget_total')} 元\n"
            f"报价清单（项目/规格/数量/单价/合价）：\n"
            + "\n".join(f"{r[0]}｜{r[1]}｜{r[3]}｜{r[4]}｜{r[5]}" for r in rows))
        return {
            "owner": f"{owner.get('nickname')}@{owner.get('community')} 户型{owner.get('layout_json')} "
                     f"预算{owner.get('budget_total')}",
            "requirements": requirements,
            "columns": self.COLUMNS,
            "rows": rows,
            "row_count": len(rows),
            "total": total_all,
            "llm_note": enhance,
            "status": "draft", "sentinel": "draft 放行（不自动发送；发送须人工确认）",
            "excel_hint": "导出 .xlsx 接口预留（列项：项目/规格/单位/数量/单价/合价/备注）",
        }
