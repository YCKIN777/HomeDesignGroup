# -*- coding: utf-8 -*-
"""dispatch 路由：M4 派单建项目 + 5.1 项目状态迁移（量房→设计→…→验收交付）"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.dispatch_agent import DispatchAgent
from db import get_conn, audit
from kernel import config_loader
from kernel import decisions as _dec
from kernel.roles import require as _perm

router = APIRouter(prefix="/api", tags=["dispatch"])

_PROFILE = "壹城精工"


class DispatchIn(BaseModel):
    user: str
    customer_id: int
    designer: str = None


class ProjectStatusIn(BaseModel):
    user: str
    to: str


class PlanIn(BaseModel):
    user: str
    style: str = ""
    points: str = ""


class PlanStatusIn(BaseModel):
    user: str
    status: str   # 初稿/评审中/已定稿/已否决


class QuoteIn(BaseModel):
    user: str
    requirements: str = ""


class DiscountIn(BaseModel):
    user: str
    discount: float   # 0.98=98折


class QuoteApproveIn(BaseModel):
    user: str
    decision: str = "已审批"   # 已审批/已否决


class QuoteItemIn(BaseModel):
    user: str
    qty: float                # 复核后工程量


class ReportIn(BaseModel):
    user: str
    stage: str
    content: str


class InspectionIn(BaseModel):
    user: str
    result: str      # 合格/整改
    note: str = ""


class PaymentIn(BaseModel):
    user: str
    stage: str              # 签约/阶段验收/验收
    amount: float           # 本次实收
    method: str = "转账"     # 转账/刷卡/现金/其他
    paid_at: str = ""       # 收款日期（空=今天）
    note: str = ""


class ExportIn(BaseModel):
    user: str


@router.post("/projects/{pid}/plans")
def create_plan(pid: int, body: PlanIn):
    """设计方案沉淀：项目下新建一版方案（version 自动递增）"""
    _perm(body.user, "design_plan")
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM projects WHERE id=?", (pid,)).fetchone()
        if not row:
            raise HTTPException(404, f"项目 {pid} 不存在")
        cur = conn.execute(
            "SELECT COALESCE(MAX(version),0)+1 AS v FROM design_plans WHERE project_id=?",
            (pid,)).fetchone()["v"]
        cur2 = conn.execute(
            "INSERT INTO design_plans(project_id, version, style, points, status, created_by) "
            "VALUES(?,?,?,?,'初稿',?)",
            (pid, cur, body.style, body.points, body.user))
        plid = cur2.lastrowid
        audit(body.user, "设计方案", f"design_plans#{plid}",
              after=f"project={pid} v{cur} {body.style}")
    return {"id": plid, "project_id": pid, "version": cur, "style": body.style,
            "points": body.points, "status": "初稿"}


@router.get("/projects/{pid}/plans")
def list_plans(pid: int):
    """项目方案列表（按版本倒序）"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, version, style, points, status, created_by, created_at "
            "FROM design_plans WHERE project_id=? ORDER BY version DESC", (pid,)).fetchall()
    return {"total": len(rows), "items": [dict(r) for r in rows]}


@router.post("/projects/plans/{plid}/status")
def plan_status(plid: int, body: PlanStatusIn):
    """方案状态流转：初稿→评审中→已定稿/已否决"""
    _perm(body.user, "design_plan")
    allowed = {"初稿": ["评审中", "已否决"], "评审中": ["已定稿", "已否决", "初稿"],
               "已定稿": [], "已否决": []}
    with get_conn() as conn:
        row = conn.execute(
            "SELECT status, project_id FROM design_plans WHERE id=?", (plid,)).fetchone()
        if not row:
            raise HTTPException(404, f"方案 {plid} 不存在")
        cur = row["status"]
        if body.status not in allowed.get(cur, []):
            raise HTTPException(400, f"方案状态流转不合法: {cur} -> {body.status}"
                                     f"（允许: {allowed.get(cur) or '无'}）")
        conn.execute("UPDATE design_plans SET status=? WHERE id=?", (body.status, plid))
        audit(body.user, "方案状态", f"design_plans#{plid}", before=cur, after=body.status)
    return {"id": plid, "project_id": row["project_id"], "from": cur, "to": body.status}


# ---------- 5.3 报价承接：模板明细 + 折扣审批 + 付款计划 ----------

def _est_qty(area: float, unit: str, cfg: dict, section: str = "") -> tuple:
    """按单位估算工程量（est=1 标记，量房后设计师复核修正）
    规则来自配置包 rules.quote_est（每家公司可调）：
    面积型→area×area_coef（section_coefs 可分类覆盖）；线型→√area×perimeter_coef；
    单件型→unit_default_qty；无法识别→fallback_qty
    """
    u = unit or ""
    if any(k in u for k in cfg.get("area_units", ["㎡"])):
        coef = cfg.get("area_coef", 1.0)
        sec = section or ""
        for kw, sc in (cfg.get("section_coefs") or {}).items():
            if kw and kw in sec:
                coef = sc
                break
        return round(area * coef, 1), 1
    if any(k in u for k in cfg.get("perimeter_units", ["m"])):
        return round((area ** 0.5) * cfg.get("perimeter_coef", 4.0), 1), 1
    if any(k in u for k in cfg.get("unit_units", ["个", "项", "套"])):
        return float(cfg.get("unit_default_qty", 1.0)), 1
    return float(cfg.get("fallback_qty", 0.0)), 0


@router.post("/projects/{pid}/quote")
def create_quote(pid: int, body: QuoteIn):
    """生成项目报价草稿：从报价模板（预算范本）生成明细，按配置规则估算工程量"""
    _perm(body.user, "quote")
    est_cfg = (config_loader.load_profile(_PROFILE)["rules"].get("quote_est") or {})
    with get_conn() as conn:
        p = conn.execute("SELECT p.status, c.area, c.budget_range FROM projects p "
                         "LEFT JOIN customers c ON c.id=p.customer_id "
                         "WHERE p.id=?", (pid,)).fetchone()
        if not p:
            raise HTTPException(404, f"项目 {pid} 不存在")
        if p["status"] == "签约":
            raise HTTPException(400, "项目已签约，不能再生成报价")
        area = p["area"] or 0.0
        tpls = conn.execute(
            "SELECT section, item, spec, unit, unit_price, sort FROM quote_templates "
            "ORDER BY source, sort").fetchall()
        if not tpls:
            raise HTTPException(400, "报价模板为空：先运行 scripts/import_quote_template.py 导入预算范本")
        items, total = [], 0.0
        for t in tpls:
            qty, est = _est_qty(area, t["unit"], est_cfg, t["section"])
            amount = round(qty * (t["unit_price"] or 0.0), 2)
            total += amount
            items.append((t["section"], t["item"], t["spec"], t["unit"],
                          t["unit_price"] or 0.0, qty, amount, est, t["sort"]))
        total = round(total, 2)
        cur = conn.execute(
            "INSERT INTO quotes(project_id, total, status, created_by) VALUES(?,?,'草稿',?)",
            (pid, total, body.user))
        qid = cur.lastrowid
        conn.execute("BEGIN")
        try:
            conn.executemany(
                "INSERT INTO quote_items(quote_id, section, item, spec, unit, unit_price, "
                "qty, amount, est, sort) VALUES(?,?,?,?,?,?,?,?,?,?)",
                [(qid, *it) for it in items])
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        est_n = sum(1 for it in items if it[7])
        audit(body.user, "报价生成", f"quotes#{qid}",
              after=f"area={area} items={len(items)} total={total}")
    return {"id": qid, "project_id": pid, "total": total, "area": area,
            "budget_range": p["budget_range"], "status": "草稿",
            "items": len(items), "est_items": est_n,
            "est_rule": "预算范本 325 条明细；面积型工序按整屋面积粗估（上限值），"
                        "量房后逐行修正（est 清零）或调 /estimate 重估"}


@router.post("/quotes/{qid}/estimate")
def quote_estimate(qid: int, body: QuoteItemIn):
    """按面积重新预填估算工程量：仅覆盖 est=1 的行，人工修正过的行（est=0）不覆盖"""
    _perm(body.user, "quote")
    est_cfg = (config_loader.load_profile(_PROFILE)["rules"].get("quote_est") or {})
    with get_conn() as conn:
        q = conn.execute("SELECT p.id, c.area FROM quotes q "
                         "JOIN projects p ON p.id=q.project_id "
                         "LEFT JOIN customers c ON c.id=p.customer_id "
                         "WHERE q.id=?", (qid,)).fetchone()
        if not q:
            raise HTTPException(404, f"报价 {qid} 不存在")
        area = body.qty if body.qty > 0 else (q["area"] or 0.0)
        rows = conn.execute("SELECT id, unit, unit_price, est, section FROM quote_items "
                            "WHERE quote_id=?", (qid,)).fetchall()
        upd, total = 0, 0.0
        conn.execute("BEGIN")
        try:
            for r in rows:
                if not r["est"]:
                    continue                  # 人工修正过的不覆盖
                qty, _ = _est_qty(area, r["unit"], est_cfg, r["section"] or "")
                amt = round(qty * (r["unit_price"] or 0.0), 2)
                conn.execute("UPDATE quote_items SET qty=?, amount=?, est=1 WHERE id=?",
                             (qty, amt, r["id"]))
                upd += 1
                total += amt
            total = round(total, 2)
            conn.execute("UPDATE quotes SET total=? WHERE id=?", (total, qid))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        audit(body.user, "报价重估", f"quotes#{qid}",
              after=f"area={area} 重估{upd}条 total={total}")
    return {"quote_id": qid, "area": area, "re_estimated": upd,
            "kept_manual": len(rows) - upd, "new_total": total}


@router.get("/quotes/{qid}/items")
def quote_items(qid: int):
    """报价明细（按分类分组）+ 汇总"""
    with get_conn() as conn:
        q = conn.execute("SELECT total, discount, status FROM quotes WHERE id=?",
                         (qid,)).fetchone()
        if not q:
            raise HTTPException(404, f"报价 {qid} 不存在")
        rows = conn.execute(
            "SELECT id, section, item, spec, unit, unit_price, qty, amount, est, sort "
            "FROM quote_items WHERE quote_id=? ORDER BY sort", (qid,)).fetchall()
    groups = {}
    for r in rows:
        groups.setdefault(r["section"] or "未分类", []).append(dict(r))
    est_n = sum(1 for r in rows if r["est"])
    return {"quote_id": qid, "total": q["total"], "discount": q["discount"],
            "status": q["status"], "items_count": len(rows), "est_items": est_n,
            "groups": groups}


@router.post("/quotes/{qid}/items/{iid}")
def quote_item_update(qid: int, iid: int, body: QuoteItemIn):
    """更新明细工程量 → 重算该行金额与报价总额（量房后复核修正）"""
    _perm(body.user, "quote")
    if body.qty < 0:
        raise HTTPException(400, "工程量不能为负")
    with get_conn() as conn:
        row = conn.execute("SELECT unit_price FROM quote_items WHERE id=? AND quote_id=?",
                           (iid, qid)).fetchone()
        if not row:
            raise HTTPException(404, f"明细 {iid} 不在报价 {qid} 中")
        amount = round(body.qty * row["unit_price"], 2)
        conn.execute("UPDATE quote_items SET qty=?, amount=?, est=0 WHERE id=?",
                     (body.qty, amount, iid))
        t = conn.execute("SELECT COALESCE(SUM(amount),0) AS s FROM quote_items "
                         "WHERE quote_id=?", (qid,)).fetchone()["s"]
        conn.execute("UPDATE quotes SET total=? WHERE id=?", (round(t, 2), qid))
        audit(body.user, "报价明细修正", f"quote_items#{iid}",
              after=f"qty={body.qty} amount={amount}")
    return {"id": iid, "quote_id": qid, "qty": body.qty, "amount": amount,
            "new_total": round(t, 2)}


@router.post("/quotes/{qid}/discount")
def quote_discount(qid: int, body: DiscountIn):
    """提交折扣：低于 9.8 折（rules.discount）自动转待审批（审批人=董事长）"""
    _perm(body.user, "quote")
    cfg = config_loader.load_profile(_PROFILE)
    need = cfg["rules"]["discount"]["need_approval_above"]   # 0.98
    approver = cfg["rules"]["discount"].get("approver_role", "董事长")
    if not (0.5 <= body.discount <= 1.0):
        raise HTTPException(400, f"折扣需在 0.5~1.0 之间（收到 {body.discount}）")
    with get_conn() as conn:
        q = conn.execute("SELECT status FROM quotes WHERE id=?", (qid,)).fetchone()
        if not q:
            raise HTTPException(404, f"报价 {qid} 不存在")
        if q["status"] in ("已审批", "已否决", "已签约"):
            raise HTTPException(400, f"报价已 {q['status']}，不可再提交折扣")
        status = "已审批" if body.discount >= need else "待审批"
        conn.execute("UPDATE quotes SET discount=?, status=? WHERE id=?",
                     (body.discount, status, qid))
        audit(body.user, "报价折扣", f"quotes#{qid}", before=str(q["status"]),
              after=f"discount={body.discount} status={status} (阈值{need}, 审批人{approver})")
    return {"id": qid, "discount": body.discount, "status": status,
            "need_approval": status == "待审批", "approver": approver}


@router.post("/quotes/{qid}/approve")
def quote_approve(qid: int, body: QuoteApproveIn):
    """审批折扣报价（权限 quote.approve；审批人按配置 approver_role）"""
    _perm(body.user, "quote.approve")
    cfg = config_loader.load_profile(_PROFILE)
    approver = cfg["rules"]["discount"].get("approver_role", "董事长")
    with get_conn() as conn:
        q = conn.execute("SELECT status, discount FROM quotes WHERE id=?", (qid,)).fetchone()
        if not q:
            raise HTTPException(404, f"报价 {qid} 不存在")
        if q["status"] != "待审批":
            raise HTTPException(400, f"报价状态为 {q['status']}，不可审批")
        if body.decision not in ("已审批", "已否决"):
            raise HTTPException(400, "decision 须为 已审批/已否决")
        conn.execute("UPDATE quotes SET status=? WHERE id=?", (body.decision, qid))
        audit(body.user, "报价审批", f"quotes#{qid}", before=q["status"], after=body.decision)
    return {"id": qid, "discount": q["discount"], "decision": body.decision,
            "approver": approver}


@router.get("/quotes/{qid}/payment-plan")
def payment_plan(qid: int):
    """付款计划：按 rules.payment_stages（壹城：签约60/阶段验收35/验收5）"""
    cfg = config_loader.load_profile(_PROFILE)
    stages = cfg["rules"]["payment_stages"]
    with get_conn() as conn:
        q = conn.execute("SELECT total FROM quotes WHERE id=?", (qid,)).fetchone()
        if not q:
            raise HTTPException(404, f"报价 {qid} 不存在")
    total = q["total"]
    rows = [{**s, "amount": round(total * s["ratio"], 2)} for s in stages]
    return {"quote_id": qid, "total": total, "stages": rows}


# ---------- 6.1 签约收款闭环：收款登记 + 进度 ----------

def _payment_progress(conn, qid: int, stages: list, total: float):
    """各阶段 应缴/已收/剩余 + 收款明细"""
    paid = {}
    recs = conn.execute(
        "SELECT id, stage, amount, method, paid_at, operator, note, created_at "
        "FROM payments WHERE quote_id=? ORDER BY id", (qid,)).fetchall()
    for r in recs:
        paid[r["stage"]] = paid.get(r["stage"], 0.0) + r["amount"]
    prog = []
    for st in stages:
        due = round(total * st["ratio"], 2)
        got = round(paid.get(st["stage"], 0.0), 2)
        prog.append({"stage": st["stage"], "ratio": st["ratio"],
                     "due": due, "paid": got, "remain": round(due - got, 2)})
    return {"stages": prog, "records": [dict(r) for r in recs]}


@router.post("/quotes/{qid}/payments")
def add_payment(qid: int, body: PaymentIn):
    """登记一笔收款：校验阶段合法、不超该阶段剩余应缴"""
    _perm(body.user, "quote")
    cfg = config_loader.load_profile(_PROFILE)
    stages = cfg["rules"]["payment_stages"]
    names = [x["stage"] for x in stages]
    if body.stage not in names:
        raise HTTPException(400, f"阶段必须是 {'/'.join(names)}")
    if body.amount <= 0:
        raise HTTPException(400, "收款金额必须大于 0")
    with get_conn() as conn:
        q = conn.execute("SELECT total FROM quotes WHERE id=?", (qid,)).fetchone()
        if not q:
            raise HTTPException(404, f"报价 {qid} 不存在")
        st = next(x for x in stages if x["stage"] == body.stage)
        due = round(q["total"] * st["ratio"], 2)
        got = conn.execute(
            "SELECT COALESCE(SUM(amount),0) AS s FROM payments "
            "WHERE quote_id=? AND stage=?", (qid, body.stage)).fetchone()["s"]
        remain = round(due - got, 2)
        if body.amount > remain + 1e-6:
            raise HTTPException(400, f"{body.stage} 阶段已收 {got:.2f}，应缴 {due:.2f}，剩余可收 {remain:.2f}")
        cur = conn.execute(
            "INSERT INTO payments(quote_id, stage, amount, method, paid_at, operator, note) "
            "VALUES(?,?,?,?,?,?,?)",
            (qid, body.stage, body.amount, body.method,
             body.paid_at or "", body.user, body.note))
        pid = cur.lastrowid
        audit(body.user, "收款登记", f"payments#{pid}",
              after=f"quote={qid} stage={body.stage} amount={body.amount}")
    return {"id": pid, "quote_id": qid, "stage": body.stage, "amount": body.amount}


@router.get("/quotes/{qid}/payments")
def payment_progress(qid: int):
    """收款进度：应缴/已收/剩余 + 明细"""
    cfg = config_loader.load_profile(_PROFILE)
    stages = cfg["rules"]["payment_stages"]
    with get_conn() as conn:
        q = conn.execute("SELECT total FROM quotes WHERE id=?", (qid,)).fetchone()
        if not q:
            raise HTTPException(404, f"报价 {qid} 不存在")
        prog = _payment_progress(conn, qid, stages, q["total"])
    return {"quote_id": qid, "total": q["total"], **prog}


# ---------- 6.3 报价单导出：325 条明细 → 客户版 Excel ----------

@router.post("/quotes/{qid}/export")
def export_quote(qid: int, body: ExportIn):
    """生成客户版报价单 xlsx（明细分组+小计+合计+付款计划+质保），落 exports/ 目录"""
    _perm(body.user, "quote")
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    import os
    cfg = config_loader.load_profile(_PROFILE)
    with get_conn() as conn:
        q = conn.execute(
            "SELECT q.id, q.total, q.discount, q.status, q.created_by, "
            "       p.id AS pid, p.designer, c.name, c.phone, c.estate, c.area, c.budget_range "
            "FROM quotes q JOIN projects p ON p.id=q.project_id "
            "LEFT JOIN customers c ON c.id=p.customer_id WHERE q.id=?", (qid,)).fetchone()
        if not q:
            raise HTTPException(404, f"报价 {qid} 不存在")
        items = conn.execute(
            "SELECT section, item, spec, unit, unit_price, qty, amount, est "
            "FROM quote_items WHERE quote_id=? ORDER BY sort", (qid,)).fetchall()
        prog = _payment_progress(conn, qid, cfg["rules"]["payment_stages"], q["total"])
    wb = Workbook()
    ws = wb.active
    ws.title = "报价单"
    thin = Side(style="thin", color="999999")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    hd_fill = PatternFill("solid", fgColor="1F3A4D")
    sec_fill = PatternFill("solid", fgColor="EAF1F6")
    hd_font = Font(color="FFFFFF", bold=True)
    sec_font = Font(bold=True)
    bold = Font(bold=True)
    ws.merge_cells("A1:G1")
    ws["A1"] = "壹城精工 · 装修项目报价单"
    ws["A1"].font = Font(size=16, bold=True)
    ws.merge_cells("A2:G2")
    ws["A2"] = f"报价单号：Q{qid} · 生成日期：{__import__('datetime').datetime.now().strftime('%Y-%m-%d')}"
    info = [
        f"客户：{q['name'] or '-'}（{q['phone'] or '-'}）",
        f"楼盘：{q['estate'] or '-'} · 面积：{q['area'] or '-'}㎡",
        f"预算：{q['budget_range'] or '-'} · 设计师：{q['designer'] or '-'}",
        f"报价总额：¥{q['total']:,.2f} · 折扣：{q['discount'] * 100:.1f}折 · 状态：{q['status']}",
    ]
    r = 4
    for i, line in enumerate(info):
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)
        ws.cell(row=r, column=1, value=line)
        r += 1
    r += 1
    headers = ["序号", "项目", "工艺/规格", "单位", "单价(元)", "工程量", "金额(元)"]
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=r, column=c, value=h)
        cell.fill = hd_fill
        cell.font = hd_font
        cell.border = border
        cell.alignment = Alignment(horizontal="center")
    r += 1
    sec_total, grand, idx = 0.0, 0.0, 0
    sec_name = None
    for it in items:
        if it["section"] != sec_name:
            if sec_name is not None:
                ws.cell(row=r, column=6, value="小计")
                ws.cell(row=r, column=6).font = bold
                ws.cell(row=r, column=7, value=round(sec_total, 2))
                ws.cell(row=r, column=7).font = bold
                for c in range(1, 8):
                    ws.cell(row=r, column=c).border = border
                r += 1
                grand += sec_total
            sec_name = it["section"]
            sec_total = 0.0
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)
            ws.cell(row=r, column=1, value=sec_name)
            ws.cell(row=r, column=1).fill = sec_fill
            ws.cell(row=r, column=1).font = sec_font
            r += 1
        idx += 1
        vals = [idx, it["item"], it["spec"], it["unit"], it["unit_price"],
                it["qty"], round(it["qty"] * it["unit_price"], 2)]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.border = border
            if c == 3 and it["spec"]:
                cell.alignment = Alignment(wrap_text=True)
        sec_total += vals[6]
        r += 1
    if sec_name is not None:
        ws.cell(row=r, column=6, value="小计")
        ws.cell(row=r, column=6).font = bold
        ws.cell(row=r, column=7, value=round(sec_total, 2))
        ws.cell(row=r, column=7).font = bold
        for c in range(1, 8):
            ws.cell(row=r, column=c).border = border
        r += 1
        grand += sec_total
    ws.cell(row=r, column=6, value="合计（元）")
    ws.cell(row=r, column=6).font = Font(bold=True, size=13)
    ws.cell(row=r, column=7, value=round(grand, 2))
    ws.cell(row=r, column=7).font = Font(bold=True, size=13)
    r += 2
    ws.cell(row=r, column=1, value="付款计划").font = bold
    r += 1
    for c, h in enumerate(["阶段", "比例", "应缴(元)", "已收(元)", "剩余(元)"], 1):
        cell = ws.cell(row=r, column=c, value=h)
        cell.fill = hd_fill
        cell.font = hd_font
        cell.border = border
    r += 1
    for st in prog["stages"]:
        for c, v in enumerate([st["stage"], f"{st['ratio'] * 100:.0f}%", st["due"], st["paid"], st["remain"]], 1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.border = border
        r += 1
    r += 1
    ws.cell(row=r, column=1, value="质保条款").font = bold
    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)
    ws.cell(row=r, column=1, value=f"整体质保 {cfg['rules'].get('warranty', {}).get('overall', '2')} 年；防水 {cfg['rules'].get('warranty', {}).get('waterproof', '10')} 年。")
    r += 2
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)
    ws.cell(row=r, column=1, value="注：标“估”的工程量为按面积估算值，量房复核后以实际工程量为准。")
    width = [6, 22, 34, 8, 12, 12, 14]
    from openpyxl.utils import get_column_letter
    for i, w in enumerate(width, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "exports")
    os.makedirs(out_dir, exist_ok=True)
    fname = f"quote_{qid}.xlsx"
    out = os.path.join(out_dir, fname)
    wb.save(out)
    audit(body.user, "报价导出", f"quotes#{qid}", after=fname)
    return {"quote_id": qid, "file": fname, "url": f"/exports/{fname}", "items": len(items)}


# ---------- 5.4 工程承接：工地日报 + 五节点验收 ----------

INSPECT_NODES = ["水电", "防水", "泥木", "油漆", "竣工"]


@router.post("/projects/{pid}/reports")
def create_report(pid: int, body: ReportIn):
    """工地日报：项目经理按施工阶段写日报"""
    _perm(body.user, "site_report")
    with get_conn() as conn:
        if not conn.execute("SELECT id FROM projects WHERE id=?", (pid,)).fetchone():
            raise HTTPException(404, f"项目 {pid} 不存在")
        cur = conn.execute(
            "INSERT INTO site_reports(project_id, stage, content, reporter) "
            "VALUES(?,?,?,?)", (pid, body.stage, body.content, body.user))
        rid = cur.lastrowid
        audit(body.user, "工地日报", f"site_reports#{rid}", after=f"stage={body.stage}")
    return {"id": rid, "project_id": pid, "stage": body.stage, "reporter": body.user}


@router.get("/projects/{pid}/reports")
def list_reports(pid: int):
    """项目日报列表（按时间倒序）"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, stage, content, reporter, created_at FROM site_reports "
            "WHERE project_id=? ORDER BY id DESC", (pid,)).fetchall()
    return {"total": len(rows), "items": [dict(r) for r in rows]}


@router.post("/projects/{pid}/inspections/{node}")
def submit_inspection(pid: int, node: str, body: InspectionIn):
    """节点验收：五节点（水电/防水/泥木/油漆/竣工），同节点只留一条"""
    _perm(body.user, "inspection")
    if node not in INSPECT_NODES:
        raise HTTPException(400, f"验收节点须为 {'/'.join(INSPECT_NODES)}（收到 {node}）")
    if body.result not in ("合格", "整改"):
        raise HTTPException(400, "result 须为 合格/整改")
    with get_conn() as conn:
        if not conn.execute("SELECT id FROM projects WHERE id=?", (pid,)).fetchone():
            raise HTTPException(404, f"项目 {pid} 不存在")
        old = conn.execute("SELECT result FROM inspections WHERE project_id=? AND node=?",
                           (pid, node)).fetchone()
        conn.execute(
            "INSERT INTO inspections(project_id, node, result, checked_by, checked_at, note) "
            "VALUES(?,?,?,?,datetime('now','localtime'),?) "
            "ON CONFLICT(project_id, node) DO UPDATE SET result=excluded.result, "
            "checked_by=excluded.checked_by, checked_at=excluded.checked_at, note=excluded.note",
            (pid, node, body.result, body.user, body.note))
        audit(body.user, "节点验收", f"inspections#{pid}:{node}",
              before=old["result"] if old else "待验收", after=body.result)
    return {"project_id": pid, "node": node, "result": body.result, "checked_by": body.user}


@router.get("/projects/{pid}/inspections")
def list_inspections(pid: int):
    """项目五节点验收看板"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT node, result, checked_by, checked_at, note FROM inspections "
            "WHERE project_id=?", (pid,)).fetchall()
    return {"project_id": pid, "nodes": [dict(r) for r in rows]}


# ---------- 5.5 项目详情汇总（工作台承接面板数据源） ----------

@router.get("/projects/{pid}/detail")
def project_detail(pid: int):
    """项目承接全景：客户+状态+方案+报价+付款计划+验收+日报"""
    with get_conn() as conn:
        p = conn.execute(
            "SELECT p.id, p.designer, p.summary, p.status, p.dispatched_at, "
            "       c.name, c.phone, c.estate, c.area, c.budget_range "
            "FROM projects p LEFT JOIN customers c ON c.id=p.customer_id "
            "WHERE p.id=?", (pid,)).fetchone()
        if not p:
            raise HTTPException(404, f"项目 {pid} 不存在")
        plans = conn.execute(
            "SELECT id, version, style, points, status, created_at FROM design_plans "
            "WHERE project_id=? ORDER BY version DESC", (pid,)).fetchall()
        quote = conn.execute(
            "SELECT id, total, discount, status, created_by FROM quotes "
            "WHERE project_id=? ORDER BY id DESC LIMIT 1", (pid,)).fetchone()
        inspections = conn.execute(
            "SELECT node, result, checked_by, checked_at FROM inspections "
            "WHERE project_id=?", (pid,)).fetchall()
        n_reports = conn.execute(
            "SELECT COUNT(*) AS n FROM site_reports WHERE project_id=?", (pid,)).fetchone()["n"]
    data = dict(p)
    data["plans"] = [dict(r) for r in plans]
    data["inspections"] = {r["node"]: r["result"] for r in inspections}
    data["report_count"] = n_reports
    if quote:
        q = dict(quote)
        cfg = config_loader.load_profile(_PROFILE)
        stages = cfg["rules"]["payment_stages"]
        q["payment_plan"] = [
            {**s, "amount": round(q["total"] * s["ratio"], 2)}
            for s in stages]
        q["payment_progress"] = _payment_progress(conn, q["id"], stages, q["total"])
        data["quote"] = q
    else:
        data["quote"] = None
    return data


@router.post("/dispatch")
def dispatch(body: DispatchIn):
    _perm(body.user, "dispatch")
    r = DispatchAgent().dispatch(user=body.user, customer_id=body.customer_id,
                                 designer=body.designer)
    _dec.capture_result(r, "dispatch", body.customer_id, body.user)
    return r


@router.post("/projects/{pid}/status")
def project_transition(pid: int, body: ProjectStatusIn):
    """项目状态迁移：量房→设计→报价→签约→开工→水电→…→验收交付
    校验 workflow.yaml transitions（内核锁定：locked_nodes 不可跳过）；
    合法迁移落库 + 审计 + 决策捕获。"""
    _perm(body.user, "transition")
    cfg = config_loader.load_profile(_PROFILE)
    transitions = cfg["workflow"]["transitions"]
    with get_conn() as conn:
        row = conn.execute("SELECT status FROM projects WHERE id=?", (pid,)).fetchone()
        if not row:
            raise HTTPException(404, f"项目 {pid} 不存在")
        cur = row["status"]
        allowed = {t["to"] for t in transitions if t["from"] == cur}
        if body.to != cur and body.to not in allowed:
            raise HTTPException(400, f"项目状态迁移不合法: {cur} -> {body.to}"
                                     f"（允许: {sorted(allowed) or '无'}）")
        # 6.4 状态闸门：迁移到 gates 配置的节点时校验前置条件（收款达标等）
        gates = (cfg.get("rules") or {}).get("gates") or {}
        gate = gates.get(body.to)
        if gate:
            q = conn.execute(
                "SELECT id, status FROM quotes WHERE project_id=? ORDER BY id DESC LIMIT 1",
                (pid,)).fetchone()
            if gate.get("quote_status") and (not q or q["status"] == "已否决"):
                raise HTTPException(400, f"开工闸门：项目无有效报价（需 {gate['quote_status']}）")
            if gate.get("payment_stage"):
                if not q:
                    raise HTTPException(400, f"开工闸门：项目无报价，无法校验收款")
                total = conn.execute("SELECT total FROM quotes WHERE id=?",
                                     (q["id"],)).fetchone()["total"]
                stages = (cfg.get("rules") or {}).get("payment_stages") or []
                st = next((x for x in stages if x["stage"] == gate["payment_stage"]), None)
                if st:
                    due = round(total * st["ratio"], 2)
                    got = round(conn.execute(
                        "SELECT COALESCE(SUM(amount),0) AS s FROM payments "
                        "WHERE quote_id=?", (q["id"],)).fetchone()["s"], 2)
                    need = round(due * gate.get("paid_ratio", 1.0), 2)
                    if got < need - 1e-6:
                        raise HTTPException(
                            400, f"开工闸门：{st['stage']} 阶段需收足 ¥{need:,.2f}"
                                 f"（应缴 ¥{due:,.2f}×{gate.get('paid_ratio', 1.0)}），当前已收 ¥{got:,.2f}，"
                                 f"还差 ¥{max(need - got, 0):,.2f}")
        conn.execute("UPDATE projects SET status=? WHERE id=?", (body.to, pid))
        audit(body.user, "项目状态迁移", f"projects#{pid}", before=cur, after=body.to)
    _dec.capture_result({"project_id": pid, "from": cur, "to": body.to},
                        "project_transition", pid, body.user)
    return {"id": pid, "from": cur, "to": body.to}


@router.get("/projects")
def list_projects(status: str = "", limit: int = 50):
    with get_conn() as conn:
        sql = "SELECT p.*, c.name, c.phone, c.estate FROM projects p LEFT JOIN customers c ON c.id=p.customer_id WHERE 1=1"
        args = []
        if status:
            sql += " AND p.status=?"
            args.append(status)
        sql += " ORDER BY p.id DESC LIMIT ?"
        args.append(limit)
        rows = conn.execute(sql, args).fetchall()
    return {"total": len(rows), "items": [dict(r) for r in rows]}
