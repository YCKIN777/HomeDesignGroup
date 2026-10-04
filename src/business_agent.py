import aiohttp
import json
import re

from providers.env import get_env, load_dotenv
from db import get_conn
from agents.kb_agent import KbAgent

load_dotenv()  # 确保 .env 已并入 os.environ（不依赖其他模块的导入顺序）

# ========= DeepSeek API Key：优先读 .env 的 DEEPSEEK_API_KEY，未配时复用平台 LLM_CLOUD_API_KEY =========
API_KEY = get_env("DEEPSEEK_API_KEY", "") or get_env("LLM_CLOUD_API_KEY", "")
API_URL = "https://api.deepseek.com/v1/chat/completions"

# 谈单知识库（S3 知识增强：回答前检索，命中片段拼入提示词）
_kb = KbAgent()

# 常见风格词（用于从用户消息中提取档案）
STYLE_KEYWORDS = ["奶油风", "现代简约", "新中式", "中式", "轻奢", "极简", "北欧", "原木风",
                  "法式", "侘寂", "工业风", "美式", "日式", "混搭", "奶油", "现代"]


def _extract_profile(text: str, profile: dict) -> dict:
    """从用户消息中提取楼盘/面积/户型/风格/预算，更新客户档案（已有字段不覆盖）"""
    # 面积：120平 / 120㎡ / 120平方米
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:㎡|平米|平方米|平方|平)", text)
    if m and not profile.get("面积"):
        profile["面积"] = m.group(1)
    # 户型：三房两厅 / 3室2厅 / 四房
    m = re.search(r"([一二三四五六七八九十\d])\s*(?:房|室)\s*([一二三四五六七八九十\d])\s*厅", text)
    if m and not profile.get("户型"):
        profile["户型"] = f"{m.group(1)}房{m.group(2)}厅"
    elif not profile.get("户型"):
        m2 = re.search(r"([一二三四五六七八九十\d])\s*(?:房|室)", text)
        if m2:
            profile["户型"] = m2.group(1) + "房"
    # 风格
    for s in STYLE_KEYWORDS:
        if s in text and not profile.get("风格"):
            profile["风格"] = s
            break
    # 预算：20万 / 20万元
    m = re.search(r"(\d+(?:\.\d+)?)\s*万(?:元)?", text)
    if m and not profile.get("预算"):
        profile["预算"] = m.group(1) + "万"
    # 楼盘：在保利和光尘樾有套房 → 保利和光尘樾
    m = re.search(r"(?:在|位于|看中|买了|考虑)\s*([\u4e00-\u9fa5A-Za-z0-9·\-]{2,16})", text)
    if m and not profile.get("楼盘"):
        cand = m.group(1)
        for kw in ["有套", "有房", "房子", "小区", "买了", "购房", "装修", "新居", "准备", "想装"]:
            i = cand.find(kw)
            if i > 0:
                cand = cand[:i]
                break
        profile["楼盘"] = cand.strip("的")
    if any([profile.get("楼盘"), profile.get("面积"), profile.get("户型")]):
        profile["status"] = "采集中"
    return profile

# 客户档案内存存储
customer_pool = {}
# 系统提示词：家装获客智能体，采集信息，信息齐全自动报价
SYSTEM_PROMPT = """
你是壹城精工家装获客顾问。
目标：收集客户信息：楼盘、房屋面积、户型、装修风格、预算。
对话规则：
1. 循序渐进提问，一次只问1项信息，不要一次性抛出一堆问题；
2. 自动识别客户回答，写入客户档案；
3. 当【楼盘+面积+户型+风格+预算】全部收集完成，自动调用报价逻辑，输出报价：总价按60/35/5付款比例，9.8折审批阈值；
4. 回复口语化，不要机器人腔调；
5. 客户档案实时维护，对话结束随流返回前端控制台。
客户档案结构：
{
"cid":"",
"楼盘":"",
"面积":"",
"户型":"",
"风格":"",
"预算":"",
"status":"收集中/已完成报价"
}
"""

async def stream_chat(user_msg:str, cid:str):
    # Key 未配置时给出友好错误，不发起调用
    if not API_KEY:
        yield json.dumps({"delta": "【配置提示】DeepSeek API Key 未配置，请在项目根目录 .env 中填写 DEEPSEEK_API_KEY 或 LLM_CLOUD_API_KEY 后重启服务。", "end": False}, ensure_ascii=False) + "\n\n"
        yield json.dumps({"end": True, "profile": {}}, ensure_ascii=False) + "\n\n"
        return
    # 初始化客户档案
    if cid not in customer_pool:
        customer_pool[cid] = {
            "cid":cid,
            "楼盘":"",
            "面积":"",
            "户型":"",
            "风格":"",
            "预算":"",
            "status":"收集中"
        }
    profile = customer_pool[cid]
    # 先解析用户消息，更新客户档案（楼盘/面积/户型/风格/预算）
    _extract_profile(user_msg, profile)
    # ---- S3 知识增强：检索谈单知识库，命中片段拼入提示词，回答/报价有依据 ----
    kb_block = ""
    try:
        hits = _kb.search(user_msg, top_k=3)
        if hits:
            kb_block = "\n参考知识（来自公司谈单知识库，回答与报价口径优先采用）：\n" + "\n".join(
                f"- [{h['title']}]({h['source']})：{h['snippet']}" for h in hits
            )
    except Exception:
        kb_block = ""
    messages = [
        {"role":"system", "content":SYSTEM_PROMPT + kb_block},
        {"role":"user", "content":f"当前客户档案：{json.dumps(profile,ensure_ascii=False)}\n用户消息：{user_msg}"}
    ]
    payload = {
        "model":"deepseek-chat",
        "messages":messages,
        "stream":True,
        "temperature":0.7
    }
    headers = {"Authorization":f"Bearer {API_KEY}", "Content-Type":"application/json"}

    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL, headers=headers, json=payload) as resp:
            async for line in resp.content:
                line = line.decode("utf-8").strip()
                if not line:
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        # ---- S2 数据打通：对话结束，有实质信息的档案写入 customers 线索池（仅建档一次） ----
                        if not profile.get("saved") and any([profile.get("楼盘"), profile.get("面积"), profile.get("户型")]):
                            profile["saved"] = True
                            try:
                                _area = None
                                try:
                                    _area = float(str(profile.get("面积", "")).replace("㎡", "").replace("平", "").strip() or 0) or None
                                except (TypeError, ValueError):
                                    _area = None
                                with get_conn() as conn:
                                    cur = conn.execute(
                                        "INSERT INTO customers (estate, area, layout, style, budget_range, channel, tags, source, status) "
                                        "VALUES (?,?,?,?,?,?,?,?,?)",
                                        (profile.get("楼盘") or None, _area, profile.get("户型") or None,
                                         profile.get("风格") or None, profile.get("预算") or None,
                                         "AI对话", "对话建档", "AI获客", "线索"))
                                    profile["customer_id"] = cur.lastrowid
                                    conn.commit()
                            except Exception:
                                profile["saved"] = False  # 写库失败不阻塞对话，下次再试
                        yield json.dumps({"end": True, "profile": profile}, ensure_ascii=False) + "\n\n"
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0]["delta"].get("content","")
                        yield json.dumps({"delta":delta},ensure_ascii=False)+"\n\n"
                    except Exception as e:
                        continue
