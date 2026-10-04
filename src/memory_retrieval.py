# -*- coding: utf-8 -*-
"""
memory_retrieval.py — 统一记忆检索门面（Step 4.11，总纲目录点名文件）
职责显式化：Otter 读取第 3 步"提问时按需检索 L3+L4"的独立能力入口。
  - 主体实现复用 MemoryManager.retrieve（知识库/沉淀中心/记忆文件/客户画像，带来源）
  - 本文件提供：检索 + 可选 L2 短记忆并入（打开客户自动载 L2 的显式调用点）
用法：
  from memory_retrieval import retrieve_all
  hits = retrieve_all("防水 质保", top_k=5, include_l2_customer=7)
"""
import os

from memory_manager import MemoryManager

ROOT = r"H:\AgentProjects\HomeDesignGroup"


def retrieve_all(query: str, top_k: int = 5, include_l2_customer: int = None,
                 company: str = "壹城精工") -> dict:
    """统一检索：L3+L4 按需检索（带来源）；可选并入指定客户的 L2 短记忆。"""
    mm = MemoryManager()
    hits = mm.retrieve(query, top_k=top_k)
    l2 = []
    if include_l2_customer:
        for m in mm.load_l2(include_l2_customer, limit=10):
            l2.append({"layer": "L2", "source": f"messages#{m['id']}",
                       "snippet": (m.get("content") or "")[:120],
                       "direction": m.get("direction"), "score": 1})
    return {
        "query": query,
        "total": len(hits) + len(l2),
        "items": l2 + hits,
        "loaded": {
            "L2_customer": include_l2_customer,
            "L3_L4_top_k": top_k,
            "note": "L2=会话短记忆(打开客户自动载), L3=知识库/沉淀/画像, L4=文本记忆",
        },
    }


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "报价"
    res = retrieve_all(q)
    print(f"[memory_retrieval] query={q!r} total={res['total']}")
    for h in res["items"]:
        print(f"  [{h['layer']}] {h['source']}: {h['snippet'][:60]}")
