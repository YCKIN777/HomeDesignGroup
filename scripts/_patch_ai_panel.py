# -*- coding: utf-8 -*-
"""融合 S4：工作台加 AI 顾问对话面板（获客对话智能体入口）"""
import io

PATH = r"H:\AgentProjects\HomeDesignGroup\src\api_server.py"
s = io.open(PATH, encoding="utf-8").read()

# ===== 1) 导航：SOP 待办后加 AI 顾问（获客组） =====
old_nav = '<a data-tab="s-todos" onclick="showTab(\'s-todos\')">SOP 待办</a>'
new_nav = old_nav + '\n      <a data-tab="s-ai" onclick="showTab(\'s-ai\')">AI 顾问</a>'
assert old_nav in s, "nav anchor"
s = s.replace(old_nav, new_nav, 1)

# ===== 2) 面板：</main> 前插入 AI 顾问 section =====
old_main = "  </section>\n    </main>"
ai_panel = """  <section id="s-ai" style="display:none"><h2>AI 顾问 · 获客对话</h2><p class="panel-sub">流式对话 · 自动建档（楼盘/面积/户型/风格/预算）· 信息齐全按壹城规则报价</p>
    <div class="card" style="display:flex;flex-direction:column;height:540px;padding:0;overflow:hidden">
      <div id="ai-msgs" style="flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px;background:#f5f5f7"></div>
      <div style="display:flex;gap:8px;padding:12px;border-top:1px solid var(--line)">
        <input id="ai-input" class="input" style="flex:1" placeholder="例如：想装 120 平三房，奶油风，预算 20 万左右">
        <button class="btn green" onclick="aiSend()">发送</button>
        <button class="btn" onclick="aiClear()">清空</button>
      </div>
    </div>
  </section>
    </main>"""
assert old_main in s, "main anchor"
s = s.replace(old_main, ai_panel, 1)

# ===== 3) JS：showTab 前插入 AI 对话逻辑 =====
old_js = "<script>\nfunction showTab(id){"
ai_js = """<script>
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
        var ln = lines[i]; if(ln.indexOf('data: ') !== 0) continue;
        try{ var o = JSON.parse(ln.slice(6)); if(o.delta){ full += o.delta; b.textContent = full; } }catch(e){}
      }
    }
  }catch(e){ b.textContent = '连接失败: ' + e.message; }
  input.disabled = false; input.focus();
}
function aiClear(){ aiCid=''; localStorage.removeItem('ai_cid'); document.getElementById('ai-msgs').innerHTML=''; }
function showTab(id){"""
assert old_js in s, "js anchor"
s = s.replace(old_js, ai_js, 1)

io.open(PATH, "w", encoding="utf-8", newline="").write(s)
print("PATCH OK")
