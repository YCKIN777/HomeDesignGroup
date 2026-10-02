# -*- coding: utf-8 -*-
"""base.py — Agent 基类：统一 name/role/capabilities/todo 协议"""


class BaseAgent:
    name = "base"
    role = ""
    capabilities = []

    def todo(self, step: str):
        """骨架占位：返回"该 Agent 在哪个 Step 实现"（Step 自检协议：有则跳过，无则实现）"""
        return {"agent": self.name, "role": self.role, "todo": step, "implemented": False}

    def handle(self, ctx, message: str):
        """子类实现：处理一条消息/任务，返回结构化结果"""
        raise NotImplementedError(f"{self.name} 未实现 handle")
