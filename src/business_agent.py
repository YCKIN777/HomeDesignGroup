import aiohttp
import json

# ========= 配置区，填入Deepseek APIKEY =========
API_KEY = "sk-926f1ea7a2c148a98983594e5113fdca"
API_URL = "https://api.deepseek.com/v1/chat/completions"

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
    messages = [
        {"role":"system", "content":SYSTEM_PROMPT},
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
                        yield json.dumps({"end":True, "profile":profile},ensure_ascii=False)+"\n\n"
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0]["delta"].get("content","")
                        yield json.dumps({"delta":delta},ensure_ascii=False)+"\n\n"
                    except Exception as e:
                        continue
