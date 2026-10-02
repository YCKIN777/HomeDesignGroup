# -*- coding: utf-8 -*-
"""vector_store.py — VectorStore（契约接口：add / search）

后端：
  FileVectorStore  文件型 JSON 向量库（data/chroma/ 下每 collection 一个 json）——
                   零依赖可运行，未来装 chromadb 后换 ChromaVectorStore 零改业务
  ChromaVectorStore 占位（chromadb 未安装时不可用，装好后即启用）
切换：VECTOR_STORE=chroma_local|qdrant_remote（缺依赖自动回退文件型并提示）
"""
import json
import math
import os
from typing import Optional

from providers.embedding import EmbeddingProvider, MockEmbedding

ROOT = r"H:\AgentProjects\HomeDesignGroup"
DATA_DIR = os.path.join(ROOT, "data", "chroma")


class Doc:
    """检索结果：文本 + 元数据 + 得分"""

    def __init__(self, text: str, metadata: Optional[dict] = None, score: float = 0.0):
        self.text = text
        self.metadata = metadata or {}
        self.score = score

    def __repr__(self):
        return f"Doc({self.text[:30]!r}, score={self.score:.3f})"


class VectorStore:
    provider = "base"

    def add(self, collection: str, docs: list, metadatas: Optional[list] = None):
        raise NotImplementedError

    def search(self, collection: str, query: str, top_k: int = 5) -> list:
        raise NotImplementedError


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


class FileVectorStore(VectorStore):
    """文件型 JSON 向量库：collection → {docs: [{text, metadata, vector}], emb_model}"""

    provider = "file"

    def __init__(self, embedding: EmbeddingProvider = None, data_dir: str = DATA_DIR):
        self.embedding = embedding or MockEmbedding()
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

    def _path(self, collection: str) -> str:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in collection)
        return os.path.join(self.data_dir, f"{safe}.json")

    def _load(self, collection: str) -> dict:
        p = self._path(collection)
        if not os.path.exists(p):
            return {"docs": []}
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    def add(self, collection: str, docs: list, metadatas: Optional[list] = None):
        data = self._load(collection)
        vectors = self.embedding.embed(docs)
        metas = metadatas or [{}] * len(docs)
        for text, vec, meta in zip(docs, vectors, metas):
            data["docs"].append({"text": text, "metadata": meta, "vector": vec})
        with open(self._path(collection), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def search(self, collection: str, query: str, top_k: int = 5) -> list:
        data = self._load(collection)
        if not data["docs"]:
            return []
        qv = self.embedding.embed([query])[0]
        scored = sorted(((_cosine(qv, d["vector"]), d) for d in data["docs"]),
                        key=lambda x: x[0], reverse=True)
        return [Doc(d["text"], d.get("metadata"), s) for s, d in scored[:top_k]]


class ChromaVectorStore(VectorStore):
    """Chroma 后端（文件型）：装好 chromadb 后启用，接口与 File 一致"""

    provider = "chroma"

    def __init__(self, path: str = DATA_DIR, embedding: EmbeddingProvider = None):
        import chromadb  # noqa: F401  # 仅在实例化时导入
        self.client = chromadb.PersistentClient(path=path)
        self.embedding = embedding or MockEmbedding()

    def _coll(self, collection: str):
        return self.client.get_or_create_collection(collection)

    def add(self, collection: str, docs: list, metadatas: Optional[list] = None):
        coll = self._coll(collection)
        emb = self.embedding.embed(docs)
        coll.add(ids=[f"d{i}" for i in range(len(docs))],
                 documents=docs, metadatas=metadatas or None, embeddings=emb)

    def search(self, collection: str, query: str, top_k: int = 5) -> list:
        coll = self._coll(collection)
        qv = self.embedding.embed([query])[0]
        res = coll.query(query_embeddings=[qv], n_results=top_k)
        return [Doc(d, m, s) for d, m, s in zip(
            res["documents"][0], res["metadatas"][0], res["distances"][0])]


def build_vector_store(mode: str, embedding: EmbeddingProvider = None) -> VectorStore:
    if mode == "qdrant_remote":
        # 未来上集群时实现 QdrantVectorStore（接口一致）
        raise NotImplementedError("Qdrant 后端为未来预留，当前用 VECTOR_STORE=chroma_local")
    if mode == "chroma_local":
        try:
            return ChromaVectorStore(embedding=embedding)
        except ImportError:
            print("[vector_store] chromadb 未安装，回退文件型 JSON 库（接口不变，未来零改切换）")
            return FileVectorStore(embedding=embedding)
    return FileVectorStore(embedding=embedding)
