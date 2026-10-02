# -*- coding: utf-8 -*-
"""demo_agents.py — Step 6 自检：三个 MVP Sub-agent 各跑通 demo case"""
import sys

sys.path.insert(0, r"H:\AgentProjects\HomeDesignGroup\src")

from agents.craft_qa_agent import CraftQaAgent
from agents.quote_agent import QuoteAgent
from agents.site_report_agent import SiteReportAgent
from models.core import connect

fails = []


def check(name, cond, msg):
    if not cond:
        fails.append(name)
        print(f"[FAIL] {name}: {msg}")
    else:
        print(f"[PASS] {name}")


# ---- 前置 seed（幂等：先清理再插入） ----
conn = connect()
conn.execute("DELETE FROM craft_knowledge WHERE title LIKE 'demo%'")
conn.execute("DELETE FROM materials WHERE name LIKE 'demo%'")
conn.execute("DELETE FROM owners WHERE wechat_id LIKE 'demo_%'")
conn.execute("INSERT INTO craft_knowledge (category,title,content,source_file,embedding_id) "
             "VALUES ('降噪隔墙','demo-轻钢龙骨双层石膏板','轻钢龙骨+岩棉+双层石膏板，隔声45dB',"
             "'knowledge/02-工艺-隐蔽工程验收.md','')")
conn.execute("INSERT INTO craft_knowledge (category,title,content,source_file,embedding_id) "
             "VALUES ('防水','demo-卫生间防水','丙纶布+涂料双道防水，闭水48小时',"
             "'knowledge/02-工艺-隐蔽工程验收.md','')")
conn.execute("INSERT INTO materials (category,name,spec,supplier,price,moq,tags) "
             "VALUES ('岩板','demo-佛山白岩板','1200x2700mm','佛山厂商A',260,10,'台面')")
conn.execute("INSERT INTO materials (category,name,spec,supplier,price,moq,tags) "
             "VALUES ('石膏板','demo-龙牌石膏板','1200x2400mm','龙牌',35,50,'隔墙')")
conn.execute("INSERT INTO owners (wechat_id,nickname,community,house_area,layout_json,"
             "budget_total,budget_used,style_preference) "
             "VALUES ('demo_wx_1','演示业主','保利和光尘樾',189,'{\"rooms\":4}',800000,120000,'新中式')")
conn.commit()
oid = conn.execute("SELECT id FROM owners WHERE wechat_id='demo_wx_1'").fetchone()["id"]
conn.close()

# ---- Agent1 工艺问答 ----
qa = CraftQaAgent()
ans = qa.answer("降噪隔墙怎么做", user="客服")
check("工艺问答：命中工艺条目", len(ans["craft"]) >= 1 and
      any("轻钢龙骨" in c["title"] for c in ans["craft"]), f"craft={ans['craft']}")
check("工艺问答：带来源", all("source" in c for c in ans["craft"]), "缺 source")
check("工艺问答：材料参考价", isinstance(ans["materials"], list), f"materials={ans['materials']}")

# ---- Agent2 报价单 ----
qa2 = QuoteAgent()
quote = qa2.build_quote(oid, "全屋硬装", category="岩板")
check("报价单：列项严格（项目/规格/单位/数量/单价/合价/备注）",
      quote["columns"] == ["项目", "规格", "单位", "数量", "单价", "合价", "备注"],
      f"columns={quote['columns']}")
check("报价单：含行数据且合价=数量×单价",
      quote["row_count"] >= 1 and
      all(r[5] == round(r[3] * r[4], 2) for r in quote["rows"]), f"rows={quote['rows'][:1]}")
check("报价单：草稿态不自动发", quote["status"] == "draft", f"status={quote['status']}")

# ---- Agent3 工地日报 ----
sr = SiteReportAgent()
rep = sr.build_report("保利和光尘樾-189户型", photo_desc="木工吊顶龙骨完成",
                      image_bytes=b"fake-site-photo")
check("工地日报：OCR+模板生成", len(rep["photo_ocr"]) > 0 and "木工" in rep["progress_summary"],
      f"ocr={rep['photo_ocr']} summary={rep['progress_summary']}")
check("工地日报：草稿进 pending_human", rep["status"] == "pending_human", f"status={rep['status']}")
sres = sr.send_report(rep)
check("工地日报：对外发送被 Sentinel 拦截（pending）",
      sres.get("pending") is True and sres.get("ok") is False, f"res={sres}")

# ---- 清理 seed 数据 ----
conn = connect()
conn.execute("DELETE FROM craft_knowledge WHERE title LIKE 'demo%'")
conn.execute("DELETE FROM materials WHERE name LIKE 'demo%'")
conn.execute("DELETE FROM owners WHERE wechat_id LIKE 'demo_%'")
conn.commit()
conn.close()
print("清理完成")

print("\n" + ("全部通过" if not fails else f"{len(fails)} 项失败"))
sys.exit(1 if fails else 0)
