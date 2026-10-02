# -*- coding: utf-8 -*-
"""
memory_manager.py — 四层记忆管理器（Step 1.6 骨架，本体驱动·Otter 读取）
设计对齐《记忆架构v2》：
  L1 即时  = sessions 表（会话可建/可续）
  L2 短    = messages / followups / audit_log（当前客户自动载，30 天滚动）
  L3 长    = customers 画像 + 配置包 + sedimentation + knowledge（本体结构化，按需检索带来源）
  L4 文本  = memory/ 目录 md（YAML frontmatter: concept_id/relation/state/time/source）
读取顺序（Otter 模式）：身份必载 → 打开客户自动载 L2 → 提问按需检索 L3/L4(top-k,带来源) → 会话内保持
约束：记忆唯一骨架=本体系统，不引入其他记忆方式（不引 Mem0/Zep/外部向量库）。
"""
import glob
import os
import re
import sqlite3

import yaml

ROOT = r"H:\AgentProjects\HomeDesignGroup"
DB_DIR = os.path.join(ROOT, "db")


class MemoryManager:
    def __init__(self, company: str = "壹城精工"):
        self.company = company
        self.db_path = os.path.join(DB_DIR, f"{company}.db")
        self.memory_dir = os.path.join(ROOT, "memory")
        self.knowledge_dir = os.path.join(ROOT, "knowledge")
        self.sedimentation_dir = os.path.join(ROOT, "sedimentation")

    # ---------- 连接 ----------
    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        conn.isolation_level = None    # 自动提交，避免跨连接锁
        return conn

    # ============ L1 即时（会话） ============
    def create_session(self, user: str, customer_id=None) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO sessions(user, customer_id, context) VALUES(?,?,?)",
                (user, customer_id, ""))
            return cur.lastrowid

    def get_session(self, session_id: int) -> dict:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        return dict(row) if row else None

    def continue_session(self, session_id: int) -> dict:
        """Otter: 会话可续接——取会话及所属客户"""
        s = self.get_session(session_id)
        if not s:
            return {"error": f"会话 {session_id} 不存在"}
        out = {"session": s}
        if s.get("customer_id"):
            out["l2"] = self.load_l2(s["customer_id"])  # 续接即自动载 L2
        return out

    # ============ L2 短（当前客户自动载） ============
    def load_l2(self, customer_id: int, limit: int = 20) -> list:
        """打开客户自动载：近期对话 + 跟进（按时间倒序）"""
        with self._conn() as conn:
            msgs = conn.execute(
                "SELECT id,'message' kind,direction author,content,created_at "
                "FROM messages WHERE customer_id=? ORDER BY id DESC LIMIT ?",
                (customer_id, limit)).fetchall()
            fups = conn.execute(
                "SELECT id,'followup' kind,channel author,content,created_at "
                "FROM followups WHERE customer_id=? ORDER BY id DESC LIMIT ?",
                (customer_id, limit)).fetchall()
        return [dict(r) for r in msgs] + [dict(r) for r in fups]

    def add_l2_message(self, customer_id: int, direction: str, content: str,
                       author: str = "ai", approve_status: str = "draft"):
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO messages(customer_id,direction,content,author,approve_status) "
                "VALUES(?,?,?,?,?)",
                (customer_id, direction, content, author, approve_status))
            return cur.lastrowid

    # ============ L3 长（按需检索带来源） ============
    def _keyword_hits(self, text: str, query: str) -> int:
        q = re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]+", query.lower())
        t = text.lower()
        return sum(1 for w in q if w and w in t)

    def retrieve(self, query: str, top_k: int = 5) -> list:
        """按需检索 L3+L4：知识库 + 沉淀中心 + 记忆文件 + 客户画像，带来源"""
        hits = []

        # L4 文本记忆（memory/*.md frontmatter+正文）
        for path in glob.glob(os.path.join(self.memory_dir, "*.md")):
            hits += self._file_hits(path, query, layer="L4")

        # L3 知识库（knowledge/*.md）
        for path in glob.glob(os.path.join(self.knowledge_dir, "**", "*.md"), recursive=True):
            hits += self._file_hits(path, query, layer="L3")

        # L3 沉淀中心（sedimentation/*.md）
        for path in glob.glob(os.path.join(self.sedimentation_dir, "**", "*.md"), recursive=True):
            hits += self._file_hits(path, query, layer="L3")

        # L3 客户画像（customers 表匹配楼盘/风格/标签）
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id,name,estate,layout,area,budget_range,style,tags,status "
                "FROM customers WHERE estate LIKE ? OR style LIKE ? OR tags LIKE ? LIMIT 10",
                (f"%{query}%", f"%{query}%", f"%{query}%")).fetchall()
        for r in rows:
            d = dict(r)
            hits.append({"source": f"customers#{d['id']}", "layer": "L3",
                         "snippet": f"{d.get('estate')} {d.get('style')} 预算{d.get('budget_range')} 标签{d.get('tags')}",
                         "score": self._keyword_hits(str(d), query)})

        hits.sort(key=lambda h: h["score"], reverse=True)
        return hits[:top_k]

    def _file_hits(self, path: str, query: str, layer: str) -> list:
        try:
            text = open(path, "r", encoding="utf-8-sig").read()
        except OSError:
            return []
        score = self._keyword_hits(text, query)
        if score == 0:
            return []
        fm = self._frontmatter(path, text)
        snippet = " ".join(text.split())[:120]
        return [{"source": os.path.relpath(path, ROOT), "layer": layer,
                 "snippet": snippet, "score": score, "frontmatter": fm}]

    @staticmethod
    def _frontmatter(path: str, text: str) -> dict:
        m = re.match(r"^---\n(.*?)\n---", text, re.S)
        if not m:
            return {}
        try:
            return yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            return {}

    # ============ 身份必载（Otter: 每次必载，不占大 token） ============
    def build_system_prompt(self, profile: dict) -> str:
        terms = [t["label"] for t in profile.get("terms", [])][:15]
        rules = profile.get("rules", {})
        wf = profile.get("workflow", {})
        locked = wf.get("locked_nodes", [])
        return (
            "你是家装公司前端智能体（获客→客服→派单）。\n"
            f"公司: {self.company}｜内核: {profile.get('manifest', {}).get('kernel_version', '')}\n"
            f"核心概念: {'、'.join(terms)}\n"
            f"状态机主干: {'→'.join(wf.get('backbone', []))}｜不可跳过: {'、'.join(locked)}\n"
            f"关键规则: 折扣阈值{rules.get('discount', {}).get('need_approval_above')} "
            f"首联时限{rules.get('sop', {}).get('first_contact_hours')}小时\n"
            "纪律: AI 只起草，人审批后发；所有动作可追溯。")

    # ---------- 总装：Otter 式上下文 ----------
    def build_context(self, session_id: int, profile: dict, query: str = "") -> dict:
        """Otter 读取顺序：身份必载 → 会话/L2 → 按需检索 L3/L4"""
        ctx = {"system_prompt": self.build_system_prompt(profile)}
        cont = self.continue_session(session_id)
        ctx["session"] = cont.get("session")
        ctx["l2"] = cont.get("l2", [])
        if query:
            ctx["retrieval"] = self.retrieve(query, top_k=5)
        return ctx
