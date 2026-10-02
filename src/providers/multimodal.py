# -*- coding: utf-8 -*-
"""multimodal.py — MultimodalProvider（契约接口：ocr(image_bytes) -> str，户型图识别用）

后端：
  CloudOCR    云端 OCR（OpenAI 兼容 vision 消息占位：接入具体 OCR 服务时填 base_url/key）
  MockOCR     占位：返回确定性文本（无 key 兜底，骨架/测试用）
切换：OCR_PROVIDER=cloud|local|mock（local 预留本地 PaddleOCR 等，接口一致）
"""
from providers.env import get_env


class MultimodalProvider:
    provider = "base"

    def ocr(self, image_bytes: bytes) -> str:
        raise NotImplementedError


class MockOCR(MultimodalProvider):
    """占位：返回固定识别文本（骨架可运行；接真实 OCR 后替换）"""

    provider = "mock"

    def ocr(self, image_bytes: bytes) -> str:
        return "[mock-ocr] 户型图：三室两厅，客厅朝南，主卧带飘窗（占位文本，接真实 OCR 后替换）"


class CloudOCR(MultimodalProvider):
    """云端 OCR（OpenAI 兼容 vision 消息——占位实现，接入具体服务时填写 base_url/key）"""

    provider = "cloud"

    def __init__(self, base_url: str, api_key: str, model: str = "doubao-vision"):
        if not api_key or api_key.startswith("your_"):
            raise ValueError("OCR_CLOUD_API_KEY 未配置")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def ocr(self, image_bytes: bytes) -> str:
        raise NotImplementedError(
            "云端 OCR 需按具体服务商协议实现（当前为占位）：接入后业务代码不变")


def build_multimodal(mode: str) -> MultimodalProvider:
    if mode == "cloud":
        return CloudOCR(get_env("OCR_CLOUD_BASE_URL", ""),
                        get_env("OCR_CLOUD_API_KEY", ""))
    if mode == "local":
        # 本地 OCR（PaddleOCR 等）未来接入，接口不变
        raise NotImplementedError("本地 OCR 后端为预留位（PaddleOCR 等），当前用 OCR_PROVIDER=mock")
    return MockOCR()
