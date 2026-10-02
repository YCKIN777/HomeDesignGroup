# MCP 出口对接说明（v1）

> 状态：v1｜更新：2026-10-01｜实现：`src/mcp_server.py` + `POST /mcp`（Step 4.8）
> 用途：让外部 Agent（豆包/Claude/Cursor/自建工作流）以统一协议调用平台能力；
> 权限经动作注册表校验，与 Web 工作台完全一致。
> 前置：平台已启动（`start_platform.ps1` → http://127.0.0.1:8000）。

## 1. 协议与端点

| 项 | 值 |
| --- | --- |
| 传输 | HTTP JSON-RPC 2.0（POST，非 SSE） |
| 端点 | `http://127.0.0.1:8000/mcp` |
| 请求头 | `Content-Type: application/json`；`X-Agent-User: <账号>`（身份来源） |
| 协议版本 | `2025-03-26` |
| 方法 | `initialize` / `notifications/initialized` / `tools/list` / `tools/call` |

调用顺序（标准握手）：

1. `initialize`（携带 protocolVersion）
2. `notifications/initialized`（通知，无响应）
3. `tools/list`（拿工具清单与 inputSchema）
4. `tools/call`（调工具，参数放 `arguments`）

## 2. 工具清单（10 个）

| 工具 | 说明 | 必需动作 | 谁能调 |
| --- | --- | --- | --- |
| `leads_search` | 查客户线索（状态/关键词） | — | 任意登录账号 |
| `leads_create` | 录入线索（按手机号去重） | `lead.write` | 客服/销售/主管 |
| `lead_score` | 意向评分 0-100 | `score` | 客服/销售/主管 |
| `inbox_draft` | AI 起草待发消息（人审后发） | `draft` | 客服/销售/主管 |
| `kb_search` | 谈单知识库检索（带来源） | — | 任意登录账号 |
| `stats_overview` | 经营指标概览 | — | 任意登录账号 |
| `config_view` | 当前公司配置包摘要 | — | 任意登录账号 |
| `memory_append` | 写 L4 文本记忆（本体 frontmatter） | `memory.write` | 客服/销售/主管 |
| `sop_run` | 手动触发 SOP 扫描 | `webhook.ingest` | 仅内部/渠道账号 |
| `action_help` | 查某账号可执行动作清单 | — | 任意登录账号 |

- 读工具：`required_action=None`，任意已登录账号可调。
- 写工具：调用时以 `arguments.user`（缺省取 `X-Agent-User`）经动作注册表校验，
  无权限返回 JSON-RPC 错误 `-32001`。
- `sop_run` 为机器入口，仅 `system:` / `渠道:` 前缀内部账号放行（人审后发不受影响）。

## 3. 调用示例

### 3.1 curl（Windows PowerShell 兼容）

```powershell
# 握手
curl.exe -s -X POST http://127.0.0.1:8000/mcp -H "Content-Type: application/json" `
  -H "X-Agent-User: admin" --data-raw '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26"}}'

# 工具清单
curl.exe -s -X POST http://127.0.0.1:8000/mcp -H "Content-Type: application/json" `
  -H "X-Agent-User: admin" --data-raw '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'

# 调用：检索知识库
curl.exe -s -X POST http://127.0.0.1:8000/mcp -H "Content-Type: application/json" `
  -H "X-Agent-User: admin" --data-raw '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"kb_search","arguments":{"query":"防水 质保","top_k":3}}}'

# 调用：起草消息（写工具，需客服/销售权限）
curl.exe -s -X POST http://127.0.0.1:8000/mcp -H "Content-Type: application/json" `
  -H "X-Agent-User: 客服" --data-raw '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"inbox_draft","arguments":{"user":"客服","customer_id":1,"kind":"first_contact"}}}'
```

### 3.2 Python（urllib，无第三方依赖）

```python
import json, urllib.request

URL = "http://127.0.0.1:8000/mcp"

def mcp(method: str, params: dict = None, user: str = "admin"):
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    req = urllib.request.Request(
        URL, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "X-Agent-User": user})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))

# 标准调用链
mcp("initialize", {"protocolVersion": "2025-03-26"})          # 1 握手
mcp("notifications/initialized")                               # 2 通知（返回 None）
print(mcp("tools/list"))                                       # 3 工具清单
print(mcp("tools/call", {"name": "stats_overview", "arguments": {}}))  # 4 调指标
print(mcp("tools/call", {"name": "memory_append",
                         "arguments": {"concept_id": "concept.channel",
                                       "relation": "derived_from",
                                       "state": "观察",
                                       "content": "小红书线索占比观察（示例）"}},
              user="销售"))                                     # 写工具带权限
```

## 4. 响应与错误约定

成功：`result.content[0].text` 为工具返回的 JSON 字符串（`isError: false`）。
业务失败：`result.isError: true`，文本含原因。
协议错误（JSON-RPC 标准 + 平台扩展）：

| code | 含义 |
| --- | --- |
| -32601 | method not found（未知方法） |
| -32602 | 参数无效（未知工具名等） |
| -32603 | 内部错误 |
| -32001 | 权限不足（写工具未经动作注册表） |

## 5. 对接注意

1. **身份**：写工具优先取 `arguments.user`，其次 `X-Agent-User`，最后 `system`；
   权限判定与 Web 工作台同一套角色矩阵（`src/kernel/roles.py` + `actions.py`）。
2. **人审后发不变**：`inbox_draft` 只起草，发送仍走人工审批（`/approve`），审计全记录。
3. **记忆约束**：`memory_append` 只写 L4 文本记忆（含本体 frontmatter），
   不引入其他记忆方式（总纲约束）。
4. **SSE 适配**：Claude Desktop 等需 SSE 传输，当前为 HTTP 请求-响应模式；
   如需 SSE 传输层列为扩展点（不影响 HTTP 客户端直接调用）。
5. **测试**：`scripts/verify_mcp_http.py` 覆盖握手→清单→调用→权限四段 HTTP 全链路。

## 6. 与动作注册表的联动

- 工具清单（`mcp_server.TOOLS`）的 `required_action` 必须能在
  `src/kernel/actions.py` 注册表找到（`check_action` 校验）。
- 新增平台能力时：先注册动作（actions.py）→ 再挂工具（mcp_server.py）→
  跑 `scripts/check_mcp.py` 函数级 + `verify_mcp_http.py` HTTP 级自检。
