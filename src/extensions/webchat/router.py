from fastapi import APIRouter
from pydantic import BaseModel
from openai import OpenAI

from providers.env import get_env, load_dotenv

router = APIRouter()

load_dotenv()  # 确保 .env 已并入 os.environ（不依赖其他模块的导入顺序）

# ========== DeepSeek API Key：优先读 .env 的 DEEPSEEK_API_KEY，未配时复用平台 LLM_CLOUD_API_KEY ==========
DEEPSEEK_API_KEY = get_env("DEEPSEEK_API_KEY", "") or get_env("LLM_CLOUD_API_KEY", "")
# =====================================================

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
) if DEEPSEEK_API_KEY else None

# 内存存储多轮对话，服务重启记忆清空
chat_history = {}

class ChatReq(BaseModel):
    user_msg: str
    session_id: str = ""

@router.post("/chat")
async def chat_api(req: ChatReq):
    if not DEEPSEEK_API_KEY:
        return {"reply": "【配置提示】DeepSeek API Key 未配置，请在项目根目录 .env 中填写 DEEPSEEK_API_KEY 或 LLM_CLOUD_API_KEY 后重启服务。"}
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
