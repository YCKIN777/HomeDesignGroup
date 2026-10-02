# -*- coding: utf-8 -*-
"""生成 报价速查表（按面积套算造价区间）：knowledge md + CSV"""
import csv

# 壹城报价口径（2026-09-30 用户提供）
BANDS = [
    ("制安造价", 800, 1500),
    ("主材", 800, 1500),
    ("家具软装", 500, 1500),
    ("电器", 0, 0),     # 业主自购
    ("设备", 0, 0),     # 业主自购
]
AREAS = [80, 90, 100, 110, 120, 128, 140, 160, 180, 189, 200, 220, 240]

KB_PATH = r"H:\AgentProjects\HomeDesignGroup\knowledge\01-报价-按面积套算速查表.md"
CSV_PATH = r"H:\AgentProjects\HomeDesignGroup\input\报价速查表-按面积套算.csv"

low_za, high_za = BANDS[0][1], BANDS[0][2]   # 制安
low_zc, high_zc = BANDS[1][1], BANDS[1][2]   # 主材
low_rj, high_rj = BANDS[2][1], BANDS[2][2]   # 家具软装
low_all = low_za + low_zc + low_rj           # 2100
high_all = high_za + high_zc + high_rj       # 4500

lines = []
A = lines.append
A("# 壹城精工 · 报价速查表（按面积套算造价区间）")
A("")
A("> 口径（壹城 2026-09-30 提供）：制安 800-1500 元/㎡、主材 800-1500 元/㎡、家具软装 500-1500 元/㎡；电器、设备业主自购。")
A("> 面积按**建筑外框面积**计（与估算书口径一致）；区间为全包综合口径，含制安管理费；估算偏差 ≤8%，最终以公司报价为准。")
A("")
A("## 套算规则")
A("")
A(f"- 全包合计（不含电器/设备）＝ 制安 + 主材 + 家具软装 ＝ **{low_all}-{high_all} 元/㎡**（中值约 3300 元/㎡）")
A("- 制安 = 面积 × 800-1500 元/㎡（中值 1150）；主材同 800-1500（中值 1150）；家具软装 = 面积 × 500-1500（中值 1000）")
A("- 电器、设备：业主自购，不计入套算；如需代购另行报价")
A("")
A("## 常见面积速查表（万元）")
A("")
A("| 面积(㎡) | 制安(万) | 主材(万) | 家具软装(万) | 全包合计(万) |")
A("| --- | --- | --- | --- | --- |")
rows = []
for s in AREAS:
    za_low, za_high = s * low_za / 10000, s * high_za / 10000
    zc_low, zc_high = s * low_zc / 10000, s * high_zc / 10000
    rj_low, rj_high = s * low_rj / 10000, s * high_rj / 10000
    all_low, all_high = s * low_all / 10000, s * high_all / 10000
    rows.append((s, za_low, za_high, zc_low, zc_high, rj_low, rj_high, all_low, all_high))
    A(f"| {s} | {za_low:.1f}-{za_high:.1f} | {zc_low:.1f}-{zc_high:.1f} | {rj_low:.1f}-{rj_high:.1f} | {all_low:.1f}-{all_high:.1f} |")
A("")
A("## 示例口径")
A("")
ex = 140
za_l, za_h = ex * low_za / 10000, ex * high_za / 10000
zc_l, zc_h = ex * low_zc / 10000, ex * high_zc / 10000
rj_l, rj_h = ex * low_rj / 10000, ex * high_rj / 10000
al_l, al_h = ex * low_all / 10000, ex * high_all / 10000
A(f"- {ex}㎡ 户型：制安 {za_l:.1f}-{za_h:.1f} 万 + 主材 {zc_l:.1f}-{zc_h:.1f} 万 + 家具软装 {rj_l:.1f}-{rj_h:.1f} 万 ≈ 全包 **{al_l:.1f}-{al_h:.1f} 万**（不含电器/设备）")
A("- 低价口径（简装/基础套餐）：2100 元/㎡；高价口径（高品质定制）：4500 元/㎡；一般改善型取中值约 3300 元/㎡")
A("- 谈单话术参考：\"140 平改善型全包大概 40-50 万区间，具体看主材档位和定制量，估算书按实际平面图出\"")
A("")
A("## 注意")
A("")
A("1. 面积口径为建筑外框面积；套内/实际施工面积会更高单价")
A("2. 远程费（绕城环外 1000 起）、二次搬运、物业费、税金（开票另计）不在此区间内")
A("3. 估算偏差 ≤8%（估算书编制说明）；大平层/复式/别墅另有水电增加费（15/25 元/㎡）")

with open(KB_PATH, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))
print("KB:", KB_PATH, len(lines), "lines")

with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["面积(㎡)", "制安低(万)", "制安高(万)", "主材低(万)", "主材高(万)",
                "家具软装低(万)", "家具软装高(万)", "全包合计低(万)", "全包合计高(万)"])
    for (s, za_l, za_h, zc_l, zc_h, rj_l, rj_h, al_l, al_h) in rows:
        w.writerow([s, round(za_l, 1), round(za_h, 1), round(zc_l, 1), round(zc_h, 1),
                    round(rj_l, 1), round(rj_h, 1), round(al_l, 1), round(al_h, 1)])
print("CSV:", CSV_PATH, len(rows), "rows")
