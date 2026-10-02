# -*- coding: utf-8 -*-
"""check_ontology_export.py — Step 4.9 自检：三格式语义导出内容核对"""
import json
import os
import sys
import xml.dom.minidom

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kernel.config_loader import load_profile

cfg = load_profile("壹城精工")
N_TERMS = len(cfg["terms"])
N_STAGES = len(cfg["workflow"]["backbone"])
N_REL = 5

ROOT = r"H:\AgentProjects\HomeDesignGroup"
EXPORT_DIR = os.path.join(ROOT, "company_profiles", "壹城精工", "ontology-export")

fails = []


def check(name, cond, msg):
    if not cond:
        fails.append(name)
        print(f"[FAIL] {name}: {msg}")
    else:
        print(f"[PASS] {name}")


# 1. 文件存在非空
for fn in ("ontology.jsonld", "ontology.rdf", "ontology.ttl"):
    p = os.path.join(EXPORT_DIR, fn)
    check(f"{fn} 存在非空", os.path.exists(p) and os.path.getsize(p) > 300, f"{p} 缺失或过小")

# 2. JSON-LD 结构与计数
with open(os.path.join(EXPORT_DIR, "ontology.jsonld"), "r", encoding="utf-8") as f:
    jld = json.load(f)
check("JSON-LD 结构", all(k in jld for k in ("terms", "relations", "stages", "@context")),
      f"键={list(jld.keys())}")
check(f"JSON-LD 术语数={N_TERMS}", len(jld["terms"]) == N_TERMS, f"实际={len(jld['terms'])}")
check(f"JSON-LD 关系数={N_REL}", len(jld["relations"]) == N_REL, f"实际={len(jld['relations'])}")
check(f"JSON-LD 阶段数={N_STAGES}", len(jld["stages"]) == N_STAGES, f"实际={len(jld['stages'])}")
ids = [t["@id"] for t in jld["terms"]]
check("JSON-LD id→IRI 映射", "http://homedesigngroup.local/ontology#concept_channel" in ids,
      f"实际={ids[:2]}")
parents = [t["subClassOf"] for t in jld["terms"]]
check("JSON-LD subClassOf 全指向", all(p.startswith("http://homedesigngroup.local/ontology#") for p in parents),
      f"异常 parent={[p for p in parents if not p.startswith('http://')]}")

# 3. RDF/XML 格式合法 + 内容
rdf_path = os.path.join(EXPORT_DIR, "ontology.rdf")
try:
    dom = xml.dom.minidom.parse(rdf_path)
    classes = dom.getElementsByTagName("owl:Class")
    props = dom.getElementsByTagName("owl:ObjectProperty")
    check("RDF/XML 格式合法", True, "")
    total_cls = N_TERMS + N_STAGES
    check(f"RDF owl:Class 数={total_cls}(术语+阶段)", len(classes) == total_cls, f"实际={len(classes)}")
    check(f"RDF ObjectProperty 数={N_REL}", len(props) == N_REL, f"实际={len(props)}")
    check("RDF 含 Ontology 声明", len(dom.getElementsByTagName("owl:Ontology")) == 1, "")
except Exception as e:
    check("RDF/XML 格式合法", False, f"解析失败: {e}")

# 4. Turtle 内容
with open(os.path.join(EXPORT_DIR, "ontology.ttl"), "r", encoding="utf-8") as f:
    ttl = f.read()
check("TTL 前缀齐全", all(p in ttl for p in ("owl:", "rdfs:", "subClassOf")), "缺前缀/关键词")
check(f"TTL 类声明数={N_TERMS}+{N_STAGES}", ttl.count("a owl:Class ;") == N_TERMS + N_STAGES,
      f"实际={ttl.count('a owl:Class ;')}")
check(f"TTL 关系属性数={N_REL}", ttl.count("a owl:ObjectProperty") == N_REL,
      f"实际={ttl.count('a owl:ObjectProperty')}")

# 5. 不含实例数据（隐私）
for fn in ("ontology.jsonld", "ontology.rdf", "ontology.ttl"):
    with open(os.path.join(EXPORT_DIR, fn), "r", encoding="utf-8") as f:
        text = f.read()
    check(f"{fn} 不含手机号/客户名", "135" not in text and "周乾坤" not in text, "泄露实例数据")

print("\n" + ("全部通过" if not fails else f"{len(fails)} 项失败"))
raise SystemExit(1 if fails else 0)
