# -*- coding: utf-8 -*-
"""embedding.py — EmbeddingProvider（契约接口：embed(texts) -> list[list[float]]）

后端：
  CloudEmbedding   云端 OpenAI 兼容（豆包 embedding 等）
  OllamaEmbedding  本地 Ollama /api/embeddings（bge-m3）
  MockEmbedding    占位：确定性哈希向量（维度 64，无 key 兜底）
切换：EMBEDDING_PROVIDER=cloud|local|mock
"""
import hashlib
import json
import math
import os
import urllib.request

from providers.env import get_env

DIM = 64


class EmbeddingProvider:
    provider = "base"

    def embed(self, texts: list) -> list:
        raise NotImplementedError


class MockEmbedding(EmbeddingProvider):
    """占位：字符 n-gram 特征向量（确定性、有字面相似信号）
    同文本同向量；含相同词/短语的文本得分更高（骨架期近似语义，换真模型后行为升级）"""

    provider = "mock"

    def embed(self, texts: list) -> list:
        out = []
        for t in texts:
            vec = [0.0] * DIM
            grams = {t[i:i + 2] for i in range(len(t) - 1)} | {t}
            for g in grams:
                h = int(hashlib.md5(g.encode("utf-8")).hexdigest()[:4], 16)
                vec[h % DIM] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out


class CloudEmbedding(EmbeddingProvider):
    provider = "cloud"

    def __init__(self, base_url: str, api_key: str, model: str):
        if not api_key or api_key.startswith("your_"):
            raise ValueError("EMBEDDING_CLOUD_API_KEY 未配置")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def embed(self, texts: list) -> list:
        payload = json.dumps({"model": self.model, "input": texts}).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/embeddings", data=payload,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return [d["embedding"] for d in data["data"]]


class OllamaEmbedding(EmbeddingProvider):
    provider = "local"

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def embed(self, texts: list) -> list:
        out = []
        for t in texts:
            payload = json.dumps({"model": self.model, "input": t}).encode("utf-8")
            req = urllib.request.Request(
                self.base_url + "/api/embeddings", data=payload,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            out.append(data["embedding"])
        return out


def build_embedding(mode: str) -> EmbeddingProvider:
    if mode == "cloud":
        return CloudEmbedding(get_env("EMBEDDING_CLOUD_BASE_URL",
                                      "https://ark.cn-beijing.volces.com/api/v3"),
                              get_env("EMBEDDING_CLOUD_API_KEY", ""),
                              get_env("EMBEDDING_CLOUD_MODEL", "doubao-embedding"))
    if mode == "local":
        return OllamaEmbedding(get_env("EMBEDDING_LOCAL_BASE_URL",
                                       "http://localhost:11434"),
                               get_env("EMBEDDING_LOCAL_MODEL", "bge-m3"))
    return MockEmbedding()
