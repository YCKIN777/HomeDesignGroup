# -*- coding: utf-8 -*-
"""craft_qa_agent.py — MVP Sub-agent 1：工艺问答 Agent（架构契约 Step 6）

业主问"降噪隔墙怎么做" → 查 craft_knowledge 表（RAG 语料，先 SQL 后向量）+
拉 materials 参考价 → 出结构化答案（工艺+材料+参考价）。
对外发送由 Sentinel external_send 闸门拦截（人工点发送）。
"""
from models.core import connect
from providers.factory import get_providers
from kernel.llm_enhance import llm_enhance


class CraftQaAgent:
    def __init__(self):
        self.providers = get_providers()

    @staticmethod
    def _split_words(q: str) -> list:
        """拆词：先去停用词取整词；为空则回退 2-gram"""
        import re
        stop = {"怎么做", "如何", "请问", "一下", "怎样", "怎么办", "是什么", "哪些", "哪种"}
        q2 = q
        for w in stop:
            q2 = q2.replace(w, " ")
        words = [w for w in re.findall(r"[\u4e00-\u9fa5]{2,}", q2)]
        if not words:                            # 全是停用词 → 回退 2-gram
            chars = re.findall(r"[\u4e00-\u9fa5]", q)
            words = ["".join(chars[i:i + 2]) for i in range(len(chars) - 1)]
        return words

    def search_craft(self, q: str, category: str = "", top_k: int = 5) -> list:
        """查工艺知识库：向量检索优先，回退关键词 LIKE（整词→2-gram 两级兜底）"""
        try:
            hits = self.providers.vector_store.search("craft_knowledge", q, top_k=top_k)
            if hits:
                return [{"text": h.text, "metadata": h.metadata, "score": round(h.score, 3)}
                        for h in hits]
        except Exception:
            pass
        words = self._split_words(q)
        if not words:
            return []
        rows = self._rank(self._like_query(words, category, top_k), words)
        if not rows and len(words) == 1 and len(words[0]) >= 4:
            # 整词无命中 → 2-gram 兜底（应对"轻钢龙骨吊顶"≠"轻钢龙骨、石膏板吊平顶"）
            import re
            chars = re.findall(r"[\u4e00-\u9fa5]", words[0])
            bigrams = ["".join(chars[i:i + 2]) for i in range(len(chars) - 1)]
            # 过滤工艺领域通用词（"工艺/施工/做法"等单独出现无区分度，避免误命中）
            stop = {"工艺", "施工", "做法", "材料", "装修", "安装", "使用", "需要",
                    "注意", "进行", "我们", "可以", "这个", "一个", "什么", "怎么",
                    "如何", "哪些", "时候", "地方", "问题", "情况", "方面", "部分"}
            bigrams = [b for b in bigrams if b not in stop]
            if bigrams:
                rows = self._rank(self._like_query(bigrams, category, top_k), bigrams)
        return rows

    @staticmethod
    def _rank(rows: list, words: list) -> list:
        """按命中词元数降序（标题/内容/分类含词越多越相关）"""
        def score(r):
            text = r.get("title", "") + r.get("content", "") + r.get("category", "")
            return sum(1 for w in words if w in text)
        return sorted(rows, key=score, reverse=True)

    @staticmethod
    def _like_query(words: list, category: str, top_k: int) -> list:
        """关键词 LIKE 查询（OR 语义）"""
        from models.core import connect
        with connect() as conn:
            sql = "SELECT id, category, title, content, source_file FROM craft_knowledge WHERE 1=1"
            params = []
            if category:
                sql += " AND category=?"
                params.append(category)
            sql += " AND (" + " OR ".join(
                ["(title LIKE ? OR content LIKE ? OR category LIKE ?)"] * len(words)) + ") LIMIT ?"
            for w in words:
                params += [f"%{w}%"] * 3
            params.append(top_k)
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def materials_price(self, category: str = "") -> list:
        """拉建材参考价（materials 表）"""
        with connect() as conn:
            sql = "SELECT name, spec, price, supplier, tags FROM materials WHERE 1=1"
            params = []
            if category:
                sql += " AND category LIKE ?"
                params.append(f"%{category}%")
            sql += " LIMIT 10"
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def answer(self, question: str, category: str = "", user: str = "客服") -> dict:
        """结构化答案：工艺 + 材料参考价 + 来源（草稿，不对外发）"""
        crafts = self.search_craft(question, category)
        mats = self.materials_price(category)
        # LLM 增强（可选层）：命中后把知识库原文整理成自然语言回答；未配 key 自动降级
        if crafts:
            src = "\n".join(f"【{c['title']}】{c['content']}" for c in crafts[:3])
            enhance = llm_enhance(
                self.providers,
                "你是家装公司的工艺顾问。用通俗、可信的语言回答业主关于施工工艺的问题。"
                "只依据给定知识库条目组织回答，不编造知识库没有的工艺参数；"
                "输出 3-5 句：做法要点 + 施工注意点。",
                f"业主问题：{question}\n知识库命中条目：\n{src}")
        else:
            enhance = {"enabled": False, "provider": "mock", "text": "",
                       "error": "知识库无命中，跳过 LLM 整理"}
        answer = {
            "question": question,
            "craft": [{"title": c.get("title"), "content": c.get("content"),
                       "source": c.get("source_file")} for c in crafts],
            "materials": [{"name": m["name"], "spec": m["spec"],
                           "price": m["price"], "supplier": m["supplier"]} for m in mats],
            "llm_summary": enhance,
            "draft": True, "sentinel": "read/draft 放行（不对外）",
        }
        return answer
