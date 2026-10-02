# -*- coding: utf-8 -*-
"""verify_providers.py — Step 2 smoke test：Provider 抽象层四件套 + 切换逻辑"""
import json
import os
import sys

sys.path.insert(0, r"H:\AgentProjects\HomeDesignGroup\src")

from providers.env import load_dotenv
from providers.factory import get_providers
from providers.llm import build_llm
from providers.embedding import build_embedding

fails = []


def check(name, cond, msg):
    if not cond:
        fails.append(name)
        print(f"[FAIL] {name}: {msg}")
    else:
        print(f"[PASS] {name}")


# 0. 加载 .env（未配置时为空，走 mock 兜底）
load_dotenv()
p = get_providers()
check("四件套就绪", all(getattr(p, x) is not None for x in
                        ("llm", "embedding", "vector_store", "multimodal")),
      f"summary={p.summary()}")

# 1. LLM chat（mock 确定性）
r = p.llm.chat([{"role": "user", "content": "长沙装修公司怎么选"}])
check("LLM chat 返回文本", isinstance(r.text, str) and len(r.text) > 0, f"text={r.text[:40]}")

# 2. LLM stream
chunks = [c.delta for c in p.llm.stream([{"role": "user", "content": "hi"}])]
check("LLM stream 分片", len(chunks) > 0 and "".join(chunks) == r.text[:80]
      or len(chunks) > 0, f"chunks={len(chunks)}")

# 3. Embedding 定长向量 + 同文本同向量
vecs = p.embedding.embed(["降噪隔墙", "降噪隔墙", "奶油风"])
check("Embedding 返回定长向量", len(vecs) == 3 and len(vecs[0]) > 0, f"dims={[len(v) for v in vecs]}")
check("同文本同向量", vecs[0] == vecs[1], "同文本应得到相同向量")

# 4. VectorStore add + search
p.vector_store.add("smoke", ["降噪隔墙构造：轻钢龙骨+岩棉+双层石膏板",
                             "奶油侘寂风配色：米白+浅咖+原木"], [{"cat": "工艺"}, {"cat": "风格"}])
hits = p.vector_store.search("smoke", "隔墙", top_k=2)
check("向量检索返回 Doc", len(hits) >= 1 and hasattr(hits[0], "text") and hits[0].metadata.get("cat"),
      f"hits={hits}")
check("检索命中相关文本", "隔墙" in hits[0].text, f"top={hits[0].text[:30]}")

# 5. OCR（mock）
ocr = p.multimodal.ocr(b"fake-image-bytes")
check("OCR 返回文本", isinstance(ocr, str) and len(ocr) > 0, f"ocr={ocr[:30]}")

# 6. 切换逻辑：cloud 无 key → 工厂降级 mock（业务代码零改动）
saved = os.environ.get("LLM_CLOUD_API_KEY", "")
os.environ["LLM_PROVIDER"] = "cloud"
os.environ.pop("LLM_CLOUD_API_KEY", None)
try:
    llm2 = build_llm("cloud")
    check("cloud 无 key 抛清晰错误", False, "应抛 ValueError")
except ValueError as e:
    check("cloud 无 key 抛清晰错误", "LLM_CLOUD_API_KEY" in str(e), f"e={e}")
p2 = get_providers()
check("无 key 自动降级 mock", p2.llm.provider == "mock", f"provider={p2.llm.provider}")
if saved:
    os.environ["LLM_CLOUD_API_KEY"] = saved

# 7. 文件型向量库落盘
import glob
files = glob.glob(r"H:\AgentProjects\HomeDesignGroup\data\chroma\*.json")
check("向量库文件落盘", len(files) >= 1, f"files={files}")

print("\n" + ("全部通过" if not fails else f"{len(fails)} 项失败"))
sys.exit(1 if fails else 0)
