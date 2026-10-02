# -*- coding: utf-8 -*-
"""验证新报价知识文件可检索命中（临时）"""
import json
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8000"
for q in ("门槛石 单价", "兔宝宝 柜体", "防水涂料 单价", "远程费"):
    url = BASE + "/api/kb/search?q=" + urllib.parse.quote(q) + "&top_k=3"
    d = json.loads(urllib.request.urlopen(url, timeout=5).read().decode())
    hit_new = [h for h in d["hits"] if "壹城估算书" in h["title"]]
    print(f"[{q}] ->", len(d["hits"]), "hits; 新文件命中:", [h["title"] for h in hit_new] or "未命中")
    for h in d["hits"][:1]:
        print("   首条:", h["title"], "|", h["source"])
