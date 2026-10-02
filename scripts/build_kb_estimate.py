# -*- coding: utf-8 -*-
"""由估算书 xlsx 生成 知识库/01-报价-壹城估算书.md（保真，数字直接来自源文件）"""
from openpyxl import load_workbook

SRC = r"H:\AgentProjects\HomeDesignGroup\壹城精工私人定制产品-装修项目估算书2026.xlsx"
OUT = r"H:\AgentProjects\HomeDesignGroup\knowledge\01-报价-壹城估算书.md"

wb = load_workbook(SRC, data_only=True)


def txt(v):
    if v is None:
        return ""
    s = str(v).strip()
    return s


def rowval(ws, r, col):
    c = ws.cell(row=r, column=col)
    return txt(c.value)


wb_cover = wb["封面"]
wb_notes = wb["预算说明"]
wb_zai = wb["制安预算"]
wb_cus = wb["成品定制"]
wb_mat = wb["主材估价"]

lines = []
A = lines.append

A("# 壹城精工 · 装修项目估算书（2026）")
A("")
A("> 来源：壹城精工私人定制产品-装修项目估算书2026.xlsx（公司预算范本，5 张表）")
A("> 用途：谈单报价问答依据｜编号：01-报价-壹城估算书")
A("")
A("## 一、封面与造价构成")
A("")
A(f"- 产品：壹城精工私人定制产品 · 装修项目估算书（{txt(wb_cover['B10'].value)} 元示例造价）")
A(f"- 构成：基础制安 {txt(wb_cover['E11'].value)} 元 / 全屋定制 {txt(wb_cover['G11'].value)} 元 / 主材 {txt(wb_cover['I11'].value)} 元")
A("- 公司：壹城装饰设计工程（湖南）有限公司")
A("- 页签：封面 / 预算说明 / 制安预算 / 成品定制 / 主材估价")
A("")

# 预算说明
A("## 二、编制说明（预算说明页）")
A("")
notes_raw = []
for r in range(2, wb_notes.max_row + 1):
    v = txt(wb_notes.cell(row=r, column=1).value)
    if v:
        notes_raw.append(v)
A("".join(notes_raw))
A("")
A("> 要点速读：① 本估算以设计平面图和客户要求为依据；② 不含二次搬运费（车辆无法直达单元楼下/电梯口时另计）；③ 材料品牌清单见下。")
A("")

# 材料品牌
A("### 制安材料品牌清单（预算说明页列示）")
A("")
brands = ["【万象】15mm欧松板", "【泰山】黄金带全功能石膏板（9.5mm）", "【都芳】超洁净味环保内墙漆",
          "【衡阳金杯】多股阻燃电线", "【伟星】环保PP-R给水管", "【中财】PVC排水管",
          "【嘉贝乐】防水涂料", "【南方】325#水泥"]
for b in brands:
    A(f"- {b}")
A("")

# 制安预算
A("## 三、制安预算（15 个分区，单位：元）")
A("")
A("| 序号 | 项目名称 | 材料/规格及工艺说明 | 单位 | 单价 | 备注/计算规则 |")
A("| --- | --- | --- | --- | --- | --- |")
cur_section = ""
for r in range(5, wb_zai.max_row + 1):
    a = txt(wb_zai.cell(row=r, column=1).value)
    b = txt(wb_zai.cell(row=r, column=2).value)
    c = txt(wb_zai.cell(row=r, column=3).value).replace("|", "／")
    d = txt(wb_zai.cell(row=r, column=4).value)
    f = txt(wb_zai.cell(row=r, column=6).value)
    g = txt(wb_zai.cell(row=r, column=7).value)
    i = txt(wb_zai.cell(row=r, column=9).value)
    e = txt(wb_zai.cell(row=r, column=5).value)
    if not b and not a:
        continue
    if not c and not d and not f and not g and not e and not i:
        # 分区标题或 空序号行
        if a.startswith(("一、", "二、", "三、", "四、", "五、", "六、", "七、", "八、", "九、", "十、", "十一", "十二", "十三", "十四", "十五")):
            A("")
            A(f"### {a}")
            A("")
        elif "小计" in str(b):
            A(f"- **{b}**：{g} 元")
        elif b.startswith(("制安工程直接费", "制安工程管理费", "制安工程总价")):
            note = f"（{c}）" if c else ""
            A(f"- **{b}{note}**：{g} 元")
        continue
    if a.startswith(("一、", "二、", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二", "十三", "十四", "十五")):
        A("")
        A(f"### {a}")
        A("")
        continue
    remark = i if i else ""
    if not f:
        f = "—"
    A(f"| {a} | {b} | {c} | {d} | {f} | {remark} |")
A("")
A("> 计价链：各分部小计 → 制安工程直接费 → 制安工程管理费（直接费×10%）→ 制安工程总价（直接费+管理费）。")
A("")

# 成品定制
A("## 四、成品定制（全屋定制，单位：元）")
A("")
A("| 序号 | 品类 | 项目名称 | 项目特征及工艺备注 | 单位 | 单价 |")
A("| --- | --- | --- | --- | --- | --- |")
cat = ""
for r in range(5, wb_cus.max_row + 1):
    a = txt(wb_cus.cell(row=r, column=1).value)
    b = txt(wb_cus.cell(row=r, column=2).value)
    c = txt(wb_cus.cell(row=r, column=3).value)
    d = txt(wb_cus.cell(row=r, column=4).value).replace("|", "／")
    e = txt(wb_cus.cell(row=r, column=5).value)
    g = txt(wb_cus.cell(row=r, column=7).value)
    if not c:
        continue
    if c.startswith(("成品定制", "税金")):
        note = txt(wb_cus.cell(row=r, column=4).value).replace("|", "／")
        h = txt(wb_cus.cell(row=r, column=8).value)
        A(f"- **{c}**：{h or g} 元（{note}）")
        continue
    if b and b != cat:
        cat = b
        A(f"- **品类：{b}**")
    A(f"  - {a and a + '、' or ''}{c}：{g} 元/{e}（{d}）")
A("")
A("> 计价链：成品定制直接费 → 管理费（直接费×10%）→ 税金（(直接费+管理费)×3%，业主需开票另计）→ 成品定制总价。")
A("")

# 主材估价
A("## 五、主材估价（单位：元）")
A("")
A("| 序号 | 材料名称 | 规格 | 单位 | 单价 | 备注 | 计算规则 |")
A("| --- | --- | --- | --- | --- | --- | --- |")
sec = ""
for r in range(5, wb_mat.max_row + 1):
    a = txt(wb_mat.cell(row=r, column=1).value)
    b = txt(wb_mat.cell(row=r, column=2).value)
    c = txt(wb_mat.cell(row=r, column=3).value).replace("|", "／")
    d = txt(wb_mat.cell(row=r, column=4).value)
    f = txt(wb_mat.cell(row=r, column=6).value)
    h = txt(wb_mat.cell(row=r, column=8).value).replace("|", "／")
    j = txt(wb_mat.cell(row=r, column=10).value).replace("|", "／")
    if not b and not a:
        continue
    if a.startswith(("一、", "二、", "三", "四", "五", "六", "七", "八", "九")):
        sec = a
        A("")
        A(f"### {a}")
        A("")
        continue
    if b.startswith(("主材直接费", "主材采保费", "主材总价")):
        A(f"- **{b}**：{f or g} 元")
        continue
    A(f"| {a} | {b} | {c} | {d} | {f} | {h} | {j} |")
A("")
A("> 计价链：主材直接费 → 主材采保费 → 主材总价。损耗：地/墙砖 8%（750×1500 等大板 10%）、踢脚线/地板 5%；单户不足量另加小单费（金属踢脚线<35m +200、强化地板<25㎡ +200）。")
A("")
A("## 六、报价问答速查要点")
A("")
A("- 造价 = 基础制安 + 全屋定制 + 主材（封面构成，示例 1540 元为占位）")
A("- 制安管理费 10%、成品定制管理费 10%、税金 3%（开票另计）")
A("- 必算项目：安全文明施工设施费(450/户)、成品保护(5/㎡)、墙固顶固(4.5/㎡)、地锢(3.5/㎡)、立体放线(6.5/㎡)")
A("- 按建筑外框面积计：水电改造(118/㎡)、复式增加费(15/㎡)、别墅增加费(25/㎡)等")
A("- 远程费：长沙绕城高速环内免收，环外 1000 元/户起；二次搬运费按实际情况收")
A("- 暂未估价：灯具/浴霸/凉霸、强电箱弱电箱、卫浴五金、墙纸墙布软包硬包、封窗、家具软装窗帘、电器设备")
A("- 主材品牌：万象欧松板/泰山石膏板/都芳内墙漆/衡阳金杯电线/伟星PP-R/中财PVC/嘉贝乐防水/南方水泥")

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))

print("生成完成:", OUT)
print("总行数:", len(lines))
