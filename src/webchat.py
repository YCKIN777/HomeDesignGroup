from fastapi import FastAPI
from fastapi.responses import StreamingResponse, HTMLResponse
import asyncio
from business_agent import stream_chat

app = FastAPI()

@app.get("/ext-webchat", response_class=HTMLResponse)
async def web_chat_page():
    html = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>壹城精工·家装AI咨询</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:system-ui, sans-serif;}
body{background:#f4f6f8;padding:16px;max-width:900px;margin:0 auto;}
.chat-wrap{background:#fff;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,0.1);overflow:hidden;}
.chat-header{background:#1677ff;color:#fff;padding:14px 18px;display:flex;justify-content:space-between;align-items:center;}
#chatBox{height:600px;overflow-y:auto;padding:16px;}
.msg{margin-bottom:14px;display:flex;}
.msg.user{justify-content:flex-end;}
.msg-bubble{max-width:75%;padding:10px 14px;border-radius:8px;white-space:pre-wrap;}
.user .msg-bubble{background:#1677ff;color:#fff;}
.ai .msg-bubble{background:#f0f2f5;color:#222;}
.input-area{display:flex;padding:12px;border-top:1px solid #eee;gap:8px;}
#msgInput{flex:1;padding:10px 12px;border:1px solid #ddd;border-radius:8px;font-size:16px;outline:none;}
#sendBtn,#clearBtn{padding:10px 16px;border:none;border-radius:8px;background:#1677ff;color:#fff;cursor:pointer;font-size:14px;}
#clearBtn{background:#ff4d4f;}
</style>
</head>
<body>
<div class="chat-wrap">
    <div class="chat-header">
        <h3>壹城精工家装咨询</h3>
        <button id="clearBtn">清空对话</button>
    </div>
    <div id="chatBox"></div>
    <div class="input-area">
        <input id="msgInput" placeholder="请说出您的装修需求..." />
        <button id="sendBtn">发送</button>
    </div>
</div>

<script>
const chatBox = document.getElementById("chatBox");
const msgInput = document.getElementById("msgInput");
const sendBtn = document.getElementById("sendBtn");
const clearBtn = document.getElementById("clearBtn");
let cid = "";

function addMsg(type, text){
    const divWrap = document.createElement("div");
    divWrap.className = `msg ${type}`;
    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";
    bubble.textContent = text;
    divWrap.appendChild(bubble);
    chatBox.appendChild(divWrap);
    chatBox.scrollTop = chatBox.scrollHeight;
    return bubble;
}

async function sendStreamMsg(text){
    if(!cid) cid = `cus_${Date.now()}`;
    addMsg("user", text);
    msgInput.value = "";
    msgInput.disabled = true;
    sendBtn.disabled = true;

    const aiWrap = document.createElement("div");
    aiWrap.className = "msg ai";
    const aiBubble = document.createElement("div");
    aiBubble.className = "msg-bubble";
    aiWrap.appendChild(aiBubble);
    chatBox.appendChild(aiWrap);
    chatBox.scrollTop = chatBox.scrollHeight;
    let fullStr = "";

    const resp = await fetch("/api/chat_stream",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({msg:text,cid:cid})
    });
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while(true){
        const {done,value} = await reader.read();
        if(done) break;
        buf += decoder.decode(value, {stream:true});
        const lines = buf.split("\n\n");
        buf = lines.pop();
        for(let line of lines){
            if(!line.startsWith("data: ")) continue;
            const raw = line.slice(6);
            try{
                const obj = JSON.parse(raw);
                if(obj.delta){
                    fullStr += obj.delta;
                    aiBubble.textContent = fullStr;
                    chatBox.scrollTop = chatBox.scrollHeight;
                }
                if(obj.end){
                    console.log("客户档案：", obj.profile);
                }
            }catch(e){}
        }
    }
    msgInput.disabled = false;
    sendBtn.disabled = false;
}

sendBtn.onclick = ()=>{
    const txt = msgInput.value.trim();
    if(txt) sendStreamMsg(txt);
}
msgInput.onkeydown = (e)=>{
    if(e.key === "Enter"){
        const txt = msgInput.value.trim();
        if(txt) sendStreamMsg(txt);
    }
}
clearBtn.onclick = async ()=>{
    cid = "";
    chatBox.innerHTML = "";
}
</script>
</body>
</html>"""
    return HTMLResponse(html)

@app.post("/api/chat_stream")
async def chat_stream(req:dict):
    user_msg = req["msg"]
    cid = req["cid"]
    return StreamingResponse(stream_chat(user_msg,cid), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("webchat:app", host="127.0.0.1", port=8001, reload=True)
