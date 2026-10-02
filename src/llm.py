# -*- coding: utf-8 -*-
"""
llm.py — LLM 抽象层（Step 1.5）
设计对齐《整体技术框架v1》：provider 可插拔，只改 config/model_config.yaml。
接口：
  chat(messages) -> str        messages=[{"role","content"}, ...]
  summarize(text) -> str       文本摘要（默认走 chat）
工厂：
  get_llm(force=None) -> BaseLLM   按配置 provider 返回实例
Provider：
  MockLLM  开发占位（无需 key，确定性输出）
  DoubaoLLM  豆包 API（key 从环境变量读，未配置则清晰报错）
  OllamaLLM  本地 Ollama
"""
import json
import os
import urllib.request

import yaml

ROOT = r"H:\AgentProjects\HomeDesignGroup"
CONFIG_PATH = os.path.join(ROOT, "config", "model_config.yaml")


class LLMError(RuntimeError):
    """模型调用错误（含未配置提示）"""


class BaseLLM:
    provider = "base"

    def chat(self, messages: list) -> str:
        raise NotImplementedError

    def summarize(self, text: str) -> str:
        return self.chat([
            {"role": "system", "content": "你是家装公司智能体，请精炼总结以下内容，保留关键事实。"},
            {"role": "user", "content": text},
        ])


class MockLLM(BaseLLM):
    """开发占位：确定性输出，让骨架/测试无需 key 即可运行"""
    provider = "mock"

    def __init__(self, temperature: float = 0.3):
        self.temperature = temperature

    def chat(self, messages: list) -> str:
        last = messages[-1]["content"] if messages else ""
        return f"[mock] 收到{len(messages)}条消息，末条: {last[:80]}"


class DoubaoLLM(BaseLLM):
    provider = "doubao"

    def __init__(self, model: str, api_key_env: str, base_url: str):
        self.model = model
        self.api_key_env = api_key_env
        self.base_url = base_url

    def chat(self, messages: list) -> str:
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise LLMError(
                f"未配置环境变量 {self.api_key_env}（豆包 API Key）。"
                f"设置后重启，或在 model_config.yaml 把 provider 改为 mock/ollama。")
        payload = json.dumps({"model": self.model, "messages": messages}).encode("utf-8")
        req = urllib.request.Request(
            self.base_url, data=payload,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {api_key}"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except Exception as e:  # 网络/响应异常统一包装
            raise LLMError(f"豆包 API 调用失败: {e}") from e


class OllamaLLM(BaseLLM):
    provider = "ollama"

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def chat(self, messages: list) -> str:
        payload = json.dumps({"model": self.model, "messages": messages,
                              "stream": False}).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/api/chat", data=payload,
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["message"]["content"]
        except Exception as e:
            raise LLMError(f"Ollama 调用失败（服务是否启动?）: {e}") from e


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
        return yaml.safe_load(f) or {}


def get_llm(force: str = None) -> BaseLLM:
    cfg = load_config()
    provider = force or cfg.get("provider", "mock")
    if provider == "mock":
        return MockLLM(cfg.get("mock", {}).get("temperature", 0.3))
    if provider == "doubao":
        d = cfg.get("doubao", {})
        return DoubaoLLM(d["model"], d["api_key_env"], d["base_url"])
    if provider == "ollama":
        o = cfg.get("ollama", {})
        return OllamaLLM(o["base_url"], o["model"])
    raise LLMError(f"未知 provider: {provider}（可选 mock/doubao/ollama）")
