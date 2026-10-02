# -*- coding: utf-8 -*-
"""env.py — .env 加载器 + 配置读取（双轨：.env 优先，回退 model_config.yaml）"""
import os

ROOT = r"H:\AgentProjects\HomeDesignGroup"
ENV_PATH = os.path.join(ROOT, ".env")


_loaded = False


def load_dotenv(path: str = ENV_PATH) -> dict:
    """手写 .env 解析（无第三方依赖）：KEY=VALUE，# 注释。

    首次调用把 .env 并入 os.environ（已存在的环境变量优先，不覆盖）；
    后续调用返回缓存，不再改写 os.environ——保证运行期调整/测试模拟生效。
    """
    global _loaded
    if _loaded:
        return {}
    _loaded = True
    if not os.path.exists(path):
        return {}
    data = {}
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key:
                data[key] = val
                os.environ.setdefault(key, val)
    return data


def get_env(key: str, default: str = "") -> str:
    """读环境变量（.env 已并入 os.environ）"""
    return os.environ.get(key, default)


def provider_mode(kind: str = "LLM") -> str:
    """返回 cloud|local|mock（缺 .env 或 key 未配时给 mock 占位）。"""
    key = f"{kind}_PROVIDER"
    mode = get_env(key, "").strip().lower()
    if not mode:
        return "mock"
    return mode if mode in ("cloud", "local", "mock") else "mock"
