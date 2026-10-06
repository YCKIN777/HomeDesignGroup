# -*- coding: utf-8 -*-
import sys
from pathlib import Path

# 获取当前api_server.py所在目录
current_dir = Path(__file__).parent
# 添加到python搜索路径
sys.path.insert(0, str(current_dir))

"""
api_server.py — FastAPI 骨架（Step 1.7）
路由（阶段2 再扩业务接口）：
  GET  /health  健康检查（db/config/llm）
  POST /login   登录（校验 users 表 pbkdf2）
  GET  /        登录页
启动：uvicorn api_server:app --port 8000（或 start.ps1）
"""
import hashlib
import os
import sqlite3
import threading
import traceback
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

ROOT = r"H:\AgentProjects\HomeDesignGroup"
DB_PATH = os.path.join(ROOT, "db", "壹城精工.db")
COMPANY = "壹城精工"

from kernel import config_loader  # noqa: E402
from llm import get_llm  # noqa: E402
from memory_manager import MemoryManager  # noqa: E402
from agents.sop_agent import SopAgent  # noqa: E402
from routers import (leads, inbox, dispatch, config, todos, kb,  # noqa: E402
                     memory_api, webhook, stats, sedimentation, decisions, core_api, agent_api,
                     team_api)

app = FastAPI(title="家装AI智能体平台", version="0.2.1-Sched")
mm = MemoryManager()
# ============ WebChat 聊天界面挂载【新增】=========
from fastapi.staticfiles import StaticFiles
from extensions.webchat.router import router as webchat_router
# 挂载WebChat接口路由
app.include_router(webchat_router, prefix="/ext-webchat/api", tags=["扩展WebChat"])
# 挂载前端静态页面目录
static_dir = current_dir / "extensions" / "webchat" / "static"
print("【WebChat静态目录】", static_dir)
app.mount("/ext-webchat", StaticFiles(directory=str(static_dir), html=True), name="webchat_static")

# 兜底路由
from fastapi.responses import FileResponse
@app.get("/ext-webchat/")
async def webchat_index():
    return FileResponse(static_dir / "index.html")


# ---------- M7 后台调度器：每 60 秒扫一次 SOP 到期 ----------
_sop_stop = threading.Event()

def _sop_loop():
    while not _sop_stop.wait(60):      # 每 60 秒一次
        try:
            SopAgent().check_due()
        except Exception:
            # 打印异常堆栈，方便调试，不再静默吞错
            traceback.print_exc()

@app.on_event("startup")
def _start_sop_scheduler():
    threading.Thread(target=_sop_loop, daemon=True).start()

@app.post("/api/sop/run")
def sop_run():
    """手动触发一次 SOP 扫描（调试/演示用）"""
    todos = SopAgent().check_due()
    return {"checked": True, "open_todos": len(todos)}

# ---------- Step 4.8：MCP 出口（JSON-RPC 2.0 over HTTP） ----------
@app.post("/mcp")
def mcp_endpoint(body: dict, request: Request):
    """MCP 出口：initialize/tools/list/tools/call（工具=平台现有能力，权限与角色矩阵一致）"""
    from mcp_server import handle_mcp
    header_user = request.headers.get("X-Agent-User", "")
    return handle_mcp(body, header_user=header_user)


for r in (leads.router, inbox.router, dispatch.router, config.router,
          todos.router, kb.router, memory_api.router, webhook.router,
          stats.router, sedimentation.router, decisions.router, core_api.router,
                       agent_api.router, team_api.router):
    app.include_router(r)


LOGIN_PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>家装AI智能体平台·登录</title>
<style>
body{font-family:'Microsoft YaHei',sans-serif;background:#F5F7FA;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}
.card{background:#fff;border-radius:12px;padding:40px 48px;box-shadow:0 4px 24px rgba(31,58,77,.12);width:360px}
h1{font-size:20px;color:#1F3A4D;margin:0 0 6px}
p.sub{color:#8A94A6;font-size:13px;margin:0 0 24px}
label{display:block;font-size:13px;color:#5B6B7F;margin:12px 0 6px}
input{width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid #D7DEE7;border-radius:8px;font-size:14px}
button{margin-top:20px;width:100%;padding:11px;background:#1F3A4D;color:#fff;border:none;border-radius:8px;font-size:15px;cursor:pointer}
#msg{margin-top:12px;font-size:13px;min-height:18px}
.ok{color:#2E7D32}.err{color:#C62828}
</style></head><body>
<div class="card">
  <h1>家装 AI 智能体平台</h1>
  <p class="sub">获客 → 客服 → 派单 · 壹城精工</p>
  <label>账号</label><input id="account" value="admin">
  <label>密码</label><input id="password" type="password" value="12345678">
  <button onclick="login()">登 录</button>
  <div id="msg"></div>
</div>
<script>
async function login(){
  const msg=document.getElementById('msg');
  try{
    const r=await fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({account:document.getElementById('account').value,password:document.getElementById('password').value})});
    const d=await r.json();
    if(d.ok){
      localStorage.setItem('platform_user', d.account);
      localStorage.setItem('platform_role', d.role);
      window.location.href='/app';   // 登录成功 → 跳转工作台
    }else{
      msg.className='err'; msg.textContent=d.error||'登录失败';
    }
  }catch(e){msg.className='err';msg.textContent='无法连接服务';}
}
</script></body></html>"""
DASHBOARD_PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>家装AI智能体平台·工作台</title>
<style>
:root{
  --bg:#f5f5f7; --card:#ffffff; --line:#e0e0e0; --divider:#f0f0f0;
  --ink:#1d1d1f; --ink2:#333333; --ink3:#7a7a7a;
  --brand:#0066cc; --brand-focus:#0071e3; --brand-soft:#E9F2FC;
  --ok:#34c759; --warn:#ff9500; --bad:#ff3b30;
  --r-pill:9999px; --r-lg:18px; --r-md:11px; --r-sm:8px;
  --font:-apple-system,"SF Pro Text","SF Pro Display",system-ui,"PingFang SC","Microsoft YaHei","Noto Sans SC","Helvetica Neue",Arial,sans-serif;
}
*{box-sizing:border-box}
body{font-family:var(--font);background:var(--bg);margin:0;color:var(--ink);font-size:14px;line-height:1.47}
.app{display:flex;min-height:100vh}
.side{width:240px;background:var(--card);border-right:1px solid var(--divider);display:flex;flex-direction:column;flex-shrink:0;position:sticky;top:0;height:100vh;overflow:auto}
.brand{display:flex;align-items:center;gap:10px;font-weight:600;font-size:16px;letter-spacing:-.3px;padding:18px 20px 14px}
.brand .logo{width:34px;height:34px;border-radius:8px;background:var(--brand);color:#fff;display:flex;align-items:center;justify-content:center;font-size:17px;font-weight:600;flex-shrink:0}
.brand small{display:block;font-size:11px;color:var(--ink3);font-weight:400;letter-spacing:0}
.nav{flex:1;padding:6px 10px}
.nav .group{font-size:12px;color:var(--ink3);padding:14px 12px 6px;letter-spacing:.2px}
.nav a{display:flex;align-items:center;gap:8px;padding:9px 12px;border-radius:var(--r-md);font-size:13.5px;color:var(--ink2);cursor:pointer;margin-bottom:2px;transition:.15s;text-decoration:none}
.nav a:hover{background:var(--bg);color:var(--ink)}
.nav a.on{background:rgba(0,102,204,.09);color:var(--brand);font-weight:600}
.side-foot{padding:14px 20px;font-size:11px;color:var(--ink3);border-top:1px solid var(--divider);line-height:1.6}
.main{flex:1;min-width:0;display:flex;flex-direction:column}
.top{height:56px;background:var(--card);border-bottom:1px solid var(--divider);display:flex;align-items:center;gap:14px;padding:0 24px;position:sticky;top:0;z-index:10}
.top-search{display:flex;align-items:center;gap:8px;background:var(--bg);border:1px solid rgba(0,0,0,.08);border-radius:var(--r-pill);padding:8px 16px;color:var(--ink3);font-size:13px;cursor:text;min-width:220px}
.top-search svg{flex-shrink:0}
.top-right{margin-left:auto;display:flex;align-items:center;gap:10px}
.icon-btn{position:relative;width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:var(--bg);color:var(--ink);cursor:pointer;transition:.15s}
.icon-btn:hover{background:#ebebee}
.icon-btn .dot{position:absolute;top:2px;right:2px;min-width:16px;height:16px;border-radius:var(--r-pill);background:var(--bad);color:#fff;font-size:10px;font-weight:600;display:flex;align-items:center;justify-content:center;padding:0 4px}
.user{display:flex;align-items:center;gap:10px;padding:4px 6px}
.user .av{width:32px;height:32px;border-radius:50%;background:var(--brand);color:#fff;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:600;flex-shrink:0}
.user .who{font-size:13px;font-weight:600;letter-spacing:-.2px;display:block}
.user .sub{font-size:11px;color:var(--ink3);display:block;font-weight:400}
.quit{font-size:12px;color:var(--ink3);cursor:pointer;padding:6px 10px;border-radius:var(--r-sm);transition:.15s}
.quit:hover{color:var(--bad);background:var(--bad-soft)}
main{max-width:1280px;margin:20px auto;padding:0 24px;width:100%}
section{background:var(--card);border:1px solid var(--line);border-radius:var(--r-lg);padding:24px;margin-bottom:16px}
section h2{font-size:20px;font-weight:600;letter-spacing:-.3px;margin:0 0 4px;color:var(--ink)}
section .panel-sub{font-size:13px;color:var(--ink3);margin:0 0 16px;letter-spacing:-.1px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{border-bottom:1px solid var(--divider);padding:9px 10px;text-align:left;vertical-align:top}
th{background:#fafafc;color:var(--ink3);font-weight:600;font-size:12px;letter-spacing:-.15px}
tbody tr:hover td{background:#fafafc}
.btn{height:36px;padding:0 20px;border-radius:var(--r-pill);font-size:14px;font-weight:600;display:inline-flex;align-items:center;gap:6px;transition:.15s;cursor:pointer;border:none;background:var(--ink);color:#fff}
.btn:hover{background:#000000}
.btn.green{background:var(--brand);color:#fff}
.btn.green:hover{background:var(--brand-focus)}
.btn.orange{background:var(--warn);color:#fff}
.btn.orange:hover{background:#e08900}
.btn.ghost{background:var(--card);color:var(--brand);border:1px solid var(--brand)}
.btn.ghost:hover{background:rgba(0,102,204,.05)}
.btn.sm{height:30px;padding:0 14px;font-size:13px}
.btn:active{transform:scale(.95)}
button{font-family:var(--font);cursor:pointer;border:none;background:none;font-size:13px}
:focus-visible{outline:2px solid var(--brand-focus);outline-offset:2px}
input,select{padding:9px 14px;border:1px solid rgba(0,0,0,.12);border-radius:var(--r-pill);font-size:13px;box-sizing:border-box;font-family:var(--font);background:var(--card);color:var(--ink)}
input:focus,select:focus{border-color:var(--brand);box-shadow:0 0 0 3px rgba(0,102,204,.12);outline:none}
.row{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px;align-items:center}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--r-lg);padding:20px 22px;font-size:13px;color:var(--ink3);letter-spacing:-.2px}
.card b{font-size:28px;font-weight:600;letter-spacing:-.5px;line-height:1.15;display:block;color:var(--ink);margin-bottom:6px}
.msg{font-size:12px;color:var(--ink3);padding:6px 0;line-height:1.7}
a{color:var(--brand)}
@media(max-width:833px){
  .side{width:64px}
  .brand div>div:last-child,.brand small,.side-foot,.nav .group{display:none}
  .nav a{justify-content:center;padding:9px 0;font-size:0}
  .nav a:after{content:"";width:8px;height:8px;border-radius:50%;background:currentColor;opacity:.35}
  .nav a.on:after{opacity:1}
  main{padding:0 14px;margin:14px auto}
  section{padding:18px}
  .top{padding:0 14px}
  .top-search{min-width:0;width:150px}
}
/* === P0 客户旅程轨道 === */
.jr-track{display:flex;align-items:flex-start;gap:0;flex:1;min-width:520px;}
.jr-node{display:flex;flex-direction:column;align-items:center;gap:4px;width:72px;flex:none;}
.jr-dot{width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:600;background:#eef1f6;color:#98a2b3;border:2px solid #e4e7ec;}
.jr-label{font-size:11px;color:#667085;white-space:nowrap;}
.jr-line{flex:1;height:2px;background:#e4e7ec;margin-top:12px;min-width:16px;}
.jr-node.done .jr-dot{background:#3b82f6;color:#fff;border-color:#3b82f6;}
.jr-node.done .jr-label{color:#3b82f6;font-weight:600;}
.jr-node.active .jr-dot{background:#fff;color:#3b82f6;border-color:#3b82f6;box-shadow:0 0 0 4px rgba(59,130,246,.15);}
.jr-node.active .jr-label{color:#1d4ed8;font-weight:700;}
.jr-node.lost .jr-dot{background:#fef2f2;color:#dc2626;border-color:#fecaca;}
.jr-node.lost .jr-label{color:#dc2626;}
</style></head><body>
<div class="app">
  <aside class="side">
    <div class="brand"><div class="logo">壹</div><div>壹城精工<small>家装 AI 平台</small></div></div>
    <nav class="nav">
      <div class="group">概览</div>
      <a class="on" data-tab="s-stats" onclick="showTab('s-stats')">数据看板</a>
      <div class="group">获客</div>
      <a data-tab="s-leads" onclick="showTab('s-leads')">客户线索</a>
      <a data-tab="s-inbox" onclick="showTab('s-inbox')">收件箱</a>
      <a data-tab="s-todos" onclick="showTab('s-todos')">SOP 待办</a>
      <a data-tab="s-ai" onclick="showTab('s-ai')">AI 顾问</a>
      <div class="group">项目</div>
      <a data-tab="s-projects" onclick="showTab('s-projects')">项目列表</a>
      <a data-tab="s-carrier" onclick="showTab('s-carrier')">承接工作区</a>
      <div class="group">支撑</div>
      <a data-tab="s-kb" onclick="showTab('s-kb')">谈单知识库</a>
      <a data-tab="s-contract" onclick="showTab('s-contract')">契约线·监理</a>
      <div class="group">组织</div>
      <a data-tab="s-team" onclick="showTab('s-team')">九部门视图</a>
    </nav>
    <div class="side-foot">通用内核 v1.18<br>壹城精工-定制配置</div>
  </aside>
  <div class="main">
    <header class="top">
      <div class="top-search" onclick="jumpSearch()">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>
        <span>搜索客户 / 项目 / 报价...</span>
      </div>
      <div class="top-right">
        <div class="icon-btn" onclick="showTab('s-inbox')" title="收件箱待审">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg>
          <span class="dot" id="bell-n">3</span>
        </div>
        <div class="user">
          <div class="av" id="av-c">苏</div>
          <div><span class="who" id="who"></span><span class="sub">壹城精工</span></div>
        </div>
        <span class="quit" onclick="logout()">退出</span>
      </div>
    </header>
    <main>
  <section id="s-stats"><h2>数据看板</h2><p class="panel-sub">业务指标实时对账（阶段 4）· 壹城精工</p>
    <div class="cards" id="t-stats"></div>
  </section>
  <section id="s-leads" style="display:none"><h2>客户线索</h2><p class="panel-sub">获客归集 · 建档打标 · 评分派单</p>
    <div class="row">
      <input id="n_phone" placeholder="手机号*"><input id="n_name" placeholder="姓名">
      <input id="n_estate" placeholder="楼盘"><input id="n_budget" placeholder="预算区间">
      <input id="n_channel" placeholder="渠道">
      <button class="btn green" onclick="addLead()">新建线索</button>
      <button class="btn ghost" onclick="document.getElementById('csv').click()">批量导入CSV</button>
      <input type="file" id="csv" accept=".csv,.txt" style="display:none" onchange="importCsv(this)">
      <input id="q" placeholder="搜索楼盘/姓名/标签" style="margin-left:auto">
      <button class="btn ghost" onclick="loadLeads()">查询</button>
      <select id="dp_designer" style="flex:0.9" title="派单设计师（默认待分配，按设计角色动态加载）">
        <option value="">派单→待分配</option>
      </select>
    </div>
    <table><thead><tr><th>ID</th><th>姓名</th><th>手机</th><th>楼盘</th><th>预算</th><th>状态</th><th>评分</th><th>操作</th></tr></thead><tbody id="t-leads"></tbody></table>
    <div class="msg" id="m-leads"></div>
  </section>
  <section id="s-inbox" style="display:none"><h2>收件箱（AI 起草 · 人审后发）</h2>
    <table><thead><tr><th>ID</th><th>客户</th><th>内容</th><th>时间</th><th>操作</th></tr></thead><tbody id="t-inbox"></tbody></table>
    <div class="msg" id="m-inbox"></div>
  </section>
  <section id="s-todos" style="display:none"><h2>SOP 待办</h2>
    <table><thead><tr><th>ID</th><th>客户</th><th>事项</th><th>操作</th></tr></thead><tbody id="t-todos"></tbody></table>
    <div class="msg" id="m-todos"></div>
  </section>
  <section id="s-projects" style="display:none"><h2>项目（派单结果）</h2>
    <table><thead><tr><th>ID</th><th>客户</th><th>状态</th><th>设计师</th><th>创建时间</th></tr></thead><tbody id="t-projects"></tbody></table>
    <div class="msg" id="m-projects"></div>
  </section>
  <section id="s-carrier" style="display:none"><h2>项目承接 · 设计 / 报价 / 工程（阶段5）</h2>
    <div class="row">
      <input id="cp_pid" placeholder="项目 ID，如 20" style="flex:1">
      <button class="btn green" onclick="loadProjectDetail()">加载承接详情</button>
    </div>
    <div id="t-carrier" class="msg" style="min-height:30px;line-height:1.7"></div>
  </section>
  <section id="s-kb" style="display:none"><h2>谈单知识库</h2>
    <div class="row"><input id="kbq" placeholder="关键词，如：隐蔽工程 / 全包">
    <button class="btn" onclick="searchKb()">检索</button></div>
    <div id="t-kb" class="msg"></div>
  </section>
  <section id="s-contract" style="display:none"><h2>契约线 · 业主监理（工艺问答 / 报价单 / 工地日报）</h2>
    <div style="border:1px solid #e0e0e0;border-radius:11px;padding:14px 18px;margin-bottom:14px;background:#fafafc">
      <b style="font-size:13px;color:#248a3d">① 工艺问答</b>
      <div class="row" style="margin-top:8px">
        <input id="qa_q" placeholder="问题，如：轻钢龙骨吊顶怎么做" style="flex:2">
        <input id="qa_cat" placeholder="分类（可留空）" style="flex:1">
        <button class="btn green" onclick="runQa()">查工艺</button>
      </div>
      <div id="t-qa" class="msg" style="min-height:20px"></div>
      <div class="msg" id="m-qa"></div>
    </div>
    <div style="border:1px solid #e0e0e0;border-radius:11px;padding:14px 18px;margin-bottom:14px;background:#fafafc">
      <b style="font-size:13px;color:#248a3d">② 报价单（草稿，不自动发）</b>
      <div class="row" style="margin-top:8px">
        <select id="q_owner" style="flex:1.2"></select>
        <input id="q_req" placeholder="需求，如：全屋硬装" style="flex:1.2">
        <input id="q_cat" placeholder="材料分类（可留空）" style="flex:1">
        <button class="btn green" onclick="runQuote()">生成报价</button>
      </div>
      <div class="msg" id="q_head"></div>
      <table id="t-quote"></table>
      <div class="msg" id="m-quote"></div>
    </div>
    <div style="border:1px solid #e0e0e0;border-radius:11px;padding:14px 18px;margin-bottom:14px;background:#fafafc">
      <b style="font-size:13px;color:#248a3d">③ 工地日报（OCR + 模板 → 人工发送）</b>
      <div class="row" style="margin-top:8px">
        <input id="rp_project" placeholder="项目，如：保利和光尘樾-189" style="flex:1.2">
        <input id="rp_note" placeholder="监理备注，如：木工吊顶龙骨完成" style="flex:1.8">
        <button class="btn green" onclick="runReport()">生成日报</button>
      </div>
      <div id="t-report" class="msg" style="min-height:20px;line-height:1.7"></div>
    </div>
  </section>
  <section id="s-team" style="display:none"><h2>九部门视图 · 编队v3（总经办 / 材料 / 软装 / 售后）</h2>
    <div style="border:1px solid #e0e0e0;border-radius:11px;padding:14px 18px;margin-bottom:14px;background:#fafafc">
      <b style="font-size:13px;color:#1d1d1f">总经办（审批 / 看板 / 审计 / 协调）</b>
      <div class="row" style="margin-top:8px">
        <button class="btn green" onclick="loadCeo('approvals')">审批汇总</button>
        <button class="btn green" onclick="loadCeo('dashboard')">数据看板</button>
        <button class="btn green" onclick="loadCeo('audit')">审计追溯</button>
        <input id="ceo_note" placeholder="跨部门协调备注" style="flex:1.5">
        <button class="btn" onclick="ceoCoord()">留痕</button>
      </div>
      <div id="t-ceo" class="msg" style="min-height:20px;line-height:1.7"></div>
    </div>
    <div style="border:1px solid #e0e0e0;border-radius:11px;padding:14px 18px;margin-bottom:14px;background:#fafafc">
      <b style="font-size:13px;color:#1d1d1f">材料 · 主材清单 / 材料库</b>
      <div class="row" style="margin-top:8px">
        <input id="mat_qid" placeholder="报价ID，如 20" style="flex:1">
        <button class="btn green" onclick="loadMat()">生成主材清单</button>
        <input id="mat_kw" placeholder="材料库检索词（可留空）" style="flex:1.5">
        <button class="btn" onclick="searchMat()">检索材料库</button>
      </div>
      <div id="t-mat" class="msg" style="min-height:20px;line-height:1.7"></div>
    </div>
    <div style="border:1px solid #e0e0e0;border-radius:11px;padding:14px 18px;margin-bottom:14px;background:#fafafc">
      <b style="font-size:13px;color:#1d1d1f">软装 · 家具 / 灯具 / 窗帘</b>
      <div class="row" style="margin-top:8px">
        <input id="soft_pid" placeholder="项目ID" style="flex:1">
        <button class="btn green" onclick="loadSoft()">软装清单</button>
      </div>
      <div class="row" style="margin-top:6px">
        <select id="soft_cat" style="flex:0.9"><option>家具</option><option>灯具</option><option>窗帘</option><option>布艺</option><option>装饰</option><option>其他</option></select>
        <input id="soft_name" placeholder="品名，如：意式极简三人沙发" style="flex:1.6">
        <input id="soft_spec" placeholder="规格" style="flex:1">
        <input id="soft_qty" placeholder="数量" value="1" style="flex:0.6">
        <input id="soft_price" placeholder="单价" style="flex:0.8">
        <button class="btn green" onclick="softAdd()">录入</button>
      </div>
      <div id="t-soft" class="msg" style="min-height:20px;line-height:1.7"></div>
    </div>
    <div style="border:1px solid #e0e0e0;border-radius:11px;padding:14px 18px;background:#fafafc">
      <b style="font-size:13px;color:#1d1d1f">售后 · 质保 / 工单 / 回访</b>
      <div class="row" style="margin-top:8px">
        <input id="as_pid" placeholder="项目ID" style="flex:1">
        <button class="btn green" onclick="loadAs()">售后列表</button>
        <button class="btn" onclick="asWarranty()">登记质保(2年/防水10年)</button>
        <button class="btn" onclick="asDue()">回访SOP提醒</button>
      </div>
      <div class="row" style="margin-top:6px">
        <input id="as_title" placeholder="工单标题，如：厨房水槽下水慢" style="flex:1.8">
        <input id="as_content" placeholder="工单内容（可留空）" style="flex:1.8">
        <button class="btn green" onclick="asTicket()">建工单</button>
      </div>
      <div id="t-as" class="msg" style="min-height:20px;line-height:1.7"></div>
    </div>
  </section>
  <section id="s-ai" style="display:none"><h2>AI 顾问 · 获客对话</h2><p class="panel-sub">流式对话 · 自动建档（楼盘/面积/户型/风格/预算）· 信息齐全按壹城规则报价</p>
    <div class="card" style="display:flex;flex-direction:column;height:540px;padding:0;overflow:hidden">
      <div id="ai-msgs" style="flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px;background:#f5f5f7"></div>
      <div style="display:flex;gap:8px;padding:12px;border-top:1px solid var(--line)">
        <input id="ai-input" class="input" style="flex:1" placeholder="例如：想装 120 平三房，奶油风，预算 20 万左右">
        <button class="btn green" onclick="aiSend()">发送</button>
        <button class="btn" onclick="aiClear()">清空</button>
      </div>
    </div>
  </section>
    </main>
  </div>
</div>
<script>
/* ===== AI 顾问（获客对话智能体融合 S4）===== */
var aiCid = localStorage.getItem('ai_cid') || '';
function aiBubble(type, text){
  var box = document.getElementById('ai-msgs');
  var wrap = document.createElement('div');
  wrap.style.cssText = 'display:flex;margin-bottom:2px;' + (type==='user'?'justify-content:flex-end':'justify-content:flex-start');
  var b = document.createElement('div');
  b.style.cssText = 'max-width:78%;padding:10px 14px;border-radius:16px;white-space:pre-wrap;line-height:1.55;font-size:14px;background:' + (type==='user'?'var(--brand);color:#fff':'#fff;color:var(--ink);border:1px solid var(--line)');
  b.textContent = text;
  wrap.appendChild(b); box.appendChild(wrap); box.scrollTop = box.scrollHeight;
  return b;
}
function aiEnsureCid(){ if(!aiCid){ aiCid = 'cus_' + Date.now(); localStorage.setItem('ai_cid', aiCid); } }
async function aiSend(){
  var input = document.getElementById('ai-input');
  var msg = input.value.trim();
  if(!msg) return;
  aiEnsureCid();
  aiBubble('user', msg); input.value = '';
  var b = aiBubble('ai', ''); input.disabled = true;
  try{
    var resp = await fetch('/api/chat_stream', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({msg:msg, cid:aiCid})});
    var reader = resp.body.getReader(); var dec = new TextDecoder(); var buf = ''; var full = '';
    while(true){
      var r = await reader.read(); if(r.done) break;
      buf += dec.decode(r.value, {stream:true});
      var lines = buf.split('\\n\\n'); buf = lines.pop();
      for(var i=0;i<lines.length;i++){
        var ln = lines[i].trim(); if(!ln) continue;
        if(ln.indexOf('data: ') === 0) ln = ln.slice(6);
        try{ var o = JSON.parse(ln); if(o.delta){ full += o.delta; b.textContent = full; } }catch(e){}
      }
    }
  }catch(e){ b.textContent = '连接失败: ' + e.message; }
  input.disabled = false; input.focus();
}
function aiClear(){ aiCid=''; localStorage.removeItem('ai_cid'); document.getElementById('ai-msgs').innerHTML=''; }
function showTab(id){
  document.querySelectorAll('main>section').forEach(function(sec){sec.style.display=(sec.id===id)?'':'none';});
  document.querySelectorAll('.nav a').forEach(function(a){a.classList.toggle('on',a.dataset.tab===id);});
}
function jumpSearch(){showTab('s-leads');var q=document.getElementById('q');if(q)q.focus();}
async function loadProjectDetail(){
  const pid=document.getElementById('cp_pid').value.trim();
  const el=document.getElementById('t-carrier');
  if(!pid){el.textContent='请输入项目 ID';return;}
  try{
    const d=await api('/api/projects/'+pid+'/detail');
    let h='<div style="background:#f5f5f7;border-radius:8px;padding:10px;margin-bottom:10px">'
      +'<b>项目 #'+esc(d.id)+'</b> · '+esc(d.name||'-')+' · '+esc(d.estate||'-')
      +' · '+esc(d.area||'-')+'㎡ · 预算 '+esc(d.budget_range||'-')
      +' · 状态 <b style="color:#248a3d">'+esc(d.status)+'</b> · 设计师 '+esc(d.designer||'-')
      +' · 日报 '+d.report_count+' 条</div>';
    h+='<b style="font-size:13px">设计方案</b><table><thead><tr><th>版本</th><th>风格</th><th>要点</th><th>状态</th></tr></thead><tbody>';
    h+=(d.plans||[]).map(x=>'<tr><td>v'+x.version+'</td><td>'+esc(x.style)+'</td><td>'+esc(x.points)+'</td><td>'+esc(x.status)+'</td></tr>').join('')||'<tr><td colspan="4">暂无方案</td></tr>';
    h+='</tbody></table>';
    if(d.quote){
      const q=d.quote;
      h+='<div style="margin-top:10px"><b style="font-size:13px">报价</b> '
        +'总额 <b id="q_total_'+q.id+'" style="color:#d97706">¥'+q.total.toLocaleString()+'</b>'
        +' · 折扣 '+(q.discount*100).toFixed(1)+'折 · 状态 <b>'+esc(q.status)+'</b></div>';
      try{
        const it=await api('/api/quotes/'+q.id+'/items');
        h+='<div style="margin-top:6px;font-size:12px;color:#7a7a7a">'+it.items_count+' 项明细'
          +(it.est_items?' · <span style="color:#d97706">'+it.est_items+' 项估算待复核</span>':'')+'</div>';
        const secs=Object.keys(it.groups||{});
        if(secs.length){
          h+='<div style="max-height:340px;overflow:auto;border:1px solid #e0e0e0;border-radius:8px;margin-top:6px">';
          secs.forEach(sec=>{
            const rows=it.groups[sec];
            h+='<div style="background:#f5f5f7;font-weight:700;font-size:12px;padding:5px 8px;border-bottom:1px solid #e0e0e0;border-top:1px solid #e0e0e0">'+esc(sec)+' · '+rows.length+' 项</div>';
            h+='<table style="margin:0"><thead><tr><th>项目</th><th>工艺</th><th>单位</th><th>单价</th><th>工程量</th><th>金额</th><th></th></tr></thead><tbody>';
            rows.forEach(x=>{
              h+='<tr><td>'+esc(x.item)+'</td>'
                +'<td style="max-width:180px;font-size:12px;color:#7a7a7a;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="'+esc(x.spec)+'">'+esc(x.spec)+'</td>'
                +'<td>'+esc(x.unit)+'</td><td>¥'+(x.unit_price||0).toLocaleString()+'</td>'
                +'<td><input id="qi_'+x.id+'" value="'+x.qty+'" style="width:64px;padding:2px 4px;border:1px solid #e0e0e0;border-radius:4px">'
                +(x.est?'<span style="color:#d97706;font-size:11px" title="估算值，量房后复核">估</span>':'')+'</td>'
                +'<td id="qa_'+x.id+'">¥'+(x.amount||0).toLocaleString()+'</td>'
                +'<td><button class="btn" style="padding:2px 8px;font-size:12px" onclick="fixItem('+q.id+','+x.id+',this)">存</button></td></tr>';
            });
            h+='</tbody></table>';
          });
          h+='</div>';
          h+='<div class="row" style="margin-top:8px">'
            +'<input id="re_area" placeholder="按面积重估（㎡）" style="flex:1">'
            +'<button class="btn green" onclick="reEstimate('+q.id+')">按面积重估（不覆盖已修正行）</button></div>';
        }
      }catch(e){ h+='<div style="color:#dc2626;font-size:12px;margin-top:6px">明细加载失败：'+esc(e.message)+'</div>'; }
      h+='<table style="margin-top:8px"><thead><tr><th>付款阶段</th><th>比例</th><th>应缴</th><th>已收</th><th>待收</th><th>登记收款</th></tr></thead><tbody>'
        +(q.payment_progress&&q.payment_progress.stages?q.payment_progress.stages.map(s=>
          '<tr><td>'+esc(s.stage)+'</td><td>'+(s.ratio*100)+'%</td><td>¥'+s.due.toLocaleString()+'</td>'
          +'<td style="color:'+(s.paid>=s.due?'#248a3d':'#d97706')+'">¥'+s.paid.toLocaleString()+'</td>'
          +'<td>¥'+s.remain.toLocaleString()+'</td>'
          +'<td><input id="pay_'+q.id+'_'+esc(s.stage)+'" placeholder="金额" style="width:72px;padding:2px 4px;border:1px solid #e0e0e0;border-radius:4px">'
          +'<button class="btn" style="padding:2px 8px;font-size:12px" data-stage="'+esc(s.stage)+'" onclick="payStage('+q.id+',this)">收</button></td></tr>').join('')
          :(q.payment_plan||[]).map(s=>'<tr><td>'+esc(s.stage)+'</td><td>'+(s.ratio*100)+'%</td><td>¥'+s.amount.toLocaleString()+'</td></tr>').join(''))
        +'</tbody></table>'
        +'<div style="margin-top:6px"><button class="btn green" onclick="exportQuote('+q.id+')">导出报价单（Excel）</button></div>';
    }else{
      h+='<div style="margin-top:10px"><b style="font-size:13px">报价</b> 暂无'
        +' <button class="btn green" onclick="genQuote('+pid+')">生成报价（预算范本 325 条明细）</button></div>';
    }
    h+='<div style="margin-top:10px"><b style="font-size:13px">工程验收（五节点）</b></div><table style="margin-top:6px"><thead><tr><th>节点</th><th>结果</th></tr></thead><tbody>';
    const nodes=d.inspections||{};
    ['水电','防水','泥木','油漆','竣工'].forEach(n=>{
      const v=nodes[n]||'待验收';
      h+='<tr><td>'+n+'</td><td style="color:'+(v==='合格'?'#248a3d':v==='整改'?'#dc2626':'#7a7a7a')+'">'+v+'</td></tr>';
    });
    h+='</tbody></table>';
    el.innerHTML=h;
  }catch(e){ el.textContent='加载失败：'+e.message; }
}
async function genQuote(pid){
  try{
    const r=await jpost('/api/projects/'+pid+'/quote',{requirements:'工作台生成'});
    alert('报价 #'+r.id+' 已生成：¥'+r.total.toLocaleString()+'，'+r.items+' 项明细（'+r.est_items+' 项估算待复核）');
    loadProjectDetail();
  }catch(e){ alert(e.message); }
}
async function fixItem(qid,iid,btn){
  try{
    const q=parseFloat(btn.closest('tr').querySelector('input').value);
    if(isNaN(q)||q<0){ alert('工程量需为非负数字'); return; }
    const r=await jpost('/api/quotes/'+qid+'/items/'+iid,{qty:q});
    btn.closest('tr').querySelector('td[id^="qa_"]').textContent='¥'+r.amount.toLocaleString();
    const qt=document.getElementById('q_total_'+qid);
    if(qt) qt.textContent='¥'+r.new_total.toLocaleString();
  }catch(e){ alert(e.message); }
}
async function reEstimate(qid){
  try{
    const a=parseFloat(document.getElementById('re_area').value)||0;
    const r=await jpost('/api/quotes/'+qid+'/estimate',{qty:a});
    alert('重估完成：'+r.re_estimated+' 项更新，保留 '+r.kept_manual+' 项人工值，新总额 ¥'+r.new_total.toLocaleString());
    loadProjectDetail();
  }catch(e){ alert(e.message); }
}
async function payStage(qid,btn){
  try{
    const stage=btn.dataset.stage;
    const amt=parseFloat(btn.parentElement.querySelector('input').value);
    if(isNaN(amt)||amt<=0){ alert('请输入大于 0 的收款金额'); return; }
    const r=await jpost('/api/quotes/'+qid+'/payments',{stage:stage,amount:amt,method:'转账'});
    alert('已登记收款：'+stage+' ¥'+r.amount.toLocaleString());
    loadProjectDetail();
  }catch(e){ alert(e.message); }
}
async function exportQuote(qid){
  try{
    const r=await jpost('/api/quotes/'+qid+'/export',{});
    window.open(r.url,'_blank');
  }catch(e){ alert(e.message); }
}
const U=()=>localStorage.getItem('platform_user')||'admin';
const R=()=>localStorage.getItem('platform_role')||'主管';
// 与 kernel/roles.py 对齐：主管/董事长全权，销售 起草/评分/邀约/审批，客服 起草/评分/迁移，其余只读
const CAN=a=>{const r=R();if(['主管','董事长'].includes(r))return true;
  if(r==='销售')return ['lead.write','transition','draft','score','invite','approve'].includes(a);
  if(r==='客服')return ['lead.write','transition','draft','score'].includes(a);return false;};
const esc=s=>String(s==null?'':s).replace(/[<>&]/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;'}[c]));
async function api(path,opts={}){
  const r=await fetch(path,opts);
  const d=await r.json();
  if(!r.ok) throw new Error((d.detail&&(typeof d.detail==='string'?d.detail:JSON.stringify(d.detail)))||d.error||('HTTP '+r.status));
  return d;
}
const jpost=(p,b)=>api(p,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...b,user:U()})});
function logout(){localStorage.removeItem('platform_user');location.href='/';}
document.getElementById('who').textContent=U()+' · '+R()+' · 壹城精工';
async function loadLeads(){
  const q=document.getElementById('q').value;
  try{
    const d=await api('/api/leads'+(q?'?q='+encodeURIComponent(q):''));
    document.getElementById('t-leads').innerHTML=d.items.map(x=>
      `<tr><td>${x.id}</td><td>${esc(x.name||'-')}</td><td>${esc(x.phone)}</td><td>${esc(x.estate||'-')}</td>
      <td>${esc(x.budget_range||'-')}</td><td>
        ${CAN('transition')
          ?`<select onchange="setStatus(${x.id},this.value)" style="font-size:12px;padding:3px 6px;border:1px solid #e0e0e0;border-radius:5px;">
             ${['线索','跟进','邀约','到店','派单'].map(s=>`<option value="${s}" ${x.status===s?'selected':''}>${s}</option>`).join('')}
           </select>`
          :`<span>${esc(x.status)}</span>`}
      </td><td>${x.score||0}</td>
      <td>
        ${CAN('draft')?`<button class="btn orange" onclick="draftLead(${x.id})">起草</button>`:''}
        ${CAN('score')?`<button class="btn green" onclick="score(${x.id})">评分</button>`:''}
        ${CAN('invite')?`<button class="btn" onclick="invite(${x.id})">邀约</button>`:''}
        ${CAN('dispatch')?`<button class="btn" onclick="dispatch(${x.id})">派单</button>`:''}
        <button class="btn ghost" onclick="toggleDetail(${x.id})">详情</button>
      </td></tr>
      <tr id="d-${x.id}" style="display:none"><td colspan="8" style="background:#fafafc;font-size:12px;line-height:1.7;"></td></tr>`).join('')||'<tr><td colspan=8>暂无数据</td></tr>';
    document.getElementById('m-leads').textContent='共 '+d.total+' 条';
  }catch(e){document.getElementById('m-leads').textContent='加载失败: '+e.message;}
}
async function importCsv(input){
  const f=input.files[0]; if(!f) return;
  const text=await f.text();
  try{
    const d=await jpost('/api/leads/import/csv',{csv_text:text});
    alert(`导入完成：新建 ${d.created} / 合并 ${d.merged} / 失败 ${d.error}（共 ${d.total} 行）`);
    loadLeads();
  }catch(e){alert('导入失败: '+e.message);}
  input.value='';
}
async function addLead(){
  try{
    const b={phone:document.getElementById('n_phone').value.trim()};
    if(!b.phone){alert('手机号必填');return;}
    for(const [k,v] of [['name','n_name'],['estate','n_estate'],['budget_range','n_budget'],['channel','n_channel']]){
      const el=document.getElementById(v); if(el.value.trim()) b[k]=el.value.trim();
    }
    const d=await jpost('/api/leads',b);
    alert(d.deduped?('已合并到客户 #'+d.id):('已录入客户 #'+d.id));
    loadLeads();
  }catch(e){alert('录入失败: '+e.message);}
}
async function score(id){try{const d=await jpost('/api/leads/'+id+'/score',{});alert('#'+id+' 评分 '+d.score+' 分 / '+d.grade);loadLeads();}catch(e){alert(e.message);}}
async function invite(id){const when=prompt('邀约时间（可留空）：','');try{await jpost('/api/leads/'+id+'/invite',{when:when||''});alert('邀约已生成');loadLeads();}catch(e){alert(e.message);}}
async function dispatch(id){const designer=document.getElementById('dp_designer').value;try{const d=await jpost('/api/dispatch',{customer_id:id,designer:designer||''});alert('项目 #'+d.id+' 已建（设计师:'+(designer||'待分配')+'）');loadLeads();loadProjects();}catch(e){alert(e.message);}}
async function draftLead(id){try{const d=await jpost('/api/inbox/draft',{customer_id:id});alert('AI 已起草 #'+d.message_id+'，到收件箱审批后发送');loadInbox();}catch(e){alert(e.message);}}
async function setStatus(id,to){try{await jpost('/api/leads/'+id+'/status',{to:to});loadLeads();}catch(e){alert('状态迁移被拦: '+e.message);loadLeads();}}
async function toggleDetail(id){
  const tr=document.getElementById('d-'+id);
  if(!tr) return;
  if(tr.style.display!=='none'){tr.style.display='none';return;}
  try{
    const d=await api('/api/leads/'+id);
    const l2=d.l2||[];
    const msgs=l2.map(m=>esc(m.content||'')).filter(Boolean).join('<br>');
    const prof=[d.estate,d.layout,d.area&&(d.area+'㎡'),d.budget_range,d.style,d.intent_time,d.channel,(Array.isArray(d.tags)?d.tags:(d.tags?String(d.tags).split(/[,，、]/):[]))].filter(Boolean).join(' / ');
    // === P0 客户旅程轨道：线索→跟进→邀约到店→派单→设计报价→签约成交 ===
    const STAGES=['线索','跟进','邀约到店','派单','设计报价','签约成交'];
    const curMap={'线索':0,'跟进':1,'邀约':2,'到店':2,'派单':3,'成交':5};
    const isLost=d.status==='流失';
    const cur=curMap[d.status]!=null?curMap[d.status]:0;
    const track=STAGES.map((s,i)=>{
      const done=!isLost&&i<cur;
      const active=!isLost&&i===cur;
      const cls=done?'done':(active?'active':'todo');
      const dot=done?'✓':(i+1);
      return '<div class="jr-node '+cls+'"><div class="jr-dot">'+dot+'</div><div class="jr-label">'+s+'</div></div>';
    }).join('<div class="jr-line"></div>');
    // 信息完整度（楼盘/面积/户型/风格/预算 5 项）
    const fields=[d.estate,d.area,d.layout,d.style,d.budget_range].filter(Boolean).length;
    const pct=Math.round(fields/5*100);
    // 停留天数
    let stay='-',stayDays=-1;
    if(d.created_at){try{stayDays=Math.floor((Date.now()-new Date(d.created_at.replace(' ','T')))/(86400000));stay=stayDays+' 天';}catch(e){}}
    // SOP 提示
    let sopHint;
    if(isLost){sopHint='<span style="color:#dc2626">已流失</span>';}
    else if(fields<3){sopHint='<span style="color:#d97706">信息未齐（'+fields+'/5），先补楼盘/面积/预算再跟进</span>';}
    else if(stayDays>=0&&stayDays>=1){sopHint='<span style="color:#d97706">已停留 '+stay+'，建议今天首联（首联2h窗口）</span>';}
    else{sopHint='<span style="color:#16a34a">状态正常</span>';}
    // === P1 Sentinel 审批闸门：根据客户状态推导关键确认项 ===
    const checks=[
      {label:'首联电话已拨', done:!!d.phone},
      {label:'信息双人复核（楼盘/面积/预算齐全）', done:!!(d.estate&&d.area&&d.budget_range)},
      {label:'报价已生成（有预算区间）', done:!!d.budget_range},
      {label:'折扣审批（<9.8折需总监批）', done:false, note:'未触发'},
      {label:'合同已签', done:d.status==='成交'},
      {label:'首付60%已收', done:d.status==='成交'}
    ];
    const checklist=checks.map(c=>
      '<div style="display:inline-block;margin:3px 14px 3px 0;font-size:12px;color:#334155;">'
      +(c.done?'<span style="color:#16a34a;font-weight:700;">☑</span> ':'<span style="color:#cbd5e1;font-weight:700;">☐</span> ')
      +c.label+'</div>').join('');
    const doneCount=checks.filter(c=>c.done).length;
    tr.innerHTML='<td colspan="8">'
      +'<div style="margin:4px 0 8px;">'+(isLost?'<span style="color:#dc2626;font-weight:600;">[流失] </span>':'')+track+'</div>'
      +'<div style="font-size:12px;color:#555;margin:6px 0;">信息完整度 <b>'+fields+'/5</b>　·　停留 <b>'+stay+'</b>　·　'+sopHint+'</div>'
      +'<div style="height:6px;background:#eef1f6;border-radius:3px;overflow:hidden;margin-bottom:10px;"><div style="height:100%;width:'+pct+'%;background:#3b82f6;"></div></div>'
      +'<div style="margin:6px 0 10px;padding:8px 12px;background:#f8fafc;border:1px solid #eef1f6;border-radius:6px;">'
      +'<div style="font-size:11px;color:#667085;margin-bottom:4px;">审批闸门 · Sentinel（对外动作默认人工确认）　已过 <b style="color:#16a34a;">'+doneCount+'/6</b></div>'
      +checklist+'</div>'
      +'<b>档案：</b>'+esc(prof||'未完善')+'<br><b>最近沟通（L2）：</b><br>'+(msgs||'暂无消息')+'</td>';
    tr.style.display='';
  }catch(e){alert(e.message);}
}
async function loadProjects(){
  try{
    const d=await api('/api/projects');
    document.getElementById('t-projects').innerHTML=d.items.map(x=>
      `<tr><td>${x.id}</td><td>#${x.customer_id}</td><td>${esc(x.status)}</td><td>${esc(x.designer||'-')}</td><td>${esc(x.created_at||'-')}</td></tr>`).join('')||'<tr><td colspan=5>暂无项目（派单后在此可见）</td></tr>';
  }catch(e){document.getElementById('m-projects').textContent='加载失败: '+e.message;}
}
async function loadInbox(){
  try{
    const d=await api('/api/inbox');
    document.getElementById('t-inbox').innerHTML=d.items.map(x=>
      `<tr><td>${x.id}</td><td>#${x.customer_id} ${esc(x.name||'-')}</td><td>${esc(x.content)}</td><td>${esc(x.created_at)}</td>
      <td>${CAN('approve')?`<button class="btn green" onclick="approve(${x.id})">审批发送</button>
      <button class="btn orange" onclick="reject(${x.id})">驳回</button>`:'<span style="color:#7a7a7a">待主管/销售审批</span>'}</td></tr>`).join('')||'<tr><td colspan=5>收件箱空（AI 起草后到这里审批）</td></tr>';
    var bn=document.getElementById('bell-n'); if(bn) bn.textContent=Math.min(d.items.length,99);
  }catch(e){document.getElementById('m-inbox').textContent='加载失败: '+e.message;}
}
async function approve(mid){try{await jpost('/api/inbox/'+mid+'/approve',{});alert('已发送（审计已记录）');loadInbox();}catch(e){alert(e.message);}}
async function reject(mid){const reason=prompt('驳回原因：','');try{await jpost('/api/inbox/'+mid+'/reject',{reason:reason||''});alert('已驳回');loadInbox();}catch(e){alert(e.message);}}
async function loadTodos(){
  try{
    const d=await api('/api/todos');
    document.getElementById('t-todos').innerHTML=d.items.map(x=>
      `<tr><td>${x.id}</td><td>#${x.customer_id} ${esc(x.name||'-')}</td><td>${esc(x.task)}</td>
      <td><button class="btn green" onclick="doneTodo(${x.id})">完成</button></td></tr>`).join('')||'<tr><td colspan=4>无待办</td></tr>';
  }catch(e){document.getElementById('m-todos').textContent='加载失败: '+e.message;}
}
async function doneTodo(tid){try{await jpost('/api/todos/'+tid+'/done',{});loadTodos();}catch(e){alert(e.message);}}
async function loadStats(){
  try{
    const d=await api('/api/stats');
    document.getElementById('t-stats').innerHTML=
      `<div class="card"><b>${d['24h首联率']}%</b>24h 首联率</div>
       <div class="card"><b>${d['响应时长中位数(小时)']??'-'}</b>响应时长中位数(h)</div>
       <div class="card"><b>${d['派单及时率(3日内)']}%</b>派单及时率</div>
       <div class="card"><b>${d['线索转化率(派单/线索)']}%</b>线索转化率</div>`;
  }catch(e){document.getElementById('t-stats').innerHTML='加载失败: '+e.message;}
}
async function searchKb(){
  const q=document.getElementById('kbq').value.trim();
  try{
    const d=await api('/api/kb/search?q='+encodeURIComponent(q)+'&top_k=5');
    document.getElementById('t-kb').innerHTML=d.hits.map(h=>
      `<div style="margin-bottom:8px"><b>${esc(h.title)}</b>（${esc(h.source)}）<br>${esc(h.snippet)}</div>`).join('')||'无命中';
  }catch(e){document.getElementById('t-kb').textContent='检索失败: '+e.message;}
}
// ===== 契约线（业主监理）：工艺问答 / 报价单 / 工地日报 =====
async function runQa(){
  const q=document.getElementById('qa_q').value.trim();
  if(!q){alert('请输入问题');return;}
  try{
    const d=await jpost('/api/agents/craft-qa',{question:q,category:document.getElementById('qa_cat').value.trim()});
    const crafts=(d.craft||[]).map(c=>
      `<div style="margin-bottom:8px"><b>${esc(c.title)}</b>（${esc(c.source||'-')}）<br>${esc(c.content)}</div>`).join('')||'<div class="msg">无命中（数据后填即可生效）</div>';
    const mh=(d.materials||[]).length?
      `<div style="margin:10px 0 4px"><b>材料参考价</b></div><table><tr><th>名称</th><th>规格</th><th>单价(元)</th><th>供应商</th></tr>`+
      d.materials.map(m=>`<tr><td>${esc(m.name)}</td><td>${esc(m.spec)}</td><td>${m.price??'待估价'}</td><td>${esc(m.supplier||'-')}</td></tr>`).join('')+'</table>':'';
    document.getElementById('t-qa').innerHTML=crafts+mh;
    document.getElementById('m-qa').textContent='草稿态，不对外发送（Sentinel read/draft 放行）';
  }catch(e){alert('查询失败: '+e.message);}
}
async function runQuote(){
  try{
    const d=await jpost('/api/agents/quote',{owner_id:parseInt(document.getElementById('q_owner').value),
      requirements:document.getElementById('q_req').value.trim(),category:document.getElementById('q_cat').value.trim()});
    document.getElementById('q_head').textContent=d.owner+' · 需求：'+(d.requirements||'-');
    document.getElementById('t-quote').innerHTML=
      '<tr>'+d.columns.map(c=>`<th>${esc(c)}</th>`).join('')+'</tr>'+
      d.rows.map(r=>'<tr>'+r.map(x=>`<td>${esc(x)}</td>`).join('')+'</tr>').join('')||'<tr><td colspan=7>无材料行</td></tr>';
    document.getElementById('m-quote').textContent='草稿态（status='+d.status+'），发送须人工确认 · Excel 导出接口预留';
  }catch(e){alert('生成失败: '+e.message);}
}
async function runReport(){
  const p=document.getElementById('rp_project').value.trim();
  if(!p){alert('请输入项目');return;}
  try{
    const d=await jpost('/api/agents/site-report',{project:p,photo_desc:document.getElementById('rp_note').value.trim()});
    document.getElementById('t-report').innerHTML=
      `<div><b>${esc(d.id)}</b> · ${esc(d.project)} · ${esc(d.date)}</div>
       <div style="margin-top:6px"><b>OCR 识别：</b>${esc(d.photo_ocr)}</div>
       <div><b>监理备注：</b>${esc(d.supervisor_note||'-')}</div>
       <div><b>进度摘要：</b>${esc(d.progress_summary)}</div>
       <div class="msg" style="color:#E07B39">状态：${esc(d.status)} — ${esc(d.sentinel)}（人工点发送才对外）</div>`;
  }catch(e){alert('生成失败: '+e.message);}
}
async function loadOwners(){
  try{
    const d=await api('/api/core/owners');
    document.getElementById('q_owner').innerHTML=(d.items||[]).map(o=>
      `<option value="${o.id}">#${o.id} ${esc(o.nickname||o.wechat_id)} · ${esc(o.community||'-')}</option>`).join('')||'<option value="">（暂无业主）</option>';
  }catch(e){}
}
// ---- 编队v3 九部门视图（P8）----
async function loadCeo(which){
  const el=document.getElementById('t-ceo');
  try{
    if(which==='approvals'){
      const d=await api('/api/team/ceo/approvals?user='+U());
      el.innerHTML='<div>待审消息草稿 <b>'+d.pending_messages.length+'</b> 条｜待审批报价 <b>'+d.pending_quote_approvals.length+'</b> 条｜待处理售后 <b>'+d.pending_after_sales.length+'</b> 条</div>'
        +(d.pending_quote_approvals||[]).map(q=>'<div>【报价#'+q.id+'】项目'+q.project_id+' ¥'+q.total.toLocaleString()+' '+(q.discount*100).toFixed(1)+'折</div>').join('')
        +(d.pending_after_sales||[]).map(x=>'<div>【售后#'+x.id+'】项目'+x.project_id+' '+esc(x.kind)+'：'+esc(x.title)+'</div>').join('');
    }else if(which==='dashboard'){
      const d=await api('/api/team/ceo/dashboard?user='+U());
      el.innerHTML='<div>客户漏斗: '+(d.customers_by_status||[]).map(r=>esc(r.status)+':'+r.n).join(' | ')+'</div>'
        +'<div>项目: '+(d.projects_by_status||[]).map(r=>esc(r.status)+':'+r.n).join(' | ')+'</div>'
        +'<div>累计收款 ¥'+d.payments_collected.toLocaleString()+'｜已批/签约报价总额 ¥'+d.approved_quotes_total.toLocaleString()+'｜验收合格 '+d.inspections_passed+' 个｜未办待办 '+d.open_todos+' 条</div>';
    }else{
      const d=await api('/api/team/ceo/audit?user='+U()+'&limit=10');
      el.innerHTML=(d.rows||[]).map(r=>'<div>#'+r.id+' '+esc(r.created_at)+' '+esc(r.user)+' '+esc(r.action)+' '+esc(r.target)+' ('+esc(r.before||'')+'→'+esc(r.after||'')+')</div>').join('')||'（无审计记录）';
    }
  }catch(e){el.textContent='加载失败：'+e.message;}
}
async function ceoCoord(){
  const note=document.getElementById('ceo_note').value.trim();
  if(!note){alert('请输入协调备注');return;}
  try{await jpost('/api/team/ceo/coord',{note});alert('协调记录已留痕');}
  catch(e){alert(e.message);}
}
async function loadMat(){
  const el=document.getElementById('t-mat');
  const qid=document.getElementById('mat_qid').value.trim();
  if(!qid){el.textContent='请输入报价ID';return;}
  try{
    const d=await api('/api/team/quotes/'+qid+'/materials?user='+U());
    let h='<div>报价 '+d.quote_id+' 主材清单：'+d.items_count+' 项（'+d.est_items+' 项估）合计 <b>¥'+d.material_total.toLocaleString()+'</b></div>';
    h+='<table><thead><tr><th>项目</th><th>规格</th><th>单位</th><th>数量</th><th>单价</th><th>金额</th></tr></thead><tbody>';
    h+=(d.items||[]).map(x=>'<tr><td>'+esc(x.name)+'</td><td style="font-size:12px;color:#7a7a7a">'+esc(x.spec||'')+'</td><td>'+esc(x.unit||'')+'</td><td>'+x.qty+'</td><td>¥'+(x.unit_price||0).toLocaleString()+'</td><td>¥'+(x.amount||0).toLocaleString()+'</td></tr>').join('');
    h+='</tbody></table>';
    el.innerHTML=h;
  }catch(e){el.textContent='加载失败：'+e.message;}
}
async function searchMat(){
  const el=document.getElementById('t-mat');
  const kw=document.getElementById('mat_kw').value.trim();
  try{
    const d=await api('/api/team/materials?user='+U()+'&keyword='+encodeURIComponent(kw));
    el.innerHTML=(d.rows||[]).map(r=>'<div>'+esc(r.category||'-')+'｜'+esc(r.name)+' '+esc(r.spec||'')+'｜¥'+r.price+'｜'+esc(r.supplier||'-')+'</div>').join('')||'（材料库无数据——契约线三表灌装后可查）';
  }catch(e){el.textContent='加载失败：'+e.message;}
}
async function loadSoft(){
  const el=document.getElementById('t-soft');
  const pid=document.getElementById('soft_pid').value.trim();
  if(!pid){el.textContent='请输入项目ID';return;}
  try{
    const d=await api('/api/team/soft?project_id='+pid+'&user='+U());
    if(!d.items_count){el.textContent='项目 '+pid+' 暂无软装项';return;}
    let h='<div>项目 '+d.project_id+' 软装清单：'+d.items_count+' 项 合计 <b>¥'+d.total.toLocaleString()+'</b></div>';
    (d.sections||[]).forEach(sec=>{
      h+='<div style="background:#f5f5f7;font-weight:700;font-size:12px;padding:5px 8px;margin-top:6px">'+esc(sec.category)+' · '+sec.count+' 项 · 小计 ¥'+sec.subtotal.toLocaleString()+'</div>';
      h+='<table><thead><tr><th>ID</th><th>品名</th><th>规格</th><th>数量</th><th>单价</th><th>金额</th><th>状态</th><th></th></tr></thead><tbody>';
      h+=(sec.items||[]).map(x=>'<tr><td>'+x.id+'</td><td>'+esc(x.name)+'</td><td style="font-size:12px;color:#7a7a7a">'+esc(x.spec||'')+'</td><td>'+x.qty+'</td><td>¥'+x.unit_price.toLocaleString()+'</td><td>¥'+x.amount.toLocaleString()+'</td><td>'+esc(x.status)+'</td>'
        +'<td><button class="btn" style="padding:2px 8px;font-size:12px" onclick="softUp('+x.id+')">确认</button>'
        +'<button class="btn" style="padding:2px 8px;font-size:12px;margin-left:4px" onclick="softDel('+x.id+')">删</button></td></tr>').join('');
      h+='</tbody></table>';
    });
    el.innerHTML=h;
  }catch(e){el.textContent='加载失败：'+e.message;}
}
async function softAdd(){
  const pid=document.getElementById('soft_pid').value.trim();
  const name=document.getElementById('soft_name').value.trim();
  if(!pid||!name){alert('项目ID与品名必填');return;}
  try{
    const r=await jpost('/api/team/soft',{project_id:parseInt(pid),
      category:document.getElementById('soft_cat').value,name,
      spec:document.getElementById('soft_spec').value.trim(),
      qty:parseFloat(document.getElementById('soft_qty').value)||1,
      unit_price:parseFloat(document.getElementById('soft_price').value)||0});
    alert('软装#'+r.id+' 已录入：¥'+r.amount.toLocaleString());
    loadSoft();
  }catch(e){alert(e.message);}
}
async function softUp(id){
  try{await jpost('/api/team/soft/'+id,{status:'已确认'});loadSoft();}
  catch(e){alert(e.message);}
}
async function softDel(id){
  try{await api('/api/team/soft/'+id+'?user='+U(),{method:'DELETE'});loadSoft();}
  catch(e){alert(e.message);}
}
async function loadAs(){
  const el=document.getElementById('t-as');
  const pid=document.getElementById('as_pid').value.trim();
  try{
    const d=await api('/api/team/aftersales?user='+U()+(pid?'&project_id='+pid:''));
    if(!(d.rows||[]).length){el.textContent='（无售后记录）';return;}
    el.innerHTML=(d.rows||[]).map(r=>'<div>#'+r.id+' 项目'+r.project_id+' '+esc(r.kind)+' '+esc(r.title)+' ['+esc(r.status)+'] '+esc(r.warranty_until||'')+' '+esc(r.result||'')+''
      +(r.kind==='售后工单'?' <button class="btn" style="padding:2px 8px;font-size:12px" onclick="asNext('+r.id+')">处理中</button><button class="btn" style="padding:2px 8px;font-size:12px" onclick="asClose('+r.id+')">关闭</button>':'')
      +'</div>').join('');
  }catch(e){el.textContent='加载失败：'+e.message;}
}
async function asWarranty(){
  const pid=document.getElementById('as_pid').value.trim();
  if(!pid){alert('请输入项目ID');return;}
  try{
    const r=await jpost('/api/team/aftersales/warranty',{project_id:parseInt(pid)});
    alert('质保登记完成：'+r.rows.map(x=>x.warranty_type+'→'+x.warranty_until).join(' | '));
    loadAs();
  }catch(e){alert(e.message);}
}
async function asTicket(){
  const pid=document.getElementById('as_pid').value.trim();
  const title=document.getElementById('as_title').value.trim();
  if(!pid||!title){alert('项目ID与标题必填');return;}
  try{
    const r=await jpost('/api/team/aftersales/ticket',{project_id:parseInt(pid),title,content:document.getElementById('as_content').value.trim()});
    alert('工单#'+r.id+' 已创建');
    loadAs();
  }catch(e){alert(e.message);}
}
async function asNext(id){try{await jpost('/api/team/aftersales/'+id+'/status',{status:'处理中'});loadAs();}catch(e){alert(e.message);}}
async function asClose(id){try{await jpost('/api/team/aftersales/'+id+'/status',{status:'已关闭'});loadAs();}catch(e){alert(e.message);}}
async function asDue(){
  try{
    const d=await jpost('/api/team/aftersales/due',{});
    alert('回访/质保提醒生成 '+d.created.length+' 条');
  }catch(e){alert(e.message);}
}
async function loadDesigners(){
  try{
    const d=await api('/api/team/designers');
    const sel=document.getElementById('dp_designer');
    const cur=sel.value;
    sel.innerHTML='<option value="">派单→待分配</option>'+(d.rows||[]).map(x=>
      '<option value="'+esc(x.account)+'">'+esc(x.account)+'('+esc(x.role)+')</option>').join('');
    if(cur) sel.value=cur;
  }catch(e){}
}
loadLeads();loadInbox();loadTodos();loadStats();loadProjects();loadOwners();loadDesigners();
</script></body></html>"""


class LoginBody(BaseModel):
    account: str
    password: str


def _hash_pwd(pwd: str) -> str:
    salt = b"homedesigngroup-v1"  # 与 init_platform.py 保持一致
    return hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), salt, 100_000).hex()


@app.get("/", response_class=HTMLResponse)
def index():
    return LOGIN_PAGE


@app.get("/exports/{fname}")
def export_file(fname: str):
    import os as _os
    from fastapi.responses import FileResponse
    p = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "exports", fname)
    if not _os.path.isfile(p) or ".." in fname:
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(p, filename=fname)


@app.get("/app", response_class=HTMLResponse)
def dashboard():
    return DASHBOARD_PAGE


@app.get("/health")
def health():
    db_ok, cfg_ok, llm_ok = False, False, False
    try:
        conn = sqlite3.connect(DB_PATH)
        v = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        db_ok = bool(v)
        conn.close()
    except Exception:
        db_ok = False
    try:
        config_loader.load_profile(COMPANY)
        cfg_ok = True
    except Exception:
        cfg_ok = False
    try:
        get_llm()
        llm_ok = True
    except Exception:
        llm_ok = False
    return {"status": "ok" if (db_ok and cfg_ok and llm_ok) else "degraded",
            "db": db_ok, "config": cfg_ok, "llm": llm_ok, "company": COMPANY}


@app.post("/api/chat_stream")
async def chat_stream_api(req: dict):
    """融合（S1）：获客对话智能体流式端点——业务 Agent 采集客户档案 + 按壹城规则自动报价"""
    from fastapi.responses import StreamingResponse
    from business_agent import stream_chat
    user_msg = (req.get("msg") or "").strip()
    cid = (req.get("cid") or "").strip()
    if not user_msg:
        return JSONResponse({"error": "msg 必填"}, status_code=400)
    return StreamingResponse(stream_chat(user_msg, cid), media_type="text/event-stream")


@app.post("/login")
def login(body: LoginBody):
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT pwd_hash, role, company FROM users WHERE account=?",
                           (body.account,)).fetchone()
        conn.close()
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"数据库异常: {e}"}, status_code=500)
    if not row:
        return JSONResponse({"ok": False, "error": "账号不存在"}, status_code=401)
    if row[0] != _hash_pwd(body.password):
        return JSONResponse({"ok": False, "error": "密码错误"}, status_code=401)
    return {"ok": True, "account": body.account, "role": row[1], "company": row[2]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000)
