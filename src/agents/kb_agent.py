# -*- coding: utf-8 -*-
"""kb_agent — 谈单知识库（M9）"""
import glob
import os
import re

from .base import BaseAgent

ROOT = r"H:\AgentProjects\HomeDesignGroup"
KNOWLEDGE_DIR = os.path.join(ROOT, "knowledge")


class KbAgent(BaseAgent):
    name = "kb"
    role = "谈单知识库（设计/报价/工艺/案例）"
    capabilities = [
        "检索知识库（关键词起步）",
        "报价与工艺口径问答",
        "案例卖点提取",
        "知识条目沉淀建议",
    ]

    def search(self, query: str, top_k: int = 5) -> list:
        """关键词检索 knowledge/**/*.md，带来源路径。
        中文整句分词缺失时会退化为整句匹配导致命中 0，故追加 bigram 切分增强。"""
        words = [w for w in re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]+", query.lower()) if w]
        # bigram 增强：含中文的词切成 2 字片段，提升短句/术语命中
        grams = []
        for w in words:
            if len(w) >= 2 and re.search(r"[\u4e00-\u9fa5]", w):
                grams.extend(w[i:i + 2] for i in range(len(w) - 1))
        terms = words + [g for g in grams if len(g) == 2]
        hits = []
        for path in glob.glob(os.path.join(KNOWLEDGE_DIR, "**", "*.md"), recursive=True):
            try:
                text = open(path, "r", encoding="utf-8-sig").read()
            except OSError:
                continue
            low = text.lower()
            score = sum(1 for w in terms if w in low)
            if score:
                title = os.path.splitext(os.path.basename(path))[0]
                first = next((l for l in text.splitlines() if l.strip() and not l.startswith("#")), "")
                hits.append({"source": os.path.relpath(path, ROOT), "title": title,
                             "snippet": (first or text[:100])[:150], "score": score})
        hits.sort(key=lambda h: h["score"], reverse=True)
        return hits[:top_k]

    def handle(self, ctx, message: str):
        return self.todo("M9 已实现（search）")
