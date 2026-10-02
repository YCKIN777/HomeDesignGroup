# -*- coding: utf-8 -*-
"""planner.py — Planner + Tool dispatch 骨架（架构契约 Step 5）

- ToolRegistry：统一注册 {name: Tool}，调用经 Sentinel 闸门（原则 3）
- Planner：目标类型 → 步骤模板 → 逐步 dispatch；每步结果可追溯
- 与现有 bus.py 共存：bus 面向指令（/lead add），Planner 面向任务目标（"给业主出报价单"）
- 规划当前为规则化模板（确定性、可测试）；未来接 LLM 规划为扩展点（接口不变）
"""
from kernel.sentinel import DRAFT, READ, SentinelDecision, evaluate


class Tool:
    def __init__(self, name: str, fn, description: str = "",
                 sentinel_type: str = READ):
        self.name = name
        self.fn = fn
        self.description = description
        self.sentinel_type = sentinel_type


class ToolRegistry:
    def __init__(self):
        self.tools = {}

    def register(self, name: str, fn, description: str = "",
                 sentinel_type: str = READ) -> "ToolRegistry":
        self.tools[name] = Tool(name, fn, description, sentinel_type)
        return self

    def list(self) -> list:
        return [{"name": t.name, "description": t.description,
                 "sentinel_type": t.sentinel_type} for t in self.tools.values()]

    def call(self, name: str, user: str = "system", **kwargs):
        """调度入口：先过 Sentinel，再执行；返回 (决策, 结果)"""
        tool = self.tools.get(name)
        if tool is None:
            raise KeyError(f"未注册工具: {name}")
        decision = evaluate(tool.sentinel_type)
        if not decision.allowed:
            raise PermissionError(
                f"Sentinel 拒绝工具 {name}（{decision.reason}），需人工确认")
        return decision, tool.fn(user=user, **kwargs)


class Planner:
    """规则化 Planner：目标类型 → 步骤模板 → 逐步 dispatch"""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def plan(self, goal_type: str) -> list:
        """返回步骤模板（工具名 + 参数来源说明）"""
        templates = {
            "工艺问答": [
                {"tool": "craft_search", "desc": "查工艺知识库（RAG 语料）"},
                {"tool": "material_search", "desc": "拉建材参考价"},
                {"tool": "answer_draft", "desc": "生成结构化答案（工艺+材料+参考价，草稿）"},
            ],
            "报价单": [
                {"tool": "owner_get", "desc": "查业主档案（户型/预算）"},
                {"tool": "material_search", "desc": "拉建材清单（materials 库）"},
                {"tool": "quote_draft", "desc": "生成 Excel 清单草稿（项目/规格/单位/数量/单价/合价/备注）"},
            ],
            "工地日报": [
                {"tool": "site_ocr", "desc": "现场照片 OCR（识别进度/部位）"},
                {"tool": "report_draft", "desc": "生成当日进度简报草稿（pending_human）"},
            ],
        }
        if goal_type not in templates:
            raise KeyError(f"未知目标类型: {goal_type}（可选 {list(templates)}）")
        return templates[goal_type]

    def run(self, goal_type: str, user: str = "system", context: dict = None) -> dict:
        """按步骤模板逐步执行，返回结果链（每步：工具/决策/结果）"""
        context = context or {}
        steps = self.plan(goal_type)
        chain = []
        for i, step in enumerate(steps, 1):
            decision, result = self.registry.call(step["tool"], user=user,
                                                  **context.get(step["tool"], {}))
            chain.append({"step": i, "tool": step["tool"], "desc": step["desc"],
                          "decision": decision.reason, "result": result})
        return {"goal": goal_type, "steps": len(chain), "chain": chain}
