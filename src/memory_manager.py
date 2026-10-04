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
