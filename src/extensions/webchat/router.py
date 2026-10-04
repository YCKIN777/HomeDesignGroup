from fastapi import APIRouter
from pydantic import BaseModel
from openai import OpenAI

router = APIRouter()

# ========== 把这里换成你的 DeepSeek API Key ==========
DEEPSEEK_API_KEY = "sk-926f1ea7a2c148a98983594e5113fdca"
# =====================================================

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

# 内存存储多轮对话，服务重启记忆清空
chat_history = {}

class ChatReq(BaseModel):
    user_msg: str
    session_id: str = ""

@router.post("/chat")
async def chat_api(req: ChatReq):
    sid = req.session_id
    system_prompt = """
你是专业家装咨询顾问，擅长户型规划、风格推荐、预算、材料、软装搭配。
回答简洁易懂，面向业主。不要长篇学术话术。
"""
    if sid not in chat_history:
        chat_history[sid] = [{"role":"system", "content": system_prompt}]
    
    chat_history[sid].append({"role":"user", "content": req.user_msg})

    resp = client.chat.completions.create(
        model="deepseek-flash",
        messages=chat_history[sid],
        temperature=0.7,
        stream=False
    )
    ai_text = resp.choices[0].message.content
    chat_history[sid].append({"role":"assistant", "content": ai_text})

    return {"reply": ai_text}
