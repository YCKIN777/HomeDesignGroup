# Agent 编队计划 v3（9 业务 Agent）

> 版本：v3（2026-10-02） · 适用范围：家装 AI 平台（HomeDesignGroup）· 通用内核 + 公司配置双层
> 决策记录：软装部与材料部并列（硬装/软装两条线）；总数 **9 个业务 Agent**，总经办兼任中控（不独立）；谈单知识库(kb) 归设计师；材料 Agent 首版只做选型+清单（浅），供应商比价/采购下单留扩展位。

---

## 1. 业务链路（9 部门 → 9 Agent）

```
业务员(1) → 客服(2) → 设计师(3) → 预算部(4) → 材料(5) ┐
                                                 ├→ 工程(7) → 售后部(9)
                                         软装(6) ┘
                                   总经办(8) 全程审批监督 + 看板 + 协调
```

**链路语义**：
- 业务员跑获客 → 客服接待建档 → 客服派单给设计师 → 设计师量房出方案+谈单 → 预算部出模板报价+收款计划 → 材料部配硬装主材 / 软装部配家具灯具窗帘 → 工程部施工+五节点验收 → 交付后售后部承接质保（整体2年/防水10年）。
- 总经办（周乾坤董事长/黄旭设计总监等）审批所有对外动作（折扣<9.8折、外发消息、方案定稿、开工闸门），看跨部门数据看板。

## 2. 九个 Agent 明细

| # | Agent | 一句话职责 | 现有代码映射 | 核心数据表 | 对外闸门 |
|---|---|---|---|---|---|
| 1 | 业务员 Agent | 线索归集→建档打标→评分→SOP跟进→邀约到店 | lead_agent + scoring_agent + sop_agent + invite_agent（4→1 收敛） | customers/scores/todos/invites | 邀约发送人工确认 |
| 2 | 客服 Agent（前台） | 首联/咨询/跟进，AI 起草→收件箱人审后发 | M3a/M3b 消息链路（封装成 Agent 类） | messages | 外发消息人审（Sentinel external_send） |
| 3 | 设计师 Agent | 接客服派单→建项目→量房设计方案（版本递增）→谈单知识库 | dispatch_agent + 方案沉淀 + kb_agent（合并） | projects/design_plans/craft_knowledge | 方案定稿人工确认 |
| 4 | 预算部 Agent | 模板驱动报价(325条)→折扣审批→收款计划→报价单导出 | quote_agent（模板驱动） | quotes/quote_items/quote_templates/payments | 折扣<9.8折待总经办审批 |
| 5 | 材料 Agent（硬装） | 主材/硬装材料选型 + 材料清单生成 | 🆕 新封装（materials 表+范本主材 67 条数据已有） | materials / quote_items(section=主材) | 首版只读+出清单，无对外动作 |
| 6 | 软装部 Agent | 家具/灯具/窗帘/布艺等软装配置 + 软装清单 | 🆕 新建（全新表 soft_furnishings） | soft_furnishings | 软装清单出给客户前人工确认 |
| 7 | 工程 Agent | 工地日报 + 五节点验收(水电/防水/泥木/油漆/竣工) + 工艺问答 | site_report_agent + craft_qa_agent（合并） | site_reports/inspections | 验收结果落库即对外（日报走人审） |
| 8 | 总经办 Agent（兼中控） | 审批汇总 + 数据看板 + 跨部门协调 + 审计追溯 | Bus + Planner + Sentinel + actions（收口成 Agent） | audit_log/sedimentation | 不直接对外，只编排审批 |
| 9 | 售后部 Agent | 质保登记（整体2年/防水10年）+ 售后工单 + 回访 SOP | 🆕 新建（全新表 after_sales） | after_sales | 质保认定/赔付动作人工确认 |

## 3. 现有代码 → 目标编队映射（归并与缺口）

| 现有文件（9 个业务 Agent） | 去向 |
|---|---|
| lead / scoring / sop / invite | → 业务员 Agent（1） |
| （M3a/M3b 消息链路逻辑） | → 客服 Agent（2） |
| dispatch / kb / 方案沉淀 | → 设计师 Agent（3） |
| quote | → 预算部 Agent（4） |
| （materials 表 + 范本主材数据） | → 材料 Agent（5）🆕 |
| — | 软装部 Agent（6）🆕 |
| site_report / craft_qa / 验收逻辑 | → 工程 Agent（7） |
| （Bus/Planner/Sentinel/actions/看板） | → 总经办 Agent（8） |
| — | 售后部 Agent（9）🆕 |

**缺口**：材料 Agent（新封装）、软装部 Agent（新表+新逻辑）、售后部 Agent（新表+新逻辑）；其余为收敛/重命名，不改业务规则。

## 4. 数据与语义隔离（沿用既有原则）

- **数据按公司隔离**：每公司一库（壹城精工.db），9 个 Agent 共用本库表链。
- **语义在通用内核共享**：Agent 不互相 import；"指令/工具注册表 + 数据库表 + 状态约束 + 审批闸门"四件套松耦合（见 Agent协作协议v1）。
- **新增 Agent 黄金法则**：加一张表 → 加一组动作(actions) → 加闸门规则(若对外) → 注册指令/工具 → 不动其他 Agent。

## 5. 推进顺序（每步自检，已有跳过，没有才做）

| 步 | 动作 | 验收 |
|---|---|---|
| P1 | 落编队计划 v3（本文档）+ 同步 Obsidian | 文档双份就位 |
| P2 | 归并收敛：lead/scoring/sop/invite → 业务员 Agent 类；dispatch/kb/方案 → 设计师 Agent 类；site_report/craft_qa → 工程 Agent 类 | 原验证脚本全绿（verify_phase2/phase34/main 等） |
| P3 | 封装客服 Agent 类（首联/人审后发收口） | 消息链路回归 |
| P4 | 封装总经办 Agent 类（审批汇总+看板+审计入口） | 审批/看板回归 |
| P5 | 材料 Agent：materials 表 + 主材清单生成（浅版） | 材料清单可生成 |
| P6 | 软装部 Agent：soft_furnishings 表 + 软装清单 | 软装清单可生成 |
| P7 | 售后部 Agent：after_sales 表 + 质保登记 + 回访 SOP | 售后工单闭环 |
| P8 | 工作台按 9 部门视图呈现 + 全链路回归 | 浏览器实测全过 |

> 注：P2-P4 为结构收敛（行为不变）；P5-P7 为新增能力；P8 为呈现收口。每一步完成后更新推进计划 v1.12+。
