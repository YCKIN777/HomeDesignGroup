# -*- coding: utf-8 -*-
"""llm.py — LLMProvider（契约接口：chat / stream）

后端（每类至少双实现，契约原则 1）：
  CloudOpenAI   云端，OpenAI 兼容协议（豆包/DeepSeek/智谱/通义皆可，只改 base_url/model/key）
  OllamaLocal   本地 Ollama（/api/chat）
  MockLLM       占位（无 key 时兜底，确定性输出）
切换：LLM_PROVIDER=cloud|local|mock（.env）
"""
import json
import os
import urllib.request
from typing import Iterator, Optional

from providers.env import get_env

PROTOCOL_KEY = "LLM_CLOUD_API_KEY"


class ChatResult:
    """统一返回结构：text 必填；usage 可选；provider 标明后端"""

    def __init__(self, text: str, provider: str = "", usage: Optional[dict] = None):
        self.text = text
        self.provider = provider
        self.usage = usage or {}

    def __repr__(self):
        return f"ChatResult({self.text[:40]!r}, provider={self.provider})"


class Chunk:
    """流式分片：delta 文本片段"""

    def __init__(self, delta: str):
        self.delta = delta


class LLMProvider:
    provider = "base"

    def chat(self, messages: list, tools: Optional[list] = None,
             temperature: float = 0.3) -> ChatResult:
        raise NotImplementedError

    def stream(self, messages: list, tools: Optional[list] = None,
               temperature: float = 0.3) -> Iterator[Chunk]:
        raise NotImplementedError


class MockLLM(LLMProvider):
    """开发占位：确定性输出，让骨架/测试无需 key 即可运行"""

    provider = "mock"

    def chat(self, messages, tools=None, temperature=0.3) -> ChatResult:
        last = messages[-1]["content"] if messages else ""
        return ChatResult(f"[mock] 收到{len(messages)}条消息，末条: {last[:80]}",
                          provider="mock")

    def stream(self, messages, tools=None, temperature=0.3) -> Iterator[Chunk]:
        text = self.chat(messages, tools, temperature).text
        for ch in text:
            yield Chunk(ch)


class CloudOpenAI(LLMProvider):
    """云端 OpenAI 兼容协议（豆包/DeepSeek/智谱/通义）"""

    provider = "cloud"

    def __init__(self, base_url: str, api_key: str, model: str):
        if not api_key or api_key.startswith("your_"):
            raise ValueError("LLM_CLOUD_API_KEY 未配置：复制 .env.example 为 .env 后填写")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def _request(self, messages, tools=None, temperature=0.3, stream=False) -> dict:
        payload = {"model": self.model, "messages": messages,
                   "temperature": temperature, "stream": stream}
        if tools:
            payload["tools"] = tools
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def chat(self, messages, tools=None, temperature=0.3) -> ChatResult:
        data = self._request(messages, tools, temperature)
        return ChatResult(data["choices"][0]["message"]["content"], provider="cloud",
                          usage=data.get("usage"))

    def stream(self, messages, tools=None, temperature=0.3) -> Iterator[Chunk]:
        # OpenAI 兼容流式接口返回 SSE：逐行 `data: {...}` / `data: [DONE]`
        payload = {"model": self.model, "messages": messages,
                   "temperature": temperature, "stream": True}
        if tools:
            payload["tools"] = tools
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "ignore").strip()
                if not line or line.startswith(":"):
                    continue
                if line.startswith("data:"):
                    line = line[5:].strip()
                if line == "[DONE]":
                    break
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                delta = d.get("choices", [{}])[0].get("delta", {}).get("content")
                if delta:
                    yield Chunk(delta)


class OllamaLocal(LLMProvider):
    """本地 Ollama"""

    provider = "local"

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def chat(self, messages, tools=None, temperature=0.3) -> ChatResult:
        payload = json.dumps({"model": self.model, "messages": messages,
                              "stream": False}).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/api/chat", data=payload,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return ChatResult(data["message"]["content"], provider="local",
                          usage={"prompt_eval_count": data.get("prompt_eval_count"),
                                 "eval_count": data.get("eval_count")})

    def stream(self, messages, tools=None, temperature=0.3) -> Iterator[Chunk]:
        payload = json.dumps({"model": self.model, "messages": messages,
                              "stream": True}).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/api/chat", data=payload,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            for raw in resp:
                if not raw.strip():
                    continue
                d = json.loads(raw)
                if d.get("message", {}).get("content"):
                    yield Chunk(d["message"]["content"])


def build_llm(mode: str) -> LLMProvider:
    """按模式构建后端：cloud→OpenAI兼容；local→Ollama；mock→占位。key 缺失抛 ValueError"""
    if mode == "cloud":
        return CloudOpenAI(get_env("LLM_CLOUD_BASE_URL",
                                   "https://ark.cn-beijing.volces.com/api/v3"),
                           get_env("LLM_CLOUD_API_KEY", ""),
                           get_env("LLM_CLOUD_MODEL", "doubao-seed-1-6-250615"))
    if mode == "local":
        return OllamaLocal(get_env("LLM_LOCAL_BASE_URL", "http://localhost:11434"),
                           get_env("LLM_LOCAL_MODEL", "qwen2.5:14b"))
    return MockLLM()
