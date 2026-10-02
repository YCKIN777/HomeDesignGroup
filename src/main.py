# -*- coding: utf-8 -*-
"""
main.py — 家装 AI 智能体平台 · 中控（编队计划 v3 · P3-P7 集成版）
定位：CLI 中控，与 api_server.py 同一套业务内核（agents + bus + db + memory + kernel）。
覆盖：获客签单闭环（M1-M9）+ 阶段5 承接 + 6.1 收款 + 6.4 开工闸门 + 软装/材料/售后（P5-P7）。

【编队 v3 九 Agent 全部就位】
  1 业务员  BusinessAgent       (business_agent.py)   lead+scoring+sop+invite
  2 客服    CustomerServiceAgent(customer_service_agent.py) M3a/M3b 收件箱人审后发
  3 设计师  DesignerAgent       (designer_agent.py)   dispatch+kb+方案沉淀
  4 预算部  （quote 模板驱动，API/CLI 共用 routers.dispatch）
  5 材料    MaterialAgent       (material_agent.py)   材料库+主材清单
  6 软装    SoftFurnishingAgent (soft_furnishing_agent.py) 家具/灯具/窗帘/布艺
  7 工程    EngineerAgent       (engineer_agent.py)   site_report+craft_qa+验收
  8 总经办  ExecutiveOfficeAgent(executive_office_agent.py) 审批/看板/审计
  9 售后    AfterSalesAgent     (after_sales_agent.py) 质保/工单/回访

【获客线指令】
  /leads                 线索列表
  /lead add <phone> [--estate x --budget_range x --style x --tags x]  录入线索（自动去重）
  /lead <id>             客户详情（含 L2 短记忆）
  /tag <id> <标签...>     建档打标
  /status <id> <to>      客户状态迁移（校验 workflow.yaml）
  /draft <id> <kind>     AI 起草（收件箱待审批）
  /inbox                 收件箱（草稿）
  /approve <mid>         审批发送（人审后发）
  /reject <mid> [原因]    驳回
  /dispatch <id> [设计师]  派单建项目
  /score <id>            评分分级 A/B/C
  /invite <id> [时间]     邀约到店
  /todos                 待办（SOP 刷新）
  /kb <关键词>            知识库检索
  /stats                 业务指标
  /config                配置摘要

【阶段5 承接指令】
  /plan add <pid> <风格> [要点]        设计方案沉淀（版本递增）
  /plan list <pid>                     项目方案列表
  /plan status <plid> <初稿|评审中|已定稿|已否决>  方案状态流转
  /quote gen <pid> [要求]              生成报价草稿（预算范本模板驱动：325 条明细+面积估算）
  /quote items <qid>                   报价明细分组摘要
  /quote discount <qid> <0.97>         提交折扣（<9.8折自动转待审批，审批人=董事长）
  /quote approve <qid> [已审批|已否决]   报价审批（quote.approve 权限）
  /quote plan <qid>                    付款计划（60/35/5）
  /pay add <qid> <签约|阶段验收|验收> <金额> [备注]   登记收款（不超阶段剩余）
  /pay plan <qid>                      收款进度（应缴/已收/待收）
  /proj <pid> <to>                     项目状态迁移（含闸门：开工需签约款收足）
  /report <pid> <阶段> <内容>          工地日报（项目经理）
  /inspect <pid> <节点> <合格|整改> [备注]  五节点验收（水电/防水/泥木/油漆/竣工）
  /detail <pid>                        项目承接全景（客户+方案+报价+收款+验收+日报+软装+售后）

【编队 v3 新增指令（P3-P7）】
  /ceo approvals                     总经办：审批汇总（消息草稿/报价待批/售后待处理）
  /ceo dashboard                     总经办：数据看板
  /ceo audit [n]                     总经办：审计追溯（董事长/财务）
  /ceo coord <备注>                   总经办：跨部门协调留痕
  /mat list [分类]                    材料：材料库检索
  /mat list4quote <qid>              材料：报价单主材清单（小计+合计）
  /soft add <pid> <分类> <品名> [--spec x --qty n --price p]   软装录入（家具/灯具/窗帘/布艺/装饰/其他）
  /soft list <pid>                    软装清单（含分类小计+合计）
  /soft up <id> <k=v k=v ...>         软装更新（category/name/spec/qty/unit_price/status/note）
  /soft rm <id>                       软装删除
  /as warranty <pid> [竣工日期]        售后：质保登记（整体2年/防水10年）
  /as ticket <pid> <标题> [内容]       售后：工单创建
  /as list [pid]                      售后：工单/质保列表
  /as status <id> <待处理|处理中|已关闭> [结果]  售后：工单状态
  /as due                             售后：回访 SOP（竣工30/90/365天 + 质保到期提醒）

【通用】/pause|/resume <id> 暂停/恢复处理 · /help 帮助 · exit 退出
启动：python src/main.py   （Web 版：start_platform.ps1 → http://127.0.0.1:8000/app）
"""
import sys

sys.path.insert(0, r"H:\AgentProjects\HomeDesignGroup\src")

from agents.business_agent import BusinessAgent                    # noqa: E402
from agents.customer_service_agent import CustomerServiceAgent     # noqa: E402
from agents.designer_agent import DesignerAgent                    # noqa: E402
from agents.engineer_agent import EngineerAgent                    # noqa: E402
from agents.executive_office_agent import ExecutiveOfficeAgent     # noqa: E402
from agents.material_agent import MaterialAgent                    # noqa: E402
from agents.soft_furnishing_agent import SoftFurnishingAgent       # noqa: E402
from agents.after_sales_agent import AfterSalesAgent               # noqa: E402
from db import get_conn                                             # noqa: E402
from kernel import config_loader                                    # noqa: E402
from kernel.bus import Bus                                          # noqa: E402
from kernel.roles import require                                    # noqa: E402
from routers.dispatch import (                                      # noqa: E402
    create_quote, quote_items, add_payment,
    payment_progress, project_transition)

USER = "admin"
bus = Bus()
bus.register_defaults()
_PROFILE = "壹城精工"

business = BusinessAgent()
cs = CustomerServiceAgent()
designer = DesignerAgent()
engineer = EngineerAgent()
ceo = ExecutiveOfficeAgent()
material = MaterialAgent()
soft = SoftFurnishingAgent()
aftersales = AfterSalesAgent()


# ---- 获客线业务指令处理器（业务员/客服 Agent） ----
def _leads(args):
    rows = business.list_customers()
    if not rows:
        return "(空)"
    return "\n".join(f"#{r['id']} {r['name'] or '-'} {r['phone']} {r['estate'] or '-'} "
                     f"{r['status']} {r['score']}分" for r in rows)


def _lead_add(args):
    if len(args) < 2:
        return "用法: /lead add <phone> [--estate x --budget_range x --style x --tags x]"
    phone, rest = args[0], args[1:]
    fields = {}
    for i in range(0, len(rest) - 1, 2):
        if rest[i].startswith("--"):
            fields[rest[i][2:]] = rest[i + 1]
    r = business.ingest(USER, phone, **fields)
    return f"线索 {'合并' if r['deduped'] else '录入'} id={r['id']}"


def _lead_get(args):
    if not args:
        return "用法: /lead <id>"
    d = business.get_customer(int(args[0]))
    l2 = d.pop("l2", [])
    return (f"#{d['id']} {d['name']} {d['phone']}\n  {d['estate']} {d['layout']} "
            f"{d['area']}㎡ 预算{d['budget_range']} {d['style']}\n  状态:{d['status']} "
            f"评分:{d['score']} 标签:{d['tags']}\n  L2({len(l2)}条): "
            + " | ".join(m["content"][:30] for m in l2[:3]))


def _tag(args):
    if len(args) < 2:
        return "用法: /tag <id> <标签,逗号分隔>"
    d = business.profile(USER, int(args[0]), tags=",".join(args[1:]))
    return f"客户 {d['id']} 标签: {d['tags']}"


def _status(args):
    if len(args) < 2:
        return "用法: /status <id> <to>"
    return str(business.transition(USER, int(args[0]), args[1]))


def _draft(args):
    if not args:
        return "用法: /draft <id> [first_contact|followup|custom]"
    kind = args[1] if len(args) > 1 else "first_contact"
    r = cs.prepare_draft(USER, int(args[0]), kind)
    return f"草稿#{r['id']}(待审批): {r['content'][:120]}"


def _inbox(args):
    rows = cs.inbox()
    if not rows:
        return "(收件箱空)"
    return "\n".join(f"#{r['id']} 客户{r['customer_id']}({r['name'] or '-'}): "
                     f"{r['content'][:60]}" for r in rows)


def _approve(args):
    if not args:
        return "用法: /approve <mid>"
    try:
        r = cs.approve(USER, int(args[0]))
    except ValueError as e:
        return str(e)
    return f"消息 {r['id']} 已审批发送（人审后发·已记审计）"


def _reject(args):
    if not args:
        return "用法: /reject <mid> [原因]"
    try:
        r = cs.reject(USER, int(args[0]), " ".join(args[1:]))
    except ValueError as e:
        return str(e)
    return f"消息 {r['id']} 已驳回（原因:{r['reason']}）"


def _dispatch(args):
    if not args:
        return "用法: /dispatch <id> [设计师]"
    designer_name = args[1] if len(args) > 1 else None
    r = designer.dispatch(USER, int(args[0]), designer_name)
    return f"项目#{r['id']} 已建（{'重复跳过' if r.get('dup') else '新派单'}），摘要: {r['summary'][:50]}"


def _score(args):
    if not args:
        return "用法: /score <id>"
    return str(business.score(USER, int(args[0])))


def _invite(args):
    if not args:
        return "用法: /invite <id> [时间]"
    when = args[1] if len(args) > 1 else ""
    r = business.create_invite(USER, int(args[0]), when)
    return f"邀约#{r['id']}: {r['content'][:120]}"


def _todos(args):
    items = business.check_due()
    if not items:
        return "(无待办)"
    return "\n".join(f"#{t['id']} 客户{t['customer_id']} {t['task']}" for t in items[:10])


def _kb(args):
    if not args:
        return "用法: /kb <关键词>"
    hits = designer.search(" ".join(args))
    if not hits:
        return "(知识库无命中)"
    return "\n".join(f"[{h['score']}] {h['title']} ({h['source']})\n    {h['snippet']}" for h in hits)


def _stats(args):
    from routers.stats import stats as _stats_fn
    return "\n".join(f"{k}: {v}" for k, v in _stats_fn().items())


def _config(args):
    cfg = config_loader.load_profile(_PROFILE)
    return (f"{cfg['manifest']['company']} @ kernel {cfg['manifest']['kernel_version']}\n"
            f"术语: {len(cfg['terms'])} 条｜规则: {list(cfg['rules'].keys())}\n"
            f"状态机: {'→'.join(cfg['workflow']['backbone'])}（锁定 {cfg['workflow']['locked_nodes']}）\n"
            f"闸门: {list((cfg['rules'].get('gates') or {}).keys())}")


# ---- 阶段5 承接指令处理器（设计师/工程/预算部共用） ----
def _plan(args):
    """/plan add <pid> <风格> [要点] | /plan list <pid> | /plan status <plid> <to>"""
    if not args:
        return "用法: /plan add|list|status ..."
    cmd = args[0]
    if cmd == "add" and len(args) >= 3:
        # CLI 演示通道：角色闸门由 Web/API 强制
        r = designer.add_plan(USER, int(args[1]), args[2], " ".join(args[3:]))
        return f"方案#{r['id']} 已沉淀: 项目{r['project_id']} v{r['version']} {r['style']}（初稿）"
    if cmd == "list" and len(args) >= 2:
        rows = designer.list_plans(int(args[1]))
        if not rows:
            return f"项目 {args[1]} 暂无方案"
        return "\n".join(f"#{r['id']} v{r['version']} {r['style']} {r['points'] or ''} "
                         f"[{r['status']}] {r['created_by']}" for r in rows)
    if cmd == "status" and len(args) >= 3:
        # CLI 演示通道：角色闸门由 Web/API 强制
        r = designer.status_plan(USER, int(args[1]), args[2])
        return f"方案 {r['id']}: {r['from']} → {r['to']}"
    return "用法: /plan add <pid> <风格> [要点] | /plan list <pid> | /plan status <plid> <to>"


def _quote(args):
    """/quote gen <pid> [要求] | /quote items <qid> | /quote discount <qid> <折扣> | /quote approve <qid> | /quote plan <qid>"""
    if not args:
        return "用法: /quote gen|items|discount|approve|plan ..."
    cmd = args[0]
    if cmd == "gen" and len(args) >= 2:
        # CLI 演示通道：角色闸门由 Web/API 强制
        from routers.dispatch import QuoteIn
        r = create_quote(int(args[1]), QuoteIn(user=USER, requirements=" ".join(args[2:])))
        return (f"报价#{r['id']} 已生成: 项目{r['project_id']} 合计 ¥{r['total']:,.2f}，"
                f"{r['items']} 项明细（{r['est_items']} 项估算待复核）")
    if cmd == "items" and len(args) >= 2:
        r = quote_items(int(args[1]))
        secs = " | ".join(f"{k}:{len(v)}项" for k, v in r["groups"].items())
        return (f"报价 {r['quote_id']} 合计 ¥{r['total']:,.2f} {r['discount'] * 100:.1f}折 "
                f"[{r['status']}] 明细{r['items_count']}项（{r['est_items']}项估）\n  {secs}")
    if cmd == "discount" and len(args) >= 3:
        require(USER, "quote")
        qid, disc = int(args[1]), float(args[2])
        if not (0.5 <= disc <= 1.0):
            return f"折扣需在 0.5~1.0 之间（收到 {disc}）"
        cfg = config_loader.load_profile(_PROFILE)
        need = cfg["rules"]["discount"]["need_approval_above"]
        approver = cfg["rules"]["discount"].get("approver_role", "董事长")
        with get_conn() as conn:
            q = conn.execute("SELECT status FROM quotes WHERE id=?", (qid,)).fetchone()
            if not q:
                return f"报价 {qid} 不存在"
            if q["status"] in ("已审批", "已否决", "已签约"):
                return f"报价已 {q['status']}，不可再提交折扣"
            status = "已审批" if disc >= need else "待审批"
            conn.execute("UPDATE quotes SET discount=?, status=? WHERE id=?",
                         (disc, status, qid))
            from db import audit
            audit(USER, "报价折扣", f"quotes#{qid}", before=q["status"],
                  after=f"discount={disc} status={status}")
        return (f"报价 {qid}: {disc * 100:.1f} 折 → {status}"
                + (f"（低于{need * 10:.0f}折，待 {approver} 审批）" if status == "待审批" else ""))
    if cmd == "approve" and len(args) >= 2:
        require(USER, "quote.approve")
        qid = int(args[1])
        decision = args[2] if len(args) > 2 else "已审批"
        if decision not in ("已审批", "已否决"):
            return "decision 须为 已审批/已否决"
        with get_conn() as conn:
            q = conn.execute("SELECT status FROM quotes WHERE id=?", (qid,)).fetchone()
            if not q:
                return f"报价 {qid} 不存在"
            if q["status"] != "待审批":
                return f"报价状态为 {q['status']}，不可审批"
            conn.execute("UPDATE quotes SET status=? WHERE id=?", (decision, qid))
            from db import audit
            audit(USER, "报价审批", f"quotes#{qid}", before=q["status"], after=decision)
        return f"报价 {qid} → {decision}"
    if cmd == "plan" and len(args) >= 2:
        qid = int(args[1])
        cfg = config_loader.load_profile(_PROFILE)
        with get_conn() as conn:
            q = conn.execute("SELECT total FROM quotes WHERE id=?", (qid,)).fetchone()
            if not q:
                return f"报价 {qid} 不存在"
        rows = [f"  {s['stage']}: {s['ratio'] * 100:.0f}% = ¥{q['total'] * s['ratio']:,.2f}"
                for s in cfg["rules"]["payment_stages"]]
        return f"报价 {qid} 付款计划（合计 ¥{q['total']:,.2f}）:\n" + "\n".join(rows)
    return ("用法: /quote gen <pid> [要求] | /quote items <qid> | /quote discount <qid> <折扣>"
            " | /quote approve <qid> | /quote plan <qid>")


def _pay(args):
    """/pay add <qid> <stage> <金额> [备注] | /pay plan <qid> — 签约收款（6.1）"""
    if not args:
        return "用法: /pay add|plan ..."
    cmd = args[0]
    if cmd == "add" and len(args) >= 4:
        from routers.dispatch import PaymentIn
        qid, stage, amount = int(args[1]), args[2], float(args[3])
        note = " ".join(args[4:])
        r = add_payment(qid, PaymentIn(user=USER, stage=stage, amount=amount, note=note))
        return f"收款#{r['id']} 已登记: 报价{qid} {stage} ¥{r['amount']:,.2f}"
    if cmd == "plan" and len(args) >= 2:
        r = payment_progress(int(args[1]))
        lines = [f"报价 {r['quote_id']} 收款进度（合计 ¥{r['total']:,.2f}）:"]
        lines += [f"  {s['stage']}: 应缴 ¥{s['due']:,.2f} | 已收 ¥{s['paid']:,.2f} | 待收 ¥{s['remain']:,.2f}"
                  for s in r["stages"]]
        if r["records"]:
            lines += ["  明细:"] + [f"    #{x['id']} {x['stage']} ¥{x['amount']:,.2f} "
                                    f"({x['method']}) {x['operator']} {x['note'] or ''}"
                                    for x in r["records"]]
        return "\n".join(lines)
    return "用法: /pay add <qid> <签约|阶段验收|验收> <金额> [备注] | /pay plan <qid>"


def _proj(args):
    """/proj <pid> <to> — 项目状态迁移（含 6.4 开工闸门）"""
    if len(args) < 2:
        return "用法: /proj <pid> <to>"
    from routers.dispatch import ProjectStatusIn
    r = project_transition(int(args[0]), ProjectStatusIn(user=USER, to=args[1]))
    return f"项目{r['id']}: {r['from']} → {r['to']}"


def _report(args):
    """/report <pid> <阶段> <内容> — 工地日报（项目经理）"""
    if len(args) < 3:
        return "用法: /report <pid> <阶段> <内容>"
    # CLI 演示通道：角色闸门由 Web/API 强制
    try:
        r = engineer.add_report(USER, int(args[0]), args[1], " ".join(args[2:]))
    except ValueError as e:
        return str(e)
    return f"日报#{r['id']} 已记录: 项目{r['project_id']} [{r['stage']}] {r['content'][:40]}"


def _inspect(args):
    """/inspect <pid> <节点> <合格|整改> [备注] — 五节点验收（项目经理）"""
    if len(args) < 3:
        return "用法: /inspect <pid> <节点> <合格|整改> [备注]"
    # CLI 演示通道：角色闸门由 Web/API 强制
    try:
        r = engineer.inspect(USER, int(args[0]), args[1], args[2], " ".join(args[3:]))
    except ValueError as e:
        return str(e)
    return f"项目{r['project_id']} {r['node']}验收: {r['result']}" + (f"（{r['note']}）" if r["note"] else "")


def _detail(args):
    """/detail <pid> — 项目承接全景（含收款进度+软装+售后）"""
    if not args:
        return "用法: /detail <pid>"
    pid = int(args[0])
    with get_conn() as conn:
        p = conn.execute(
            "SELECT p.id,p.designer,p.summary,p.status,c.name,c.estate,c.area,c.budget_range "
            "FROM projects p LEFT JOIN customers c ON c.id=p.customer_id "
            "WHERE p.id=?", (pid,)).fetchone()
        if not p:
            return f"项目 {pid} 不存在"
        quote = conn.execute(
            "SELECT id,total,discount,status FROM quotes WHERE project_id=? "
            "ORDER BY id DESC LIMIT 1", (pid,)).fetchone()
    plans = designer.list_plans(pid)
    inspections = engineer.list_inspections(pid)
    reports = engineer.list_reports(pid)
    soft_items = soft.list_items(pid)
    as_rows = aftersales.list(project_id=pid)
    lines = [f"项目#{p['id']} {p['name'] or '-'} {p['estate'] or '-'} {p['area'] or '-'}㎡ "
             f"预算{p['budget_range'] or '-'} 状态:{p['status']} 设计师:{p['designer'] or '-'}",
             f"日报 {len(reports)} 条"]
    lines.append("方案:")
    lines += [f"  v{r['version']} {r['style']} {r['points'] or ''} [{r['status']}]"
              for r in plans] or ["  (无)"]
    if quote:
        lines.append(f"报价#{quote['id']}: ¥{quote['total']:,.2f} "
                     f"{quote['discount'] * 100:.1f}折 [{quote['status']}]")
        try:
            pp = payment_progress(quote["id"])
            lines += [f"  {s['stage']}: 应缴 ¥{s['due']:,.2f} | 已收 ¥{s['paid']:,.2f} | 待收 ¥{s['remain']:,.2f}"
                      for s in pp["stages"]]
        except Exception:
            pass
    else:
        lines.append("报价: (无)")
    lines.append("验收: " + (" | ".join(f"{r['node']}:{r['result']}" for r in inspections) or "待验收"))
    lines.append(f"软装: {len(soft_items)} 项 | 售后: {len(as_rows)} 条")
    return "\n".join(lines)


# ---- 编队 v3 新增指令（总经办/材料/软装/售后） ----
def _ceo(args):
    """/ceo approvals|dashboard|audit [n]|coord <备注>"""
    if not args:
        return "用法: /ceo approvals|dashboard|audit [n]|coord <备注>"
    cmd = args[0]
    if cmd == "approvals":
        a = ceo.approval_inbox(USER)
        lines = [f"待审消息草稿: {len(a['pending_messages'])} 条",
                 f"待审批报价: {len(a['pending_quote_approvals'])} 条",
                 f"待处理售后: {len(a['pending_after_sales'])} 条"]
        for q in a["pending_quote_approvals"][:5]:
            lines.append(f"  [报价#{q['id']}] 项目{q['project_id']} ¥{q['total']:,.2f} {q['discount'] * 100:.1f}折")
        for s in a["pending_after_sales"][:5]:
            lines.append(f"  [售后#{s['id']}] 项目{s['project_id']} {s['kind']}: {s['title'][:30]}")
        return "\n".join(lines)
    if cmd == "dashboard":
        d = ceo.dashboard(USER)
        lines = ["客户漏斗: " + " | ".join(f"{r['status']}:{r['n']}" for r in d["customers_by_status"]),
                 "项目: " + " | ".join(f"{r['status']}:{r['n']}" for r in d["projects_by_status"]),
                 f"累计收款: ¥{d['payments_collected']:,.2f}",
                 f"已审批/签约报价总额: ¥{d['approved_quotes_total']:,.2f}",
                 f"验收合格节点: {d['inspections_passed']} 个 | 未办待办: {d['open_todos']} 条"]
        return "\n".join(lines)
    if cmd == "audit":
        n = int(args[1]) if len(args) > 1 else 10
        try:
            rows = ceo.audit_trail(USER, n)
        except Exception as e:
            return f"审计权限不足或错误: {e}"
        if not rows:
            return "(无审计记录)"
        return "\n".join(f"#{r['id']} {r['created_at']} {r['user']} {r['action']} {r['target']} "
                         f"({r['before'] or ''}→{r['after'] or ''})" for r in rows)
    if cmd == "coord" and len(args) >= 2:
        r = ceo.coordinate(USER, " ".join(args[1:]))
        return f"协调记录已留痕: {r['note'][:60]}"
    return "用法: /ceo approvals|dashboard|audit [n]|coord <备注>"


def _mat(args):
    """/mat list [分类] | /mat list4quote <qid>"""
    if not args:
        return "用法: /mat list [分类] | /mat list4quote <qid>"
    cmd = args[0]
    if cmd == "list":
        rows = material.list_materials(category=args[1] if len(args) > 1 else "")
        if not rows:
            return "(材料库无数据——契约线三表灌装后可查)"
        return "\n".join(f"  {r['category'] or '-'} {r['name']} {r['spec'] or ''} "
                         f"¥{r['price']} {r['supplier'] or ''} [{r['tags'] or ''}]" for r in rows[:20])
    if cmd == "list4quote" and len(args) >= 2:
        try:
            r = material.build_material_list(int(args[1]))
        except ValueError as e:
            return str(e)
        lines = [f"报价 {r['quote_id']} 主材清单: {r['items_count']} 项（{r['est_items']} 项估）"
                 f"合计 ¥{r['material_total']:,.2f}"]
        lines += [f"  {x['name']} {x['spec'] or ''} ×{x['qty']} ¥{x['unit_price']} "
                  f"= ¥{x['amount']:,.2f}{'（估）' if x['est'] else ''}" for x in r["items"][:20]]
        return "\n".join(lines)
    return "用法: /mat list [分类] | /mat list4quote <qid>"


def _soft(args):
    """/soft add|list|up|rm"""
    if not args:
        return "用法: /soft add <pid> <分类> <品名> [--spec x --qty n --price p] | /soft list <pid> | /soft up <id> <k=v...> | /soft rm <id>"
    cmd = args[0]
    if cmd == "add" and len(args) >= 4:
        pid, category, name = int(args[1]), args[2], args[3]
        opts = {}
        rest = args[4:]
        for i in range(0, len(rest) - 1, 2):
            if rest[i].startswith("--"):
                opts[rest[i][2:]] = rest[i + 1]
        try:
            r = soft.add_item(USER, pid, category, name, spec=opts.get("spec", ""),
                              qty=float(opts.get("qty", 1)), unit_price=float(opts.get("price", 0)),
                              note=opts.get("note", ""))
        except ValueError as e:
            return str(e)
        return (f"软装#{r['id']} 已录入: 项目{r['project_id']} {r['category']} {r['name']} "
                f"×{r['qty']} ¥{r['unit_price']} = ¥{r['amount']:,.2f}")
    if cmd == "list" and len(args) >= 2:
        try:
            r = soft.build_soft_list(int(args[1]))
        except ValueError as e:
            return str(e)
        if not r["items_count"]:
            return f"项目 {args[1]} 暂无软装项"
        lines = [f"项目 {r['project_id']} 软装清单: {r['items_count']} 项 合计 ¥{r['total']:,.2f}"]
        for s in r["sections"]:
            lines.append(f"  【{s['category']}】{s['count']} 项 小计 ¥{s['subtotal']:,.2f}")
            lines += [f"    #{x['id']} {x['name']} {x['spec'] or ''} ×{x['qty']} "
                      f"¥{x['unit_price']} = ¥{x['amount']:,.2f} [{x['status']}]" for x in s["items"]]
        return "\n".join(lines)
    if cmd == "up" and len(args) >= 3:
        item_id = int(args[1])
        fields = {}
        for kv in args[2:]:
            if "=" in kv:
                k, v = kv.split("=", 1)
                if k in ("qty", "unit_price"):
                    v = float(v)
                fields[k] = v
        try:
            r = soft.update_item(USER, item_id, **fields)
        except ValueError as e:
            return str(e)
        return (f"软装#{r['id']} 已更新: {r['category']} {r['name']} ×{r['qty']} "
                f"= ¥{r['amount']:,.2f} [{r['status']}]")
    if cmd == "rm" and len(args) >= 2:
        try:
            r = soft.remove_item(USER, int(args[1]))
        except ValueError as e:
            return str(e)
        return f"软装#{r['id']} 已删除"
    return "用法: /soft add <pid> <分类> <品名> [--spec x --qty n --price p] | /soft list <pid> | /soft up <id> <k=v...> | /soft rm <id>"


def _as(args):
    """/as warranty|ticket|list|status|due"""
    if not args:
        return "用法: /as warranty <pid> [竣工日期] | /as ticket <pid> <标题> [内容] | /as list [pid] | /as status <id> <状态> [结果] | /as due"
    cmd = args[0]
    if cmd == "warranty" and len(args) >= 2:
        try:
            r = aftersales.register_warranty(USER, int(args[1]),
                                             args[2] if len(args) > 2 else "")
        except ValueError as e:
            return str(e)
        return "质保登记完成: " + " | ".join(f"{x['warranty_type']}→{x['warranty_until']}"
                                             for x in r["rows"])
    if cmd == "ticket" and len(args) >= 3:
        try:
            r = aftersales.create_ticket(USER, int(args[1]), args[2],
                                         " ".join(args[3:]))
        except ValueError as e:
            return str(e)
        return f"售后工单#{r['id']} 已创建: 项目{r['project_id']} {r['title']} [{r['status']}]"
    if cmd == "list":
        pid = int(args[1]) if len(args) > 1 else None
        rows = aftersales.list(project_id=pid)
        if not rows:
            return "(无售后记录)"
        return "\n".join(f"#{r['id']} 项目{r['project_id']} {r['kind']} {r['title']} "
                         f"[{r['status']}] {r['warranty_until'] or ''} {r['result'] or ''}"
                         for r in rows[:20])
    if cmd == "status" and len(args) >= 3:
        try:
            r = aftersales.update_status(USER, int(args[1]), args[2],
                                         " ".join(args[3:]))
        except ValueError as e:
            return str(e)
        return f"售后#{r['id']} → {r['status']}" + (f"（{r['result']}）" if r["result"] else "")
    if cmd == "due":
        created = aftersales.check_due()
        return (f"回访/质保提醒生成 {len(created)} 条: "
                + ("、".join(set(created)) if created else "（无新增）"))
    return "用法: /as warranty <pid> [竣工日期] | /as ticket <pid> <标题> [内容] | /as list [pid] | /as status <id> <状态> [结果] | /as due"


def _help_text():
    lines = ["[中控] 获客线指令:"]
    for k, v in bus.COMMANDS.items():
        lines.append(f"  /{k}  {v}")
    lines += ["  /leads 线索列表 | /lead add <phone> 录入 | /lead <id> 详情",
              "  /tag <id> <标签> | /status <id> <to> | /score <id> | /invite <id>",
              "  /draft <id> <kind> | /inbox | /approve <mid> | /reject <mid>",
              "  /dispatch <id> [设计师] | /todos | /kb <词> | /stats | /config",
              "",
              "[中控] 阶段5 承接指令:",
              "  /plan add <pid> <风格> [要点] | /plan list <pid> | /plan status <plid> <to>",
              "  /quote gen <pid> [要求] | /quote items <qid> | /quote discount <qid> <折扣>",
              "  /quote approve <qid> | /quote plan <qid>",
              "  /pay add <qid> <签约|阶段验收|验收> <金额> [备注] | /pay plan <qid>",
              "  /proj <pid> <to>（含开工闸门：签约款收足才放行）",
              "  /report <pid> <阶段> <内容> | /inspect <pid> <节点> <合格|整改> [备注]",
              "  /detail <pid>",
              "",
              "[中控] 编队 v3 新增（P3-P7）:",
              "  /ceo approvals|dashboard|audit [n]|coord <备注>",
              "  /mat list [分类] | /mat list4quote <qid>",
              "  /soft add <pid> <分类> <品名> [--spec x --qty n --price p] | /soft list <pid>",
              "  /soft up <id> <k=v...> | /soft rm <id>",
              "  /as warranty <pid> [竣工日期] | /as ticket <pid> <标题> [内容]",
              "  /as list [pid] | /as status <id> <状态> [结果] | /as due"]
    return "\n".join(lines)


def register_all():
    for cmd, fn in [("leads", _leads), ("tag", _tag), ("status", _status),
                    ("draft", _draft), ("inbox", _inbox), ("approve", _approve),
                    ("reject", _reject), ("dispatch", _dispatch), ("score", _score),
                    ("invite", _invite), ("todos", _todos), ("kb", _kb),
                    ("stats", _stats), ("config", _config),
                    ("plan", _plan), ("quote", _quote), ("pay", _pay), ("proj", _proj),
                    ("report", _report), ("inspect", _inspect), ("detail", _detail),
                    ("ceo", _ceo), ("mat", _mat), ("soft", _soft), ("as", _as)]:
        bus.register(cmd, lambda ctx, *a, _fn=fn: _fn(list(a)))
    bus.register("lead", lambda ctx, *a: _lead_add(list(a)) if a and a[0] == "add"
                 else _lead_get(list(a)))
    bus.register("help", lambda ctx, *a: _help_text())


def main():
    register_all()
    print("== 家装 AI 智能体平台 · 中控（壹城精工 · 编队v3 九 Agent 全就位）==")
    print("输入 /help 查看指令；exit 退出")
    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见")
            break
        if not text:
            continue
        if text.lower() == "exit":
            print("再见")
            break
        try:
            print(bus.route(text))
        except Exception as e:
            print(f"[中控] 错误: {e}")


if __name__ == "__main__":
    main()
