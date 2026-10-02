# Agent 协作协议 v1（双产品线）

> 版本：v1（2026-10-01） · 适用范围：获客签单线（壹城精工）+ 业主监理线（契约 v0.1）
> 一句话本质：**Agent 之间不点对点调用，靠"指令/工具注册表 + 数据库表 + 状态约束 + 审批闸门"四件套松耦合协作——表结构就是 Agent 之间的语义契约。**

---

## 1. 协作本质

平台内所有 Agent（无论哪条产品线）遵循同一协作范式：

```
Agent A ──(写表/发指令)──▶ 共享数据层/总线 ──(读表/接指令)──▶ Agent B
                                │
                    权限(roles) + 闸门(Sentinel) + 审计(audit_log)
```

- Agent 之间**没有直接代码调用**，不存在"A import B"的依赖。
- 一个 Agent 的输出以**结构化数据**落入数据库或消息总线；下一个 Agent 从同一处读取。
- 谁可以写、能不能对外执行，由**roles 权限矩阵 + Sentinel 闸门**统一裁决，Agent 自身不做授权判断。
- 一切写操作经 **actions.py 动作注册表**统一记账（审计可追溯）。

## 2. 协议四件套

| 件 | 作用 | 实现 |
| --- | --- | --- |
| ① 指令/工具协议 | Agent 之间的"消息格式" | 获客线：`bus.py` 指令集；契约线：`planner.py` 目标模板 + `ToolRegistry` |
| ② 数据协议 | Agent 之间的"共同语言"（表即契约） | SQLite 表结构（壹城精工.db / homeagent.db） |
| ③ 状态约束 | 什么流转合法、什么非法 | `company_profiles/*/workflow` 配置 + `actions.guard` |
| ④ 审批闸门 | 对外动作默认人工 | `sentinel.py` 5 规则 + `roles.py` 权限 + M3a 收件箱 |

---

## 3. 获客签单线协议（壹城精工 · 消息总线驱动）

### 3.1 指令协议：Bus 总线

`src/kernel/bus.py` — `Bus` 类：

| 方法 | 职责 |
| --- | --- |
| `register(command, handler)` | 注册一条指令（如 `/lead add`）及其处理器 |
| `register_defaults()` | 装载内置指令集（建档/评分/审批/派单/暂停/恢复等） |
| `route(text, ctx)` | 入口：把用户/AI 的文本指令路由到对应 handler |
| `commands()` | 列出当前可用指令（供工作台/帮助使用） |

协作方式：Agent 或人**只发指令文本**，总线负责路由；指令 handler 内部写库。新增 Agent 只需 `register` 新指令，不修改其他 Agent。

### 3.2 数据协议：壹城精工.db 表链

`src/db.py` 统一连接（`get_conn()`），8 张表构成流水线数据链：

```
customers(线索建档) → todos(SOP/派单待办) → messages(草稿/发送) → projects(派单建项目)
      ↘ scores / invites / sedimentation_items / audit_log
```

协作规则：**上一 Agent 写表、下一 Agent 读表**；表字段就是双方约定的接口（如派单 Agent 读 `customers.estate/layout/area/budget_range` 生成 `projects`）。

### 3.3 状态约束：workflow 配置 + guard

- 客户状态迁移（新线索→已建档→已派单→…）的合法边定义在 `company_profiles/壹城精工/workflow/`（公司配置，可定制）。
- `actions.py` 注册动作的 `guard` 声明前置条件（如 `dispatch`：客户存在且未派单，防重复）。
- 非法迁移被拦截（HTTP 409/403），并落审计。

### 3.4 审批闸门：M3a 收件箱（人审后发）

- `draft`：AI 起草待发消息 → messages 表 `status=draft`
- `approve`：人工在收件箱点"通过" → draft→sent（触发外呼/发送）；`reject` → draft→rejected
- 防止重复审批：消息已处理再审批返回 409。

---

## 4. 契约线协议（业主监理线 · Planner 驱动）

### 4.1 编排协议：Planner 目标模板

`src/kernel/planner.py` — 目标类型 → 步骤链 → 逐工具调度：

| 目标 | 步骤链 |
| --- | --- |
| 工艺问答 | craft_search → material_search → answer_draft |
| 报价单 | owner_get → material_search → quote_draft |
| 工地日报 | site_ocr → report_draft |

与总线的关系：**bus 面向指令（用户说一句话触发一个动作），Planner 面向任务目标（一个目标拆多个步骤自动编排）**。两者共用 ToolRegistry 工具，不冲突。

### 4.2 工具协议：ToolRegistry

- `register(name, fn, description, sentinel_type)` 注册工具。
- `call(name, user, **kwargs)` 统一调度：**先过 Sentinel 评估，再执行**。
- 工具是 Agent 能力的原子单元；Agent 通过 Planner 串联工具，不直接调函数。

### 4.3 审批闸门：Sentinel 5 规则（strict）

| 动作类型 | 策略 | 含义 |
| --- | --- | --- |
| read / draft | allow | 查资料、生成草稿自动放行（draft 记审计） |
| external_send | pending | 发消息给业主/工长 → 草稿进 pending_human，人工点发送 |
| payment | deny | 下单/付款拒绝自动，仅订单摘要给人工确认 |
| owner_edit | confirm | 改业主预算/户型 → 二次确认 |
| third_party_api | audit | 第三方 API 非只读调用 → 记审计 |

`SENTINEL_MODE=strict`（生产默认）；`auto` 仅调试；`SENTINEL_AUTO_ALLOWED` 白名单。

### 4.4 数据协议：homeagent.db 三张核心表

```
owners(业主档案) + craft_knowledge(工艺知识) + materials(建材库)
```

- 三个 MVP Agent（craft_qa / quote / site_report）共享这三张表。
- 检索策略：**向量优先 → SQL 回退**（数据后填即可生效，无需改代码）。

---

## 5. 共用内核（两条线都依赖）

| 内核件 | 位置 | 职责 |
| --- | --- | --- |
| Provider 抽象层 | `src/providers/` | LLM/Embedding/向量库/OCR 双后端，切本地零改业务代码 |
| 四层记忆 | `memory_manager.py` | L1-L4（即时/短/长/文本），本体驱动，检索带来源 |
| 权限矩阵 | `kernel/roles.py` | 写操作按角色（客服/销售/主管/董事长/设计总监/…），读开放 |
| 动作注册表 | `kernel/actions.py` | 所有写操作声明 权限/前置/副作用/审计，统一记账 |
| MCP 出口 | `mcp_server.py` | /mcp JSON-RPC，外部系统可调平台能力 |
| 审计 | `db.audit()` | 谁/何时/改了什么/前后值，全追溯 |
| 沉淀中心 | `sedimentation/` | 优质数据提炼→物化→评审入内核 |

---

## 6. 数据与语义隔离

| 维度 | 获客线 | 契约线 |
| --- | --- | --- |
| 数据库 | `db/壹城精工.db`（每公司一库） | `db/homeagent.db`（契约独立库） |
| 表结构 | 8 张（customers/todos/messages/projects/…） | 3 张（owners/craft_knowledge/materials） |
| 语义定义 | 壹城配置包（manifest/terms/rules/workflow） | 契约本体（docs/00-领域本体） |
| 共享 | 共用内核（Provider/记忆/权限/审计），**数据不跨公司共享** | 同左 |

规则：公司数据隔离（每公司一库）；语义/内核共享（一套通用架构）；定制只改配置包与本体语义，不动内核。

---

## 7. 新增一个 Agent 的黄金法则

1. **加一张表**（或复用现有表）：定义它与外界的"数据契约"字段。
2. **加一组动作**：`actions.py` 里 `_register`，声明 权限/前置/副作用/审计。
3. **加一条闸门规则**（若它对外做事）：`sentinel.py` RULES 里加动作类型与策略。
4. **注册指令或工具**：获客线 `bus.register(command, handler)`；契约线 `ToolRegistry.register(name, fn, sentinel_type)`。
5. **不动其他 Agent**：不 import 别的 Agent，不修改别的表结构。

---

## 8. 协议速查表

| 你要做什么 | 用哪个协议 | 入口 |
| --- | --- | --- |
| 录一条线索 | 指令协议 | `Bus.route("/lead add 手机号 …")` |
| AI 起草给业主的消息 | 指令+闸门 | `draft` 动作 → 收件箱人工 approve |
| 客户状态迁移 | 状态约束 | `transition` 动作（workflow 合法边内） |
| 给业主出报价单 | Planner+工具 | `Planner.run("报价单", …)` |
| 发工地日报 | 闸门 | `report_draft` → `external_send` pending |
| 查工艺做法 | 数据协议 | `craft_qa.search_craft(q)`（向量→SQL） |
| 调用第三方 API | 闸门 | `third_party_api`（强制审计） |
| 外部系统调平台 | MCP | `POST /mcp` JSON-RPC |

## 9. 验证清单（每次改协议后跑）

```powershell
python scripts/verify_phase2.py      # 获客线 M1-M4
python scripts/verify_phase34.py     # 获客线 M5-M9+沉淀
python scripts/verify_providers.py   # Provider 抽象 10/10
python scripts/verify_core_tables.py # 三表 9/9
python scripts/verify_sentinel.py    # Sentinel 13/13
python scripts/verify_planner.py     # Planner 7/7
python scripts/demo_agents.py        # 三 Agent 10/10
python scripts/verify_agents_http.py # HTTP 3/3
```
