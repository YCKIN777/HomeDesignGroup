# -*- coding: utf-8 -*-
"""
mcp_server.py — MCP 出口（Step 4.8，对齐"开放API(Ontology MCP)"）
轻量 Model Context Protocol：JSON-RPC 2.0 over HTTP（POST /mcp）。
  方法：initialize / notifications/initialized / tools/list / tools/call
  工具：把平台现有能力（线索/起草/评分/知识库/指标/记忆/配置/调度）以标准
        工具清单暴露，外部 Agent（豆包/Claude/Cursor 等）可经统一协议调用。
  权限：每工具声明所需动作，调用时经 actions.check_action 校验（与角色矩阵一致）；
        业务层自身照常审计（本层不重复记账）。
  说明：轻量模式为 HTTP JSON-RPC（非 SSE 流式）；接 Claude Desktop 需 SSE 传输，
        列为扩展点，不影响 HTTP 客户端直接调用。
"""
import json

from agents.lead_agent import LeadAgent
from agents.scoring_agent import ScoringAgent
from agents.kb_agent import KbAgent
from agents.sop_agent import SopAgent
from agents.craft_qa_agent import CraftQaAgent
from agents.quote_agent import QuoteAgent
from agents.site_report_agent import SiteReportAgent
from db import get_conn
from kernel import actions as act_registry
from kernel.config_loader import load_profile

COMPANY = "壹城精工"
PROTOCOL_VERSION = "2025-03-26"

_lead_agent = LeadAgent()
_scoring = ScoringAgent()
_kb = KbAgent()
_sop = SopAgent()
_craft_qa = CraftQaAgent()

# ---------- 工具注册表：name → (description, inputSchema, required_action 或 None=读) ----------
TOOLS = {
    "leads_search": {
        "description": "按状态/关键词查询客户线索（读）",
        "inputSchema": {"type": "object", "properties": {
            "status": {"type": "string", "description": "线索/跟进/邀约/到店/派单/成交/流失"},
            "q": {"type": "string", "description": "姓名/楼盘/电话/标签关键词"},
            "limit": {"type": "integer", "description": "条数上限"}},
            "additionalProperties": False},
        "required_action": None,
    },
    "leads_create": {
        "description": "录入一条线索（按手机号去重合并）",
        "inputSchema": {"type": "object", "properties": {
            "user": {"type": "string", "description": "操作账号"},
            "phone": {"type": "string"},
            "name": {"type": "string"}, "estate": {"type": "string"},
            "layout": {"type": "string"}, "area": {"type": "number"},
            "budget_range": {"type": "string"}, "style": {"type": "string"},
            "intent_time": {"type": "string"}, "channel": {"type": "string"},
            "tags": {"type": "string"}, "source": {"type": "string"}},
            "required": ["phone"], "additionalProperties": False},
        "required_action": "lead.write",
    },
    "lead_score": {
        "description": "对线索做意向评分（0-100）",
        "inputSchema": {"type": "object", "properties": {
            "user": {"type": "string"}, "customer_id": {"type": "integer"}},
            "required": ["user", "customer_id"], "additionalProperties": False},
        "required_action": "score",
    },
    "inbox_draft": {
        "description": "AI 起草待发消息（人审后发流程）",
        "inputSchema": {"type": "object", "properties": {
            "user": {"type": "string"}, "customer_id": {"type": "integer"},
            "kind": {"type": "string", "enum": ["first_contact", "followup", "custom"]},
            "context": {"type": "string"}},
            "required": ["user", "customer_id"], "additionalProperties": False},
        "required_action": "draft",
    },
    "kb_search": {
        "description": "检索谈单知识库（报价/工艺/案例），带来源",
        "inputSchema": {"type": "object", "properties": {
            "query": {"type": "string"}, "top_k": {"type": "integer"}},
            "required": ["query"], "additionalProperties": False},
        "required_action": None,
    },
    "stats_overview": {
        "description": "平台经营指标概览（线索/项目/待办/消息）",
        "inputSchema": {"type": "object", "properties": {},
                        "additionalProperties": False},
        "required_action": None,
    },
    "config_view": {
        "description": "查看当前公司配置包摘要（规则/工作流/术语）",
        "inputSchema": {"type": "object", "properties": {},
                        "additionalProperties": False},
        "required_action": None,
    },
    "memory_append": {
        "description": "写一条 L4 文本记忆（含本体 frontmatter）",
        "inputSchema": {"type": "object", "properties": {
            "concept_id": {"type": "string", "description": "术语注册表 id，如 concept.channel"},
            "relation": {"type": "string", "enum": ["part_of", "preceded_by",
                                                    "has_participant", "has_responsible", "derived_from"]},
            "state": {"type": "string", "enum": ["观察", "已核验", "已废弃"]},
            "source": {"type": "string"}, "content": {"type": "string"}},
            "required": ["concept_id", "content"], "additionalProperties": False},
        "required_action": "memory.write",
    },
    "sop_run": {
        "description": "手动触发一次 SOP 扫描（首联超时/跟进到期→待办）",
        "inputSchema": {"type": "object", "properties": {},
                        "additionalProperties": False},
        "required_action": "webhook.ingest",   # 机器入口，仅内部账号
    },
    "action_help": {
        "description": "查询某账号可执行动作清单（动作注册表）",
        "inputSchema": {"type": "object", "properties": {
            "user": {"type": "string"}}, "required": ["user"],
            "additionalProperties": False},
        "required_action": None,
    },
    # ===== 契约线（业主监理）=====
    "contract_craft_qa": {
        "description": "工艺问答：查工艺知识库（211 条，预算范本）+ 材料参考价，草稿态不对外",
        "inputSchema": {"type": "object", "properties": {
            "user": {"type": "string"},
            "question": {"type": "string", "description": "如：轻钢龙骨吊顶怎么做"},
            "category": {"type": "string", "description": "工艺分类，可留空"}},
            "required": ["question"], "additionalProperties": False},
        "required_action": None,
    },
    "contract_build_quote": {
        "description": "生成报价单草稿（严格列项：项目/规格/单位/数量/单价/合价/备注，来自 materials 库）",
        "inputSchema": {"type": "object", "properties": {
            "user": {"type": "string"},
            "owner_id": {"type": "integer", "description": "业主档案 id（owners 表）"},
            "requirements": {"type": "string"},
            "category": {"type": "string", "description": "材料分类，如：瓷砖"}},
            "required": ["user", "owner_id"], "additionalProperties": False},
        "required_action": "draft",
    },
    "contract_site_report": {
        "description": "生成工地日报草稿（OCR+模板→pending_human，人工点发送才对外）",
        "inputSchema": {"type": "object", "properties": {
            "user": {"type": "string"},
            "project": {"type": "string"},
            "photo_desc": {"type": "string", "description": "监理现场备注"}},
            "required": ["user", "project"], "additionalProperties": False},
        "required_action": "draft",
    },
}


# ---------- 工具实现 ----------
def _call_tool(name: str, args: dict, user: str) -> dict:
    """返回 (result dict)；权限或业务失败时抛 ValueError"""
    if name == "leads_search":
        with get_conn() as conn:
            sql = "SELECT * FROM customers WHERE 1=1"
            params = []
            if args.get("status"):
                sql += " AND status=?"
                params.append(args["status"])
            if args.get("q"):
                sql += " AND (name LIKE ? OR estate LIKE ? OR phone LIKE ? OR tags LIKE ?)"
                params += [f"%{args['q']}%"] * 4
            sql += " ORDER BY id DESC LIMIT ?"
            params.append(int(args.get("limit", 20)))
            rows = conn.execute(sql, params).fetchall()
        return {"total": len(rows), "items": [dict(r) for r in rows]}

    if name == "leads_create":
        r = _lead_agent.ingest(user=user, phone=args["phone"], name=args.get("name"),
                               estate=args.get("estate"), layout=args.get("layout"),
                               area=args.get("area"), budget_range=args.get("budget_range"),
                               style=args.get("style"), intent_time=args.get("intent_time"),
                               channel=args.get("channel"), tags=args.get("tags"),
                               source=args.get("source"))
        return r

    if name == "lead_score":
        return _scoring.score(user=user, customer_id=args["customer_id"])

    if name == "inbox_draft":
        return _lead_agent.prepare_draft(user=user, customer_id=args["customer_id"],
                                         kind=args.get("kind", "first_contact"),
                                         context=args.get("context", ""))

    if name == "kb_search":
        hits = _kb.search(args["query"], top_k=int(args.get("top_k", 5)))
        return {"total": len(hits), "items": hits}

    if name == "stats_overview":
        with get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
            status_rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM customers GROUP BY status").fetchall()
            projects = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
            open_todos = conn.execute(
                "SELECT COUNT(*) FROM todos WHERE done=0").fetchone()[0]
            drafts = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE approve_status='draft'").fetchone()[0]
        return {"customers_total": total, "by_status": {r["status"]: r["n"] for r in status_rows},
                "projects": projects, "open_todos": open_todos, "draft_messages": drafts}

    if name == "config_view":
        cfg = load_profile(COMPANY)
        return {"company": cfg["manifest"]["company"],
                "kernel_version": cfg["manifest"]["kernel_version"],
                "terms": len(cfg["terms"]),
                "rules_keys": list(cfg["rules"].keys()),
                "workflow_backbone": cfg["workflow"]["backbone"],
                "workflow_locked": cfg["workflow"]["locked_nodes"],
                "extensions_concepts": len(cfg["extensions"].get("concepts", []))}

    if name == "memory_append":
        import os
        from datetime import datetime
        ROOT = r"H:\AgentProjects\HomeDesignGroup"
        MEMORY_DIR = os.path.join(ROOT, "memory")
        os.makedirs(MEMORY_DIR, exist_ok=True)
        fname = f"{datetime.now().strftime('%Y-%m-%d')}-{args['concept_id'].replace('.', '-')}.md"
        path = os.path.join(MEMORY_DIR, fname)
        content = (args.get("content") or "").strip()
        if not content:
            raise ValueError("内容为空")
        if os.path.exists(path):
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"\n\n---\n{content}\n")
            return {"file": os.path.relpath(path, ROOT), "append": True}
        text = (f"---\nconcept_id: {args['concept_id']}\nrelation: {args.get('relation', 'derived_from')}\n"
                f"state: {args.get('state', '观察')}\ntime: \"{datetime.now().strftime('%Y-%m-%d')}\"\n"
                f"source: {args.get('source', 'MCP')}\n---\n\n{content}\n")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return {"file": os.path.relpath(path, ROOT), "append": False}

    if name == "sop_run":
        todos = _sop.check_due()
        return {"checked": True, "open_todos": len(todos)}

    if name == "action_help":
        return {"user": user, "actions": act_registry.describe_actions(user)}

    # ===== 契约线（业主监理）=====
    if name == "contract_craft_qa":
        ans = _craft_qa.answer(args["question"], args.get("category", ""), user)
        return {"question": ans["question"], "craft_total": len(ans["craft"]),
                "craft": ans["craft"], "materials": ans["materials"],
                "draft": True}

    if name == "contract_build_quote":
        q = QuoteAgent(user).build_quote(int(args["owner_id"]),
                                         args.get("requirements", ""),
                                         args.get("category", ""))
        return {"owner": q["owner"], "columns": q["columns"], "rows": q["rows"],
                "row_count": q["row_count"], "status": q["status"]}

    if name == "contract_site_report":
        rep = SiteReportAgent().build_report(args["project"], args.get("photo_desc", ""))
        return {"id": rep["id"], "project": rep["project"], "date": rep["date"],
                "photo_ocr": rep["photo_ocr"], "progress_summary": rep["progress_summary"],
                "status": rep["status"]}

    raise ValueError(f"未知工具: {name}")


# ---------- MCP 协议处理 ----------
def handle_mcp(body: dict, header_user: str = "") -> dict:
    """JSON-RPC 分发。通知类返回 None（无需响应）。"""
    method = body.get("method")
    rid = body.get("id")
    params = body.get("params") or {}

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": params.get("protocolVersion", PROTOCOL_VERSION),
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": f"{COMPANY}-MCP", "version": "0.1"}}}

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        tools = [{"name": n, "description": t["description"],
                  "inputSchema": t["inputSchema"]} for n, t in TOOLS.items()]
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": tools}}

    if method == "tools/call":
        name = params.get("name")
        args = dict(params.get("arguments") or {})
        user = (args.get("user") or header_user or "system").strip() or "system"
        t = TOOLS.get(name)
        if t is None:
            return _err(rid, -32602, f"未知工具: {name}")
        # 权限校验（读工具任意登录可调；写工具经动作注册表）
        if t["required_action"]:
            ok, msg = act_registry.check_action(user, t["required_action"])
            if not ok:
                return _err(rid, -32001, f"权限不足: {msg}")
        try:
            result = _call_tool(name, args, user)
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                "isError": False}}
        except ValueError as e:
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": f"业务错误: {e}"}], "isError": True}}
        except Exception as e:   # noqa: BLE001
            return _err(rid, -32603, f"内部错误: {e}")

    return _err(rid, -32601, "method not found")


def _err(rid, code: int, msg: str) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": msg}}


if __name__ == "__main__":
    # 自检：协议握手 + 工具清单
    print("[mcp] initialize ->", json.dumps(handle_mcp(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": PROTOCOL_VERSION}}, header_user="admin"), ensure_ascii=False))
    lst = handle_mcp({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, header_user="admin")
    print(f"[mcp] tools/list -> {len(lst['result']['tools'])} 个工具")
