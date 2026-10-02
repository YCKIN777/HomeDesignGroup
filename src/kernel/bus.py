# -*- coding: utf-8 -*-
"""
bus.py — 消息总线 + 指令集（Step 1.3）
设计对齐《整体技术框架v1》：中控 main.py 复用；指令路由到子 Agent/处理器。
指令集（与原型 /pause /resume /reject 对齐，新增 /approve /dispatch）：
  /pause   <customer_id>   暂停该客户处理（AI 不再自动动作）
  /resume  <customer_id>   恢复处理
  /reject  <message_id>    驳回 AI 起草（人审后发）
  /approve <message_id>    审批通过并发送（人审后发）
  /dispatch <customer_id> [designer]  派单给设计师，建项目
  /help                    指令说明
用法：
  from kernel.bus import Bus
  bus = Bus()
  bus.register("approve", my_handler)
  reply = bus.route("/approve 12", ctx)
"""
import re


class Bus:
    """注册式消息总线：/cmd arg1 arg2 -> 处理器(ctx, *args)"""

    COMMANDS = {
        "pause": "暂停某客户处理: /pause <customer_id>",
        "resume": "恢复某客户处理: /resume <customer_id>",
        "reject": "驳回 AI 起草: /reject <message_id>",
        "approve": "审批通过并发送: /approve <message_id>",
        "dispatch": "派单建项目: /dispatch <customer_id> [设计师]",
        "help": "显示指令说明: /help",
    }

    def __init__(self):
        self._handlers = {}   # command -> fn(ctx, *args)
        self._paused = set()  # 暂停处理的 customer_id 集合

    # ---- 注册与路由 ----
    def register(self, command: str, handler):
        """注册指令处理器；同指令重复注册覆盖（幂等）"""
        command = command.lower().lstrip("/")
        self._handlers[command] = handler

    def register_defaults(self):
        """注册内置默认处理器（占位实现，业务逻辑由后续步骤/Agent 覆盖）"""
        self.register("pause", self._do_pause)
        self.register("resume", self._do_resume)
        self.register("reject", self._do_reject)
        self.register("approve", self._do_approve)
        self.register("dispatch", self._do_dispatch)
        self.register("help", self._do_help)

    def route(self, text: str, ctx=None) -> str:
        """解析并路由一条指令/消息；返回回复文本"""
        text = (text or "").strip()
        if not text:
            return "[bus] 空消息"
        m = re.match(r"^/(\w+)\s*(.*)$", text, re.S)
        if not m:
            return self._route_plain(text, ctx)  # 非指令消息
        cmd, args = m.group(1).lower(), m.group(2).strip()
        if cmd not in self._handlers:
            return f"[bus] 未知指令 /{cmd}，可用: /help"
        return self._handlers[cmd](ctx, *self._split(args))

    def _route_plain(self, text: str, ctx=None) -> str:
        """普通消息：交给默认处理器（后续步骤接 Agent）"""
        if "default" in self._handlers:
            return self._handlers["default"](ctx, text)
        return f"[bus] 收到普通消息(未注册默认处理器): {text[:50]}"

    @staticmethod
    def _split(args: str) -> list:
        return [a for a in args.split() if a]

    # ---- 内置默认处理器（占位，返回状态；后续接数据库/Agent）----
    def _do_pause(self, ctx, customer_id):
        if not customer_id:
            return "[pause] 用法: /pause <customer_id>"
        self._paused.add(int(customer_id))
        return f"[pause] 客户 {customer_id} 已暂停处理"

    def _do_resume(self, ctx, customer_id):
        if not customer_id:
            return "[resume] 用法: /resume <customer_id>"
        self._paused.discard(int(customer_id))
        return f"[resume] 客户 {customer_id} 已恢复处理"

    def _do_reject(self, ctx, message_id):
        if not message_id:
            return "[reject] 用法: /reject <message_id>"
        return f"[reject] 消息 {message_id} 已驳回（待接入 audit_log）"

    def _do_approve(self, ctx, message_id):
        if not message_id:
            return "[approve] 用法: /approve <message_id>"
        return f"[approve] 消息 {message_id} 已审批并发送（待接入 audit_log）"

    def _do_dispatch(self, ctx, customer_id, designer=None):
        if not customer_id:
            return "[dispatch] 用法: /dispatch <customer_id> [设计师]"
        d = designer or "待分配"
        return f"[dispatch] 客户 {customer_id} 派单给 {d}（待接入 projects 表）"

    def _do_help(self, ctx, *args):
        lines = ["[bus] 指令集:"]
        lines += [f"  /{k}  {v}" for k, v in self.COMMANDS.items()]
        return "\n".join(lines)

    # ---- 供上层查询 ----
    def is_paused(self, customer_id) -> bool:
        return customer_id in self._paused

    def commands(self) -> list:
        return list(self.COMMANDS.keys())
