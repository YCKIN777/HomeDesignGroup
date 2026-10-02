# -*- coding: utf-8 -*-
"""验证速查表检索命中（临时）"""
import json
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8000"
for q in ("140平 全包 多少钱", "全包 每平米 造价", "按面积 套算"):
    url = BASE + "/api/kb/search?q=" + urllib.parse.quote(q) + "&top_k=5"
    d = json.loads(urllib.request.urlopen(url, timeout=5).read().decode())
    titles = [h["title"] for h in d["hits"]]
    print(f"[{q}] ->", titles)
