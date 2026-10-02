# -*- coding: utf-8 -*-
"""从预算范本提取数据 → 灌契约线 craft_knowledge / materials 两表
来源标注：壹城精工私人定制产品-装修项目估算书2026.xlsx（用户提供，2026-09）
表结构（openpyxl 实测）：
  制安预算：A=分类/序号 B=项目名称 C=工艺说明 D=单位 E=单价 F=合计
  主材估价：A=分类/序号 B=材料名称 C=规格 D=单位 E=单价 F=合价 G=备注
  成品定制：A=分类/序号 B=品类 C=项目名称 D=工艺说明 E=单位 F=工程量 G=单价
"""
import re
import sqlite3
import openpyxl

XLSX = r"H:\AgentProjects\HomeDesignGroup\壹城精工私人定制产品-装修项目估算书2026.xlsx"
DB = r"H:\AgentProjects\HomeDesignGroup\db\homeagent.db"
SRC = "壹城精工私人定制产品-装修项目估算书2026.xlsx"

wb = openpyxl.load_workbook(XLSX, data_only=True)

CAT_RE = re.compile(r"^[一二三四五六七八九十]+、")


def is_cat(v):
    return v is not None and CAT_RE.match(str(v).strip())


def is_seq(v):
    if v is None:
        return False
    s = str(v).strip()
    return bool(re.match(r"^\d+$", s))


def num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    s = str(v).strip().replace(",", "").replace("元", "")
    m = re.match(r"^[\d.]+", s)
    return float(m.group()) if m else None


def collect_craft():
    """制安预算 → craft_knowledge（category=分区，title=项目，content=工艺做法+单价）"""
    ws = wb["制安预算"]
    items, cat = [], "制安"
    for row in ws.iter_rows(min_row=5, max_row=ws.max_row, max_col=6):
        a, b, c_, d, e = [c.value for c in row][:5]
        if is_cat(a):
            cat = str(a).strip()
            continue
        if not is_seq(a):
            continue
        title = str(b).strip() if b else ""
        content = str(c_).strip() if c_ else ""
        if not title or not content:
            continue
        unit = str(d).strip() if d else ""
        price = num(e)
        items.append({"category": cat, "title": title,
                      "content": content + (f"｜单位:{unit}｜单价:{price}元" if price else ""),
                      "source_file": f"{SRC}（制安预算）"})
    return items


def collect_main_materials():
    """主材估价 → materials（A序号 B材料名 C规格 D单位 E工程量 F单价 G合价 H备注）"""
    ws = wb["主材估价"]
    items, cat = [], "主材"
    for row in ws.iter_rows(min_row=3, max_row=ws.max_row, max_col=8):
        a, b, c_, d, e, f, g, h = [c.value for c in row][:8]
        if is_cat(a):
            cat = str(a).strip()
            continue
        if not is_seq(a):
            continue
        name = str(b).strip() if b else ""
        if not name or name.startswith(("主材", "税金", "小计")):
            continue
        items.append({"category": cat, "name": name,
                      "spec": str(c_).strip() if c_ else "",
                      "supplier": "",
                      "price": num(f), "moq": 0,
                      "tags": str(h).strip() if h else ""})
    return items


def collect_custom_materials():
    """成品定制 → materials（category=品类，name=项目名）"""
    ws = wb["成品定制"]
    items, cat = [], "成品定制"
    for row in ws.iter_rows(min_row=5, max_row=ws.max_row, max_col=8):
        a, b, c_, d, e, f, g = [c.value for c in row][:7]
        if is_cat(a):
            cat = str(a).strip()
            continue
        if not is_seq(a):
            continue
        name = str(c_).strip() if c_ else ""      # 项目名称（C 列）
        if not name or name.startswith(("成品定制", "税金", "小计")):
            continue
        items.append({"category": f"定制-{cat}", "name": name,
                      "spec": str(d).strip()[:60] if d else "",
                      "supplier": "",
                      "price": num(g) or num(f), "moq": 0,
                      "tags": ""})
    return items


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    cols = [r[1] for r in conn.execute("PRAGMA table_info(materials)")]
    if "source_file" not in cols:
        conn.execute("ALTER TABLE materials ADD COLUMN source_file TEXT")
        conn.commit()

    conn.execute("DELETE FROM craft_knowledge WHERE source_file LIKE ?", ("%估算书2026%",))
    conn.execute("DELETE FROM materials WHERE source_file LIKE ?", ("%估算书2026%",))
    conn.commit()

    crafts = collect_craft()
    mats = collect_main_materials() + collect_custom_materials()

    for c in crafts:
        conn.execute("INSERT INTO craft_knowledge (category,title,content,source_file,embedding_id) "
                     "VALUES (?,?,?,?,'')",
                     (c["category"], c["title"], c["content"], c["source_file"]))
    for m in mats:
        conn.execute("INSERT INTO materials (category,name,spec,supplier,price,moq,tags,source_file) "
                     "VALUES (?,?,?,?,?,?,?,?)",
                     (m["category"], m["name"], m["spec"], m["supplier"],
                      m["price"], m["moq"], m["tags"], f"{SRC}（主材/定制）"))
    conn.commit()

    n_c = conn.execute("SELECT COUNT(*) c FROM craft_knowledge").fetchone()["c"]
    n_m = conn.execute("SELECT COUNT(*) c FROM materials").fetchone()["c"]
    cats = [r["category"] for r in conn.execute(
        "SELECT DISTINCT category FROM craft_knowledge ORDER BY category")]
    mcats = [r["category"] for r in conn.execute(
        "SELECT DISTINCT category FROM materials ORDER BY category")]
    conn.close()
    print(f"工艺知识 craft_knowledge：灌入 {len(crafts)} 条（库内共 {n_c}）")
    print(f"  分类：{cats}")
    print(f"材料库 materials：灌入 {len(mats)} 条（库内共 {n_m}）")
    print(f"  分类：{mcats}")


if __name__ == "__main__":
    main()
