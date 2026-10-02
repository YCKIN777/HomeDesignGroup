# -*- coding: utf-8 -*-
"""import_quote_template.py — 预算范本 xlsx → quote_templates（幂等）

解析三 sheet：制安预算 / 成品定制 / 主材估价 → 结构化报价模板条目。
幂等：先清空 quote_templates 再导入（模板是配置资产，整库重建安全）。
"""
import sqlite3
import sys
from openpyxl import load_workbook

ROOT = r"H:\AgentProjects\HomeDesignGroup"
XLSX = ROOT + r"\壹城精工私人定制产品-装修项目估算书2026.xlsx"
DB = ROOT + r"\db\壹城精工.db"

wb = load_workbook(XLSX, data_only=True)


def num(v):
    """兼容 单价 数字/字符串/None"""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def clean(v):
    if v is None:
        return ""
    s = str(v).replace("\n", " ").strip()
    return s


def is_section(a, b):
    """分类行：A 列以 一、二、三… 或含 类 字开头，且无序号"""
    return clean(a)[:1] in "一二三四五六七八九十" and "、" in clean(a)[:3]


def parse_zian(ws):
    """制安预算：r3 表头(序号|项目名称|工艺|单位|工程量|单价|合计) r5+ 数据"""
    rows = []
    sec = ""
    for i, row in enumerate(ws.iter_rows(min_row=5, values_only=True), start=5):
        a, b, c, d, e, f, g = (row + (None,) * 7)[:7]
        if a is None and b is None:
            continue
        if is_section(a, b):
            sec = clean(a)
            continue
        if clean(a).isdigit() or b:
            rows.append({"section": sec, "item": clean(b), "spec": clean(c),
                         "unit": clean(d), "unit_price": num(f), "source": "制安预算",
                         "sort": i})
    return rows


def parse_dz(ws):
    """成品定制：r3 表头(序号|品类|项目名称|工艺|单位|工程量|单价|合计) r5+ 数据"""
    rows = []
    sec = ""
    for i, row in enumerate(ws.iter_rows(min_row=5, values_only=True), start=5):
        a, b, c, d, e, f, g, h = (row + (None,) * 8)[:8]
        if a is None and b is None and c is None:
            continue
        if clean(b) and not clean(a).isdigit():
            sec = clean(b)
        item = clean(c) or clean(b)
        if not item:
            continue
        rows.append({"section": sec, "item": item, "spec": clean(d),
                     "unit": clean(e), "unit_price": num(g), "source": "成品定制",
                     "sort": i})
    return rows


def parse_zc(ws):
    """主材估价：r3 表头(序号|材料名称|规格|单位|工程量|单价|合价|备注) r4+ 数据"""
    rows = []
    sec = ""
    for i, row in enumerate(ws.iter_rows(min_row=4, values_only=True), start=4):
        a, b, c, d, e, f, g, h = (row + (None,) * 8)[:8]
        if a is None and b is None:
            continue
        if is_section(a, b):
            sec = clean(a)
            continue
        if clean(a).isdigit() or b:
            rows.append({"section": sec, "item": clean(b), "spec": clean(c),
                         "unit": clean(d), "unit_price": num(f), "source": "主材估价",
                         "sort": i})
    return rows


all_rows = parse_zian(wb["制安预算"]) + parse_dz(wb["成品定制"]) + parse_zc(wb["主材估价"])

conn = sqlite3.connect(DB)
conn.execute("DELETE FROM quote_templates")
conn.executemany(
    "INSERT INTO quote_templates(section, item, spec, unit, unit_price, source, sort) "
    "VALUES(:section,:item,:spec,:unit,:unit_price,:source,:sort)", all_rows)
conn.commit()
n = conn.execute("SELECT COUNT(*) FROM quote_templates").fetchone()[0]
by_src = dict(conn.execute("SELECT source, COUNT(*) FROM quote_templates "
                           "GROUP BY source").fetchall())
conn.close()

print(f"[import] quote_templates 共 {n} 条：{by_src}")
print(f"[import] 有单价条目 {sum(1 for r in all_rows if r['unit_price'] > 0)} / 总 {len(all_rows)}")
