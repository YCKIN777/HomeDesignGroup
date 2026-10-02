# 记忆架构 v2 · Otter 模式解读与结合

> 状态：v2｜更新：2026-09-30｜存放：HomeDesignGroup/docs/05-开发架构/
> 背景：用户确认"Otonage"指 **Otter** 的记忆模式。本文件罗列 Otter 的记忆架构、新开窗口读取模式，并映射到四层记忆。

---

## 1. Otter 是什么（两个同名对象，都相关）

### 1.1 Otter.ai —— 会议知识引擎（产品形态）
来源：otter.ai 官方文档/博客

核心定位：把"对话"变成企业知识。架构要点：
- **每次会议**：录音→实时转写→摘要/行动项/决策/洞察（结构化记录，带发言人+时间戳归属）
- **AI Chat 会话**：每个会话**私有的、维持自己的上下文**；可随时开新会话或回到旧会话继续
- **跨会话检索**：问一个问题，跨全部会议/频道/文件夹检索，答案**标注来源**（哪场会议、谁说的）
- **上下文机制**：`@ Add context` 手动附加某会议/频道/文件夹作为上下文；AI Chat 自动理解你正在看的内容（"Contextual answers"）
- **知识图谱**：纵向知识图谱——随时间持续增长的对话记录，把决策↔决策人↔上下文↔工作流连起来
- **外部连接**：Gmail/Drive/Jira/Salesforce 实时拉取；MCP Server 让 ChatGPT/Claude 等外部 AI 按需访问会议知识
- **组织方式**：按客户/机会/主题的 Conversation Channels（会话频道）

### 1.2 OtterBot —— 开源 Agent 记忆框架（工程形态）
来源：https://otterbot.ai/docs/architecture/

架构要点：
- **每个 Agent 一个独立运行时 + 独立数据库** `data/profiles/<id>/agent.db`：conversations（对话）、messages（消息）、memories（记忆）、skills（技能）、vectors（向量嵌入，sqlite-vec）
- **profile 目录**：profile.json（身份/角色/模型引用）+ **SOUL.md（人设 = 系统提示身份块，每次必载）** + skills/（markdown 技能包，载入提示词）+ agent.db
- **memory 模块**：summarize（总结）、extract（抽取）、store（存储）、search（检索）——四件事
- **control.db（共享控制面）**：agent 注册表、Agent 间消息总线日志、子任务记录、定时任务、加密密钥
- **隔离**：每 Agent 库物理隔离，不同 Agent 可用不同 embedding 模型；全库加密（OTTERBOT_DB_KEY）
- **技术栈**：Fastify + Socket.IO + Vercel AI SDK（模型统一接口，可接 Ollama/Anthropic/OpenAI）+ Drizzle + SQLite/sqlite-vec + croner

## 2. Otter 记忆架构（合并要点）

| 部件 | Otter.ai | OtterBot | 本质 |
| --- | --- | --- | --- |
| 身份/人设 | 组织知识图谱 | SOUL.md + profile.json | **始终在上下文里的"你是谁"** |
| 会话上下文 | AI Chat 会话（每会话私有+续接） | agent.db 的 conversations/messages | **会话内记忆（L1/L2）** |
| 结构化记录 | 摘要/决策/行动项，带发言人归属 | memories（抽取的事实与观察） | **提炼后的长记忆（L3）** |
| 可检索语料 | 全部会议转写+频道+文件夹 | vectors（sqlite-vec 向量检索） | **按需检索（L3+L4）** |
| 外部知识 | Gmail/Drive/Jira/Salesforce + MCP | skills/ 技能包 | **工具与外部接入** |
| 来源标注 | 答案显示来源会议/发言人 | 记忆条目带归属 | **可追溯（审计）** |

**一句话：Otter 记忆 = "身份必载 + 会话内上下文 + 结构化提炼 + 按需检索（不全部塞进上下文）+ 来源可追溯"。**

## 3. 新开窗口（新会话）的读取模式（用户核心问题）

罗列 Otter 的行为模式，映射到家装 Agent：

| 步骤 | Otter 做法 | 家装 Agent 对应 |
| --- | --- | --- |
| ① 身份必载 | SOUL.md/人设 + 组织上下文 | 公司配置包语义（术语/规则/扩展）+ 角色 prompt，**每次新窗口必载，不占大 token** |
| ② 当前对象上下文 | 打开某会议/频道时自动带出 | 打开某客户详情：自动加载该客户的**短记忆**（近期对话/跟进/审批） |
| ③ 会话内上下文 | 本会话问答历史保持 | 本会话对话历史保持（sessions 表） |
| ④ 按需检索 | 问问题时跨语料 RAG，只取相关 | 问问题时检索**长记忆**（画像/沉淀/知识库）+ **文本记忆**（memory 文件），top-k 命中 |
| ⑤ 上下文手动附加 | `@ Add context` 选会议/频道/文件夹 | 手动指定范围（如只看某渠道、某楼盘、某项目） |
| ⑥ 来源标注 | 答案附来源 | 答案附来源（哪条记录/哪个记忆文件）——对齐审计 |
| ⑦ 不加载什么 | 不把全部历史塞进提示词 | 不把全部 L3/L4 塞进上下文（防 token 爆炸与噪音） |

**核心结论：新开窗口 ≠ 失忆。新窗口 = 身份（必载）+ 当前对象的近期记忆（自动）+ 其余全部"按需检索"（问到了才取，带来源）。**

## 4. 映射到四层记忆（v1 → v2 结合）

| 四层 | Otter 对应 | 变更 |
| --- | --- | --- |
| L1 即时 | AI Chat 会话上下文 | 不变（会话内） |
| L2 短 | 当前对象自动带出的近期记录 | 不变（打开客户自动加载） |
| L3 长（本体驱动） | 知识图谱 + memories + vectors | **新增"按需检索"机制**：Agent 提问→RAG 检索 L3，只取 top-k，带来源 |
| L4 文本 | 转写/摘要/洞察（Otter 的"语料"） | **对齐 Otter：记忆文件即检索语料**，可被 RAG 检索，答案标注文件来源 |

## 5. 落地变更（相对记忆架构 v1）

1. **新增 memory_retrieval.py**：按需检索器（关键词+向量双通道，先关键词后向量），替代"全量加载"
2. **新增 sessions 表**：会话级上下文（L1），支持"重开旧会话续接"（对齐 Otter AI Chat）
3. **读取顺序规则**（写进 memory_manager）：
   - 新窗口必载：身份（配置包语义+角色）
   - 打开客户：自动载该客户 L2
   - 提问时：RAG 检索 L3+L4（top-k，带来源）
   - 会话内：保持本会话上下文
4. **来源标注**：Agent 回答带来源引用（记录 ID / 记忆文件路径），进 audit_log
5. **隔离对齐**：OtterBot 每 Agent 独立 agent.db → 我们每公司独立 db 文件 + 独立 memory 目录（已在架构中）

## 6. 来源清单

- Otter.ai AI Chat Overview：https://help.otter.ai/hc/en-us/articles/19682180167575-Otter-AI-Chat-Overview
- Otter.ai 知识引擎博客：https://otter.ai/blog/otter-ai-evolves-from-ai-notetaker-to-create-100b-enterprise-conversational-knowledge-engine-market
- Otter.ai Agentic Workflows for Sales：https://otter.ai/blog/agentic-ai-workflows-for-sales
- OtterBot 架构文档：https://otterbot.ai/docs/architecture/
- Otter.ai AI Chat Review（跨会议检索）：https://work-management.org/productivity-tools/otter-ai-review/
