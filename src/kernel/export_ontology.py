# -*- coding: utf-8 -*-
"""
export_ontology.py — 语义导出（Step 4.9，对齐 Palantir"本体定义可导入导出、防深度锁定"）
把配置包的语义定义（terms.yaml 术语 + workflow 阶段 + 关系白名单）导出为三种开放格式：
  JSON-LD（.jsonld） / RDF-XML（.rdf） / OWL Turtle（.ttl）
特性：
  - 零新依赖：手写序列化器（json/yaml 均为标准库+已有依赖）
  - 只导出语义定义（类/属性/关系声明），不含公司私有实例数据（隐私安全）
  - 语义保持：id 映射为 IRI（concept.channel → concept_channel），parent→rdfs:subClassOf
  - workflow 阶段导出为"阶段类"（状态机节点显式化），transitions 不导出方向三元组
    （preceded_by 方向语义未在术语表定义，避免导出错误语义）
用法：
  python -m kernel.export_ontology [公司名]     # 默认 壹城精工
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kernel.config_loader import load_profile  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROFILE_DIR = os.path.join(ROOT, "company_profiles")

NS = "http://homedesigngroup.local/ontology#"
OWL = "http://www.w3.org/2002/07/owl#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"

RELATIONS = ["part_of", "preceded_by", "has_participant",
             "has_responsible", "derived_from"]


def _iri(cid: str) -> str:
    return NS + cid.replace(".", "_")


def _term_to_iris(terms: list) -> dict:
    return {t["id"]: _iri(t["id"]) for t in terms}


# ---------- JSON-LD ----------
def build_jsonld(company: str) -> dict:
    cfg = load_profile(company)
    terms = cfg["terms"]
    doc = {
        "@context": {
            "owl": OWL, "rdfs": RDFS,
            "label": {"@id": "rdfs:label", "@language": "zh"},
            "definition": {"@id": "rdfs:comment", "@language": "zh"},
            "subClassOf": {"@id": "rdfs:subClassOf", "@type": "@id"},
            "source": "http://homedesigngroup.local/schema#source",
            "status": "http://homedesigngroup.local/schema#status",
        },
        "@id": NS + company,
        "@type": "owl:Ontology",
        "title": f"{company} 家装业务本体（语义定义导出）",
        "terms": [],
        "relations": [],
        "stages": [],
    }
    for t in terms:
        node = {"@id": _iri(t["id"]), "@type": "owl:Class",
                "label": t["label"], "definition": t["definition"],
                "subClassOf": _iri(t["parent"])}
        if t.get("source"):
            node["source"] = t["source"]
        if t.get("status"):
            node["status"] = t["status"]
        doc["terms"].append(node)
    for r in RELATIONS:
        doc["relations"].append({"@id": _iri(f"rel.{r}"), "@type": "owl:ObjectProperty",
                                 "label": r})
    for s in cfg["workflow"]["backbone"]:
        doc["stages"].append({"@id": _iri(f"stage.{s}"), "@type": "owl:Class",
                              "label": s})
    return doc


# ---------- RDF/XML ----------
def _xml_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def build_rdfxml(company: str) -> str:
    cfg = load_profile(company)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<rdf:RDF xmlns:rdf="{RDF}" xmlns:rdfs="{RDFS}" '
        f'xmlns:owl="{OWL}" xml:base="{NS}">',
        f'  <owl:Ontology rdf:about="{NS}{company}">',
        f"    <rdfs:label>{_xml_escape(company)} 家装业务本体（语义定义导出）</rdfs:label>",
        "  </owl:Ontology>",
    ]
    for t in cfg["terms"]:
        cid = _iri(t["id"])
        lines.append(f'  <owl:Class rdf:about="{cid}">')
        lines.append(f"    <rdfs:label>{_xml_escape(t['label'])}</rdfs:label>")
        lines.append(f"    <rdfs:comment>{_xml_escape(t['definition'])}</rdfs:comment>")
        lines.append(f'    <rdfs:subClassOf rdf:resource="{_iri(t["parent"])}"/>')
        if t.get("source"):
            lines.append(f"    <source>{_xml_escape(t['source'])}</source>")
        if t.get("status"):
            lines.append(f"    <status>{_xml_escape(t['status'])}</status>")
        lines.append("  </owl:Class>")
    for r in RELATIONS:
        lines.append(f'  <owl:ObjectProperty rdf:about="{_iri("rel." + r)}">')
        lines.append(f"    <rdfs:label>{r}</rdfs:label>")
        lines.append("  </owl:ObjectProperty>")
    for s in cfg["workflow"]["backbone"]:
        lines.append(f'  <owl:Class rdf:about="{_iri("stage." + s)}">')
        lines.append(f"    <rdfs:label>{_xml_escape(s)}</rdfs:label>")
        lines.append("  </owl:Class>")
    lines.append("</rdf:RDF>")
    return "\n".join(lines)


# ---------- OWL Turtle ----------
def _ttl_label(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_ttl(company: str) -> str:
    cfg = load_profile(company)
    lines = [
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix : <" + NS + "> .",
        "",
        f":{company} a owl:Ontology ;",
        f"    rdfs:label {_ttl_label(company + ' 家装业务本体（语义定义导出）')} .",
        "",
    ]
    for t in cfg["terms"]:
        cid = _iri(t["id"])
        lines.append(f"{cid} a owl:Class ;")
        lines.append(f"    rdfs:label {_ttl_label(t['label'])} ;")
        lines.append(f"    rdfs:comment {_ttl_label(t['definition'])} ;")
        lines.append(f"    rdfs:subClassOf {_iri(t['parent'])} .")
    lines.append("")
    for r in RELATIONS:
        lines.append(f"{_iri('rel.' + r)} a owl:ObjectProperty ;")
        lines.append(f"    rdfs:label {_ttl_label(r)} .")
    lines.append("")
    for s in cfg["workflow"]["backbone"]:
        lines.append(f"{_iri('stage.' + s)} a owl:Class ;")
        lines.append(f"    rdfs:label {_ttl_label(s)} .")
    return "\n".join(lines)


def export(company: str) -> dict:
    """导出三格式，返回文件清单"""
    out_dir = os.path.join(PROFILE_DIR, company, "ontology-export")
    os.makedirs(out_dir, exist_ok=True)
    files = {}
    # JSON-LD
    jld = build_jsonld(company)
    p = os.path.join(out_dir, "ontology.jsonld")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(jld, f, ensure_ascii=False, indent=2)
    files["jsonld"] = os.path.relpath(p, ROOT)
    # RDF/XML
    p = os.path.join(out_dir, "ontology.rdf")
    with open(p, "w", encoding="utf-8") as f:
        f.write(build_rdfxml(company))
    files["rdf"] = os.path.relpath(p, ROOT)
    # Turtle
    p = os.path.join(out_dir, "ontology.ttl")
    with open(p, "w", encoding="utf-8") as f:
        f.write(build_ttl(company))
    files["ttl"] = os.path.relpath(p, ROOT)
    return files


if __name__ == "__main__":
    company = sys.argv[1] if len(sys.argv) > 1 else "壹城精工"
    files = export(company)
    print(f"[export_ontology] {company} 语义导出完成：")
    for k, v in files.items():
        print(f"  {k}: {v}")
