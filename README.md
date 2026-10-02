# 家装 AI 平台（HomeDesignGroup）

面向家装场景的 AI Agent 平台。**通用内核 + 定制配置双层**：内核锁定（状态机/规则引擎/权限/审计/Provider 抽象），配置按公司灌入（YAML 配置包）。未来切本地部署零改业务代码。

## 两条产品线（共用内核，独立子 Agent）

| 线 | 场景 | Agent |
| --- | --- | --- |
| 获客签单线（壹城精工，已建成） | 线索→客服→派单 | lead / scoring / sop / invite / kb / dispatch（6 个） |
| 业主监理线（契约 v0.1，已完成 Step1-7） | 工艺问答 / 报价单 / 工地日报 | 3 个 MVP Sub-agent（craft_qa / quote / site_report） |

## 目录结构

```
HomeDesignGroup/
├── src/                 # main.py 中控 · agents/ · kernel/(状态机/规则/总线/动作注册表) · providers/(Step2) · routers/
├── config/              # app_config.json · model_config.yaml（现有模型开关）
├── company_profiles/壹城精工/   # 配置包（manifest/terms/rules/extensions/workflow）
├── db/                  # 壹城精工.db（SQLite，每公司一库）
├── knowledge/           # 谈单知识库（报价/工艺/案例）
├── sedimentation/       # 沉淀中心（提炼物 md）
├── memory/              # 四层记忆（L1-L4，本体驱动）
├── data/chroma/         # 向量库（文件型，Step 2 起用）
├── scripts/             # verify/check 自检脚本
└── docs/                # 架构文档（总纲/技术框架/推进计划/契约）
```

## 启动

```powershell
.\start_platform.ps1     # 启动 API 服务 → http://127.0.0.1:8000（登录 admin/12345678）
python src/main.py       # CLI 中控（业务指令集 /help）
.\backup.ps1             # 数据备份 → backups\<时间戳>\
```

## 模型开关（双轨，Step 2 完成接线）

- **现有**：`config/model_config.yaml` → `provider: mock|doubao|ollama`（mock 无需 key）
- **契约**：`.env` → `LLM_PROVIDER=cloud|local`、`EMBEDDING_PROVIDER`、`VECTOR_STORE`、`OCR_PROVIDER`
- 真实调用前：复制 `.env.example` 为 `.env`，填 `LLM_CLOUD_API_KEY`；未配置时 provider 保持 `mock`

## 架构契约（最高优先级）

`docs/架构契约_Agent骨架提示词_v0.1.md` — 4 条不可妥协原则（Provider 抽象 / Day1 结构化三表 / Sentinel 人工闸门 / 双层配置）+ 7 个 Step。每次新开对话按 `_每次开场必粘贴.txt` 复述。

| Step | 内容 | 状态 |
| --- | --- | --- |
| 1 | 目录骨架+.env.example+README | ✅ |
| 2 | Provider 抽象层（LLM/Embedding/VectorStore/OCR 双后端+smoke） | ✅ 10/10 |
| 3 | owners/craft_knowledge/materials 三表+迁移+HTTP 路由 | ✅ 9/9 |
| 4 | Sentinel 中间件+5 规则单测 | ✅ 13/13 |
| 5 | Planner+Tool dispatch | ✅ 7/7 |
| 6 | 三个 MVP Sub-agent demo+HTTP 出口（/api/agents/*） | ✅ 10/10 + 3/3 |
| 7 | 切本地部署操作手册 | ✅ 见 docs/07-部署运维 |

**契约线 HTTP 出口（已挂载运行）**：`POST /api/agents/craft-qa`（工艺问答）· `POST /api/agents/quote`（报价单草稿）· `POST /api/agents/site-report`（工地日报 pending）· `POST/GET /api/core/owners|craft|materials`（三张核心表）。

详细推进：`docs/05-开发架构/平台搭建推进计划v1.md`（v1.4）
