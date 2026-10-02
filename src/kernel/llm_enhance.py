# -*- coding: utf-8 -*-
"""llm_enhance.py — LLM 增强层（可选层，架构契约原则 1）

契约线三 Agent 的主链路（检索/拼装/草稿态/Sentinel）不依赖 LLM；
本模块只负责"检索结果之上再生成自然语言润色"。

降级规则（保证骨架永远可跑）：
  - providers.llm.provider == "mock"（未配 key）→ 返回 enabled=False，text 为空
  - 调用异常（网络/超时/配额）→ 捕获并返回 enabled=False + error 说明
  - 结果过长 → 截断，避免污染响应体
"""
from providers.factory import get_providers


def llm_enhance(providers, system: str, user: str, max_chars: int = 500) -> dict:
    """单次 LLM 增强调用。返回 {enabled, provider, text, error?}，永不抛异常。"""
    if providers.llm.provider == "mock":
        return {"enabled": False, "provider": "mock", "text": ""}
    try:
        r = providers.llm.chat([
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ], temperature=0.3)
        text = (r.text or "").strip()
        if len(text) > max_chars:
            text = text[:max_chars] + "…"
        return {"enabled": True, "provider": r.provider, "text": text}
    except Exception as e:   # noqa: BLE001
        return {"enabled": False, "provider": "error", "text": "", "error": str(e)}


if __name__ == "__main__":
    p = get_providers()
    r = llm_enhance(p, "测试系统", "测试用户")
    print("providers:", p.summary())
    print("enhance:", r)
