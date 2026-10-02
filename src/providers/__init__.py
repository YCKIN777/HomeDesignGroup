# -*- coding: utf-8 -*-
"""providers — Provider 抽象层（架构契约 v0.1 原则 1）

所有 LLM/Embedding/向量库/多模态调用只走本包接口，业务代码绝不直接
import 具体 SDK。切换云端/本地只改 .env 开关（LLM_PROVIDER / EMBEDDING_PROVIDER /
VECTOR_STORE / OCR_PROVIDER），业务代码零改动。

双轨兼容：新代码走本包（.env 驱动）；现有获客线继续走 src/llm.py（model_config.yaml），
两线互不破坏。未来 pip install litellm / chromadb 后，在对应后端工厂加一行即可切换。
"""
from providers.llm import ChatResult, Chunk, LLMProvider  # noqa: F401
from providers.embedding import EmbeddingProvider        # noqa: F401
from providers.vector_store import Doc, VectorStore      # noqa: F401
from providers.multimodal import MultimodalProvider      # noqa: F401
from providers.factory import get_providers              # noqa: F401
