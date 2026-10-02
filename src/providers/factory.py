# -*- coding: utf-8 -*-
"""factory.py — Provider 统一工厂（架构契约原则 1 的切换总闸）

业务代码只调 get_providers() 拿到的实例；切换云端/本地只改 .env：
  LLM_PROVIDER / EMBEDDING_PROVIDER / VECTOR_STORE / OCR_PROVIDER
缺 key 自动降级 mock 并在 stderr 提示（骨架始终可运行）。
"""
import os
import sys

from providers.env import load_dotenv, provider_mode
from providers.embedding import EmbeddingProvider, build_embedding
from providers.llm import LLMProvider, build_llm
from providers.multimodal import MultimodalProvider, build_multimodal
from providers.vector_store import VectorStore, build_vector_store


class Providers:
    """四件套容器"""

    def __init__(self, llm: LLMProvider, embedding: EmbeddingProvider,
                 vector_store: VectorStore, multimodal: MultimodalProvider):
        self.llm = llm
        self.embedding = embedding
        self.vector_store = vector_store
        self.multimodal = multimodal

    def summary(self) -> dict:
        return {"llm": self.llm.provider, "embedding": self.embedding.provider,
                "vector_store": getattr(self.vector_store, "provider", "?"),
                "multimodal": self.multimodal.provider}

    def __repr__(self):
        return f"Providers({self.summary()})"


def get_providers() -> Providers:
    """统一入口：按 .env 组装四件套；缺配置安全降级 mock"""
    load_dotenv()

    # LLM：cloud/local 需要对应 key；缺失则 mock + 提示
    llm_mode = provider_mode("LLM")
    if llm_mode in ("cloud", "local"):
        try:
            llm = build_llm(llm_mode)
        except (ValueError, NotImplementedError) as e:
            print(f"[providers] LLM_PROVIDER={llm_mode} 不可用（{e}），降级 mock", file=sys.stderr)
            llm = build_llm("mock")
            llm_mode = "mock"
    else:
        llm = build_llm("mock")

    emb_mode = provider_mode("EMBEDDING")
    if emb_mode in ("cloud", "local"):
        try:
            embedding = build_embedding(emb_mode)
        except (ValueError, NotImplementedError) as e:
            print(f"[providers] EMBEDDING_PROVIDER={emb_mode} 不可用（{e}），降级 mock",
                  file=sys.stderr)
            embedding = build_embedding("mock")
            emb_mode = "mock"
    else:
        embedding = build_embedding("mock")

    vs_mode = os.environ.get("VECTOR_STORE", "chroma_local").strip().lower()
    try:
        vector_store = build_vector_store(vs_mode, embedding=embedding)
    except (NotImplementedError, ImportError) as e:
        print(f"[providers] VECTOR_STORE={vs_mode} 不可用（{e}），回退文件型", file=sys.stderr)
        vector_store = build_vector_store("chroma_local", embedding=embedding)

    ocr_mode = provider_mode("OCR")
    if ocr_mode in ("cloud", "local"):
        try:
            multimodal = build_multimodal(ocr_mode)
        except (ValueError, NotImplementedError) as e:
            print(f"[providers] OCR_PROVIDER={ocr_mode} 不可用（{e}），降级 mock", file=sys.stderr)
            multimodal = build_multimodal("mock")
    else:
        multimodal = build_multimodal("mock")

    return Providers(llm, embedding, vector_store, multimodal)


if __name__ == "__main__":
    p = get_providers()
    print("providers:", p.summary())
    print("llm.chat:", p.llm.chat([{"role": "user", "content": "你好"}]).text[:50])
    print("embedding:", len(p.embedding.embed(["测试"])[0]), "维")
    p.vector_store.add("smoke", ["降噪隔墙怎么做"], [{"cat": "工艺"}])
    hits = p.vector_store.search("smoke", "隔墙", top_k=1)
    print("vs.search:", hits)
    print("ocr:", p.multimodal.ocr(b"fake"))
