# 家装 AI 平台 · Agent 骨架搭建提示词 v0.1.4

> 创建日期：2026-10-01
> 最近更新：2026-10-01（v0.1.4：交付前自检+失败降级；v0.1.3：渠道适配层；v0.1.2：双档路由；v0.1.1：快照+血泪库）
> 用途：整段复制下面的「启动提示词」，发给你的家装平台 AI 开发助手，让它按 Step 执行。
> 配套文件：本文末尾附 `.env.example`，让开发助手一并落盘。
> 核心原则：**模型调用全部走 Provider 抽象层，未来一行 .env 切到本地部署；业务代码零改动。**

---

## 一、启动提示词（从下一行开始整段复制）

```
# 任务：为我的家装 AI 平台搭建 MVP 后端骨架（v0.1.4）

## 你是谁
你是资深全栈 AI 工程师。我（产品方）已经确定产品方向和架构原则，你负责把骨架搭出来。不要自由发挥产品方向，只在技术实现上做选择。

## 产品背景
- 这是一个面向长沙家装/房屋托管/装修监理场景的 AI Agent 平台
- C 端是业主（H5 网页/微信里打开链接使用），B 端是监理和管家（企业微信机器人）
- 核心动作：答疑、工地进度推送、报价单生成、建材比价、工艺问答、验收报告
- 当前阶段：MVP，目标 4 周内跑通前 3 个真实业主试点

## 八条不可妥协的设计原则（违反任何一条都要停下问我）

### 原则 1：所有模型调用必须走 Provider 抽象层（核心！）
未来我要从云端模型切到本地部署（Ollama/vLLM），切换时不能改业务代码。
你必须实现以下抽象，业务代码只调这些接口，绝不直接 import openai / anthropic / zhipu 等 SDK：

- LLMProvider.chat(messages, tools=None, temperature) -> ChatResult
- LLMProvider.stream(...) -> Iterator[Chunk]
- EmbeddingProvider.embed(texts: list[str]) -> list[list[float]]
- VectorStore.add(collection, docs, metadatas)
- VectorStore.search(collection, query, top_k) -> list[Doc]
- MultimodalProvider.ocr(image_bytes) -> str（户型图识别用）

实现要求：
- 每个 Provider 至少提供两个后端实现：一个云端（OpenAI 兼容协议，可接豆包/DeepSeek/智谱任意一家），一个本地（Ollama）
- 通过 .env 里一行 LLM_PROVIDER=cloud|local 切换，业务代码零改动
- 推荐用 litellm 做 LLM 抽象，省得自己造轮子；向量库先用 Chroma（文件型，未来迁 Qdrant 不改业务代码）

### 原则 2：数据从 Day 1 结构化入库，不写死在 prompt
以下三张表必须建好 schema，所有内容通过 API 读写，禁止硬编码在系统 prompt 里：

1. owners（业主档案 / Library）：
   - id, wechat_id, nickname, community, house_area, layout_json（户型尺寸）, budget_total, budget_used, style_preference（奶油侘寂/暗黑侘寂/叙利亚/新中式等 tag）, created_at, updated_at
2. craft_knowledge（工艺知识库，RAG 语料）：
   - id, category（水电/泥木/油漆/降噪隔墙等）, title, content, source_file, embedding_id
3. materials（建材供应链库）：
   - id, category（岩板/石英石/软装等）, name, spec（如 1200×2700mm）, supplier, price, moq, tags

### 原则 3：Sentinel 审批闸门（安全红线，必须实现为中间件）
所有 Agent 想"对外做事"的动作，在执行前必须过 Sentinel。规则写死：

| 动作类型 | 默认策略 |
|---|---|
| 查资料、写草稿、生成报价/报告（不对外） | 自动放行 |
| 发微信消息给业主/工长 | 生成草稿，状态=pending_human，必须人工点"发送" |
| 下单、付款、调用支付接口 | 一律拒绝自动执行，只生成订单摘要给人工确认 |
| 修改 owners 档案里的预算/户型字段 | 必须二次确认 + **修改前自动快照到 backups/，可回滚** |
| 调用第三方 API（非只读） | 必须记录审计日志（谁、什么时候、改了什么、可回滚） |

Sentinel 实现成一个装饰器 / 中间件，所有 tool 函数挂上 @sentinel_check，统一在一个地方改规则。
**全局快照要求**：任何写库操作（UPDATE/DELETE）在落库前，必须把该行旧值序列化存到 `backpoints/YYYY-MM-DD/<table>_<id>.json`，文件名带时间戳，保留 30 天。

### 原则 4：通用内核 + 定制配置双层
- 内核（不改）：Planner、Sub-agent 编排、Sentinel、Provider 抽象、会话状态机
- 配置（按公司灌入）：话术模板、建材价格表、工艺问答数据、收费阶梯（三房 150 / 别墅 368 这类）、长沙本地供应商列表
- 所有行业相关的常量、prompt 片段、价格表，全部放 config/ 目录下的 YAML，不要写死在 Python 里

### 原则 5：血泪教训库（事故复盘沉淀，从 Day 1 建机制）
参考大厂多 Agent 生产治理经验，但不要过度工程。你必须做到：
- 项目里建一个 `docs/lessons/` 目录，每踩一次坑（Sentinel 误拦、报价算错、OCR 识别错户型、业主投诉等），就新建一个 `YYYY-MM-DD-<一句话标题>.md`，写清楚：
  1. 发生了什么
  2. 根因（是哪条 Sentinel 规则没覆盖？是 RAG 检索错了？是 prompt 漏洞？）
  3. 修复动作（改了哪段代码 / 加了哪条规则 / 改了哪个配置）
- 每次开新对话时，开场白要求你先读 `docs/lessons/` 下所有 md，避免重蹈覆辙
- **现在不要做**：死锁检测、全局仲裁、协作链路压测、单集群实例数红线——这些是几十个 Agent 互相调用时才需要的，等真出现 Agent 之间互相干扰的事故再补
- 但要在 Planner 接口里预留 `max_steps` 参数（默认 20，防止 Agent 跑飞循环烧 token），现在就把这个参数位置留好，值可以设得宽松

### 原则 6：双档模型路由（cheap / frontier，省钱是核心）
80% 的业主请求是 FAQ 级别（"岩板多少钱一平"、"降噪隔墙怎么做"、"工期多久"），不该都调云端大模型烧钱。你必须在 Planner 前面加一个 Router：

- **cheap 档**：简单问答、查价、查工艺 → 走本地 Ollama 小模型（qwen2.5:7b 或更小）+ RAG，延迟低、零 token 成本
- **frontier 档**：报价单生成、多步规划、跨表推理、复杂对比 → 走云端大模型（豆包 Pro / DeepSeek）
- **路由判断**：MVP 阶段不要上 LLM judge、不要训分类器，直接用 `config/router.yaml` 写关键词规则（比如命中"多少钱/价格/工期/是什么/怎么做"走 cheap；命中"报价/方案/对比/计划/帮我算"走 frontier）
- **默认档位**：路由规则没命中时，**默认走 frontier**（宁可多花 token 也不要答错简单问题）
- **scope 过滤**：完全不在家装范围内的请求（"帮我写个爬虫"、"翻译这段论文"），Router 直接回"这个我不处理"，不进入后续流程
- **预留但不实现**：置信度低时升级给人工（escalate）这个接口留位置，MVP 阶段不用真做置信度评估
- Router 要记录每个请求最终走了哪一档，写进日志，方便事后看分流比例

### 原则 7：渠道适配层（业务逻辑不感知消息从哪来）
Agent 的核心能力（Router → Sentinel → Sub-agent → 数据层）必须跟"消息入口"解耦。你必须在 `src/channels/` 下做 adapter 层：

- **web_h5.py**：C 端业主入口，FastAPI 直接出一个 `/chat` 页面，微信里点开链接就能用。MVP 阶段就用这个，不做小程序、不做 App
- **wecom.py**：B 端监理/管家入口，接企业微信智能机器人（API 长连接模式），监理在企业微信里 @ 机器人就能查建材、生成日报
- **统一接口**：每个 adapter 做两件事——把外部消息转成统一的 `UserMessage` 对象（含 user_id、channel、text、attachments），把 Agent 输出转成对应渠道的消息格式发出去
- **业务层不允许 import 任何微信/企业微信 SDK**——所有渠道相关的代码只在 `channels/` 目录里
- **现在不要做**：个人微信机器人（封号风险）、微信小程序（审核重）、LightVela skill（生态还没开放开发者入驻）。这些记在 config/roadmap.yaml 里，等条件成熟再做
- 未来要加新渠道（飞书、钉钉、LightVela），只在 `channels/` 下加一个新文件，业务代码一行不改

### 原则 8：交付前自检 + 失败降级（Evaluation + Recovery，克制版）
Agent 生成的东西不能直接甩给用户，必须过两道机器关：

**A. 交付前自检（确定性校验，不用 LLM）**
任何结构化产物（报价单、验收报告、工艺答案）在返回用户前，必须跑一遍硬校验：
- 报价单：每一行 数量×单价=合价 对不对？合计对不对？有没有负数量/负单价？有没有必填字段空着？预算有没有超 owners.budget_total？
- 工艺答案：引用的材料和价格是不是真的在 materials 表里？有没有编造 SKU？
- 校验不过 → Agent 自己修一遍；修不了 → 直接告诉用户"这个我没算对，先不发你"，**不要硬交一个错的结果**
- 校验逻辑写在 `src/validators/` 里，纯 Python 函数，不调 LLM

**B. 失败降级（工具调用失败时）**
- OCR 挂了、查建材 API 超时、向量库搜不到 → 捕获异常，**重试 1 次**，还失败就优雅降级：
  - 告诉用户具体哪步没搞定（"这张图我没看清，麻烦重拍一张清晰点的"）
  - 写一条 lesson 到 docs/lessons/
  - **不要把 Python 堆栈、错误码、英文报错甩给用户看**
- **现在不要做**：LLM-as-judge 打分、自动重试 N 次、复杂熔断链路、自动换模型降级——这些等真出了事故再补

**C. 上下文工程默认规则（防止 context window 被撑爆，必须做）**
这两条是 RAG 和会话管理的默认行为，不是优化项：
- **工具输出截断**：RAG 查回来的工艺文档、建材列表、聊天记录，不要全塞进 prompt。每段工具返回只取 top 5 相关片段，每段正文不超过 500 字，带文档标题和来源。宁可少给，不要撑爆。
- **历史压缩**：同一个业主对话超过 5 轮，就把前面的对话压成一段摘要（"业主：120㎡三房，预算25万，偏好奶油侘寂，已问过降噪隔墙和岩板价格"），后续请求只带摘要 + 最近 3 轮原始消息。摘要由 cheap 档小模型生成，不调 frontier。
- 这两条写在 Provider 抽象层的上下文组装逻辑里，业务层不感知。

## 技术栈建议（可调整，但要满足上面 8 条原则）
- Python 3.11+，FastAPI 出 API
- SQLite 起步（未来迁 Postgres 用 SQLAlchemy ORM 隔离）
- Chroma 做向量库（文件型，未来迁 Qdrant 不改业务代码）
- 任务编排：先别上 LangChain 全家桶，手写一个简单的 Planner + Tool dispatch 就够，避免被框架锁死
- 日志：统一结构化日志，每个 Agent 动作有 trace_id
- 快照：写库前自动备份到 backups/ 目录，用现成 SQLAlchemy event listener 或装饰器实现即可

## MVP 阶段只做这 3 个 Sub-agent（不要多做）
1. 工艺问答 Agent：业主问"降噪隔墙怎么做" -> 查 craft_knowledge 库 -> 出结构化答案（工艺+材料+参考价）
2. 报价单生成 Agent：业主报户型+需求 -> 拉 materials 库 -> 出 Excel 格式清单（列项严格按：项目/规格/单位/数量/单价/合价/备注），不自动发
3. 工地日报 Agent：监理上传现场照片+几句描述 -> OCR + 模板 -> 生成当日进度简报，草稿进 pending

## Step 自检协议（我之前定的，必须遵守）
你按以下顺序交付，每完成一步先检查产物是否已存在、可运行，存在就跳过：
1. 项目目录骨架 + .env.example + README
2. Provider 抽象层（LLM/Embedding/VectorStore 各两个后端实现）+ 一个跑通的 smoke test
3. 三张核心表的 SQLAlchemy model + 迁移脚本
4. Sentinel 中间件 + 6 条规则的单元测试（含"改 owners 前自动快照"那条）
5. Planner + Tool dispatch 骨架（预留 max_steps 参数，默认 20）
6. 三个 MVP Sub-agent 各自跑通一个 demo case
7. 一份"未来切本地部署"的操作手册：告诉我哪几个 .env 变量改一下就能全栈切到 Ollama + 本地 bge-m3 + Chroma
8. 建一个 docs/lessons/ 目录 + 一个 README 说明"以后踩坑怎么记"，并在开场白模板里加上"开新对话先读 lessons/"这一条
9. 最简 Router：按 config/router.yaml 关键词规则分流 cheap/frontier 两档，scope 外请求直接拒；跑一个测试用例证明"降噪隔墙怎么做"走 cheap、"帮我算个 120㎡三房报价"走 frontier
10. 渠道适配层：先做 web_h5.py（一个最简单的 /chat 页面，能在浏览器里对话就算通），wecom.py 留好文件骨架和 TODO，不真接企业微信（等 B 端团队真要用了再接）；业务层不 import 任何渠道 SDK
11. 自检与降级 + 上下文工程：在 src/validators/ 下写一个报价单校验器（合计/必填/负数/预算超支），在所有 Sub-agent 外层包一个 try-except，工具失败重试 1 次后优雅降级；实现工具输出截断（top 5、每段≤500字）和历史压缩（5 轮后摘要 + 最近 3 轮）；跑一个用例证明"报价单算错时会被拦下"

## 不要做的事
- 不要写前端、不要做登录系统、不要接支付通道（接口留位置就行）
- 不要引入你觉得酷但我没要求的框架（DAG 引擎、图数据库、LangGraph 之类先不碰）
- 不要把任何业主数据、价格表、工艺文案写死在代码里
- 不要替我做产品决策（比如"我觉得应该加个 XX 功能"），按上面的清单做

## 交付要求
每完成一个 Step，给我：
1. 改了哪些文件（路径列表）
2. 如何跑起来验证（一条命令）
3. 这一步满足了上面哪条原则

全部 Step 完成后，给我一份 1 页的 README，包含：如何启动、如何切云端/本地、如何加一个新 Sub-agent、如何加一条 Sentinel 规则。
```

---

## 二、配套 `.env.example`（让开发助手一并落盘到项目根目录）

```env
# ==========================================
# 家装 AI 平台 · 环境变量示例
# 复制为 .env 后按实际填写。切云端/本地只改 PROVIDER 这几个开关。
# ==========================================

# ---------- LLM 主模型 ----------
# cloud = 走 OpenAI 兼容协议（豆包/DeepSeek/智谱/通义都兼容）；local = 走本地 Ollama
LLM_PROVIDER=cloud

# 云端 LLM（豆包/DeepSeek/智谱任意一家，base_url 按你选的填）
LLM_CLOUD_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
LLM_CLOUD_API_KEY=your_cloud_api_key_here
LLM_CLOUD_MODEL=doubao-seed-1-6-250615

# 本地 LLM（Ollama）
LLM_LOCAL_BASE_URL=http://localhost:11434
LLM_LOCAL_MODEL=qwen2.5:14b

# ---------- Embedding 模型 ----------
EMBEDDING_PROVIDER=cloud
EMBEDDING_CLOUD_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
EMBEDDING_CLOUD_API_KEY=your_cloud_api_key_here
EMBEDDING_CLOUD_MODEL=doubao-embedding
EMBEDDING_LOCAL_BASE_URL=http://localhost:11434
EMBEDDING_LOCAL_MODEL=bge-m3

# ---------- 向量库 ----------
# chroma_local = 本地文件型；qdrant_remote = 未来上集群时切
VECTOR_STORE=chroma_local
CHROMA_PATH=./data/chroma
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=

# ---------- OCR / 多模态 ----------
OCR_PROVIDER=cloud
OCR_CLOUD_API_KEY=your_ocr_key_here

# ---------- 数据库 ----------
DATABASE_URL=sqlite:///./data/homeagent.db

# ---------- Sentinel 安全闸门 ----------
# strict = 所有对外动作默认人工审批；auto = 放行（仅开发调试用，生产必须 strict）
SENTINEL_MODE=strict
# 哪些动作允许自动执行（逗号分隔），留空=全人工
SENTINEL_AUTO_ALLOWED=
# 写库前自动快照目录，保留 30 天
BACKUP_DIR=./backups
BACKUP_RETENTION_DAYS=30

# ---------- Planner 限流（防 Agent 跑飞） ----------
# 单个任务最多允许 Agent 走多少步，超过自动熔断并报警
MAX_STEPS_PER_TASK=20

# ---------- Router 双档模型路由 ----------
# simple_keyword = 按 config/router.yaml 关键词分流；llm_judge = 让小模型判断（以后再开）
ROUTER_MODE=simple_keyword
# 没命中规则时默认走哪档：frontier（保守，宁多花 token）
ROUTER_DEFAULT_TIER=frontier
# cheap 档用哪套 LLM 配置（指向本地 Ollama）
CHEAP_LLM_PROVIDER=local
# frontier 档用哪套 LLM 配置（指向云端大模型）
FRONTIER_LLM_PROVIDER=cloud
# scope 外请求的拒答话术
ROUTER_OUT_OF_SCOPE_REPLY=抱歉，这个问题不在我的服务范围（家装/装修/监理），建议您咨询相关专业人士。

# ---------- 渠道适配层 ----------
# web_h5 = C 端 H5 入口（MVP 默认开）；wecom = B 端企业微信（先关，需要时再开）
CHANNEL_WEB_H5_ENABLED=true
CHANNEL_WECOM_ENABLED=false
# 企业微信机器人凭据（CHANNEL_WECOM_ENABLED=true 时填）
WECOM_BOT_ID=
WECOM_BOT_SECRET=

# ---------- 日志 ----------
LOG_LEVEL=info
TRACE_SAMPLE_RATE=1.0
```

---

## 三、使用方法

1. 打开你那个家装平台 AI 的对话窗口
2. 把上面「一、启动提示词」代码块里的全部内容整段复制粘贴发过去
3. 再把「二、.env.example」整段发过去，告诉它"按这个内容落盘到项目根目录，不要改变量名"
4. 它会按 8 个 Step 依次交付，每步回报改动文件 + 验证命令 + 对应原则
5. 验收时重点看：Step 2 的 smoke test 能不能在 `LLM_PROVIDER=cloud` 和 `LLM_PROVIDER=local` 之间切换跑通同一段对话
6. 每次开新对话，开场白里要加一句："先读 docs/lessons/ 下所有 md，避免重蹈覆辙"
7. 未来真要切本地部署时：把 `.env` 里 4 个 `*_PROVIDER` 从 `cloud` 改成 `local`，确认 Ollama 在跑，重启服务即可——业务代码应该一行不改

## 四、未来演进预留位（先记着，别现在做）

- 多 Agent 群聊协作（参考 Manus Cue）：现在 Sub-agent 是主 Agent 派活，未来可升级成多个 Agent 互相接力；真上的时候再补死锁检测/全局仲裁
- 支付通道：现在 Sentinel 直接拒，未来接 Stripe Link 一次性虚拟卡这种方案再放开
- 眼镜/语音入口：交互层预留，先不做
- 业主主动推送（Feed）：等 Library 里有 20 个业主真实数据后再做

## 五、变更记录

- **v0.1.4.1（2026-10-01）**：原则 8 补 C 段上下文工程——工具输出截断（top 5、每段≤500字）+ 历史压缩（5 轮后摘要+最近 3 轮，cheap 档生成摘要）；Step 11 同步加上这两条
- **v0.1.4（2026-10-01）**：补原则 8（交付前自检 + 失败降级），src/validators/ 写确定性校验器（合计/必填/负数/预算超支），工具失败重试 1 次后优雅降级不甩堆栈；Step 加第 11 步
- **v0.1.3（2026-10-01）**：补原则 7（渠道适配层），C 端走 web_h5、B 端走 wecom，业务层不 import 任何渠道 SDK；Step 加第 10 步；.env 加 CHANNEL_WEB_H5_ENABLED/CHANNEL_WECOM_ENABLED/WECOM_BOT_ID/WECOM_BOT_SECRET。明确不做：个人微信机器人、小程序、LightVela skill
- **v0.1.2（2026-10-01）**：补原则 6（双档模型路由 cheap/frontier，关键词规则分流，默认走 frontier，scope 外直接拒）；Step 加第 9 步（最简 Router）；.env 加 ROUTER_MODE/ROUTER_DEFAULT_TIER/CHEAP_LLM_PROVIDER/FRONTIER_LLM_PROVIDER/ROUTER_OUT_OF_SCOPE_REPLY
- **v0.1.1（2026-10-01）**：补原则 5（血泪教训库机制）、Sentinel 加"改 owners 前自动快照"、Planner 预留 max_steps、Step 7 之后加 Step 8（建 lessons/ 目录）、.env 加 BACKUP_DIR/BACKUP_RETENTION_DAYS/MAX_STEPS_PER_TASK
- **v0.1（2026-10-01）**：初版，4 条原则 + 7 Step + .env.example
