class MemoryManager:
    def __init__(self):
        self.store = {}

    def get_history(self, cid: str):
        return self.store.get(cid, [])

    def save_msg(self, cid: str, role: str, content: str):
        if cid not in self.store:
            self.store[cid] = []
        self.store[cid].append({"role": role, "content": content})

    def clear_history(self, cid: str):
        if cid in self.store:
            del self.store[cid]

    def load_l2(self, cid, limit: int = 10):
        """读取客户 L2 对话记忆（最近 limit 条）。
        cid 支持单客户 ID 或 ID 列表（列表时合并返回，按顺序取最近 limit 条）。"""
        if isinstance(cid, (list, tuple, set)):
            out = []
            for c in cid:
                out.extend(self.store.get(str(c), []))
            return out[-limit:] if limit else out
        hist = self.store.get(str(cid), [])
        return hist[-limit:] if limit else hist
