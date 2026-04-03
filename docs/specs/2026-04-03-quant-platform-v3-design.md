# Quant Platform v3 需求设计

**日期**: 2026-04-03
**版本**: v1.0
**状态**: 待评审
**来源**: 基于 `docs/specs/2026-04-02-quant-platform-redesign.md` 收敛重写，不覆盖原文

---

## 1. 设计结论

本次版本定义为一次完整大版本重构，但首期聚焦“可落地闭环”而不是“所有愿景一次做完”。

本版采用以下边界：

- 产品与技术底座一起升级，不拆成两个项目
- `Layer 2 因子发现`、`Layer 3 策略演进` 首期保留入口、任务模型、手动触发能力，不纳入自动闭环硬验收
- 研究层支持 `股票 / 行业 / 概念 / 市场` 多实体分析
- 执行层只支持 `股票持仓` 与 `股票调仓单`
- 数据层一次性切换为 `MySQL + asyncmy`，不保留 SQLite/SQLAlchemy 兼容运行

推荐方案为“闭环主线版”：

- `Feature Adapter -> Factor Engine(Layer 1) -> Agent 决策重构 -> Mode A/Mode B -> Approval -> 股票执行单 -> 真实回测 -> T+5 结算 -> 图谱回填`

---

## 2. 背景与问题

当前项目已具备基础交易研究产品雏形，已有页面与主流程包括：

- Dashboard
- Portfolio
- Analyze
- Approvals
- Rules
- Backtest
- Graph

但从当前代码与交互形态看，系统仍偏演示态，主要问题如下：

1. Agent 缺少统一因子证据层  
   现有 Agent 主要直接读取原始数据并输出结论，缺少统一的因子上下文与可追溯证据。

2. 调仓建议不稳定  
   当前推荐权重存在随机逻辑，相同输入无法保证输出一致。

3. 回测与真实信号脱节  
   回测结果仍以模拟为主，无法真实验证历史决策质量。

4. 研究层与执行层未分层  
   当前系统主要围绕股票分析设计，不支持“研究上看行业/概念，执行上仍回落股票”的完整闭环。

5. 底层存储已不适合本次扩展  
   若接入因子快照、策略版本、Agent 结算、候选池、多实体研究等能力，当前数据层会成为明显瓶颈。

---

## 3. 版本目标

### 3.1 业务目标

- 建立统一特征接入层，支持股票、行业、概念、市场四类实体特征查询
- 建立 `Layer 1` 因子筛选与每日快照能力，提供有效因子集与因子得分
- 重构 Agent 决策层，使 Agent 基于因子上下文进行推理
- 支持双模式决策：
  - `Mode A`: 定向分析
  - `Mode B`: 组合调仓
- 支持研究层多实体分析，但执行层始终输出股票调仓单
- 回测改为真实历史信号/因子驱动
- 建立 `T+5` 结算与 Agent 表现回填机制
- 为 `Layer 2/3` 预留稳定扩展入口

### 3.2 技术目标

- 一次性切换到 `MySQL + asyncmy`
- 去除 SQLAlchemy ORM 主路径，改为显式查询层
- 以 `Factor Snapshot + Decision Run + Agent Performance` 为核心重建业务模型
- 前端信息架构由“操作型页面集合”升级为“研究-决策-审批-验证”闭环平台

---

## 4. 范围定义

### 4.1 In Scope

- MySQL 数据模型重建
- Feature Adapter
- Factor Engine `Layer 1`
- Agent Pipeline 重构
- `Mode A / Mode B`
- 多实体研究能力
- 股票执行单与审批流
- 真实回测
- `T+5` 结算
- Agent 动态权重
- 图谱结果回填
- `Factors / Strategy / Decisions` 新页面
- `Layer 2/3` 的入口、任务记录、手动触发与占位展示

### 4.2 Out of Scope

- 行业/概念直接入仓
- 多资产执行引擎
- 分钟级或 Tick 级回测
- Layer 2/3 自动闭环调优上线
- 兼容旧 SQLite/SQLAlchemy 双栈

---

## 5. 产品原则

1. 因子证据优先  
   Agent 输出必须能回溯到具体因子或因子组合，而不是只给文字结论。

2. 研究与执行分层  
   研究对象可多实体，执行对象只落股票。

3. 相同输入得到相同建议  
   调仓结果必须确定性，不允许随机幅度。

4. 先做真实闭环，再做自动演进  
   首期先把可验证主链路做实，再扩展 Layer 2/3 自动化。

5. 首期必须可验收  
   所有关键能力都应具备清晰状态、接口、页面与数据记录。

---

## 6. 核心业务设计

### 6.1 实体分层

系统区分两类实体：

- 研究实体
  - `stock`
  - `industry`
  - `concept`
  - `market`
- 执行实体
  - `stock`

约束如下：

- `Mode A` 可以直接分析股票、行业、概念
- `Mode B` 可以参考股票、行业、概念信号
- 最终输出的调仓单只允许股票
- 审批、持仓、净值、结算只面向股票

### 6.2 双模式决策

#### Mode A: 定向分析

输入：

- 分析对象列表，可为股票/行业/概念
- 可选组合上下文

输出：

- 每个对象的 Agent 信号
- 因子归因
- 风险等级
- 最终方向结论

用途：

- 辅助研究判断
- 为后续审批或再分析提供证据

#### Mode B: 组合调仓

输入：

- 当前股票持仓
- 股票候选池
- 可选行业/概念研究信号
- 目标仓位比例

输出：

- 股票调仓单
- 当前权重、目标权重、权重变化
- 组合约束校验结果
- 因子与 Agent 共同给出的调仓依据

### 6.3 多实体研究到股票执行的映射

首期采用“研究多实体，执行回落股票”的映射规则：

- 行业信号可提升对应行业成分股评分
- 概念信号可提升相关概念成分股评分
- 市场状态影响整体风险开关与目标仓位建议
- 最终股票调仓建议由：
  - 股票自身因子得分
  - 行业映射得分
  - 概念映射得分
  - Agent 信号加权结果
  - 风险约束
 共同决定

---

## 7. 架构设计

### 7.1 分层结构

- 前端 Vue 3
- FastAPI 应用层
- Feature Adapter
- Factor Engine
- Agent Pipeline
- Backtest / Settlement / Graph
- MySQL 查询层

### 7.2 关键模块

#### Feature Adapter

职责：

- 接入特征平台 API 或数据库
- 对外提供统一查询接口
- 按实体类型返回标准化字段

首期要求：

- 支持股票、行业、概念、市场四类实体
- 支持按日期查询
- 支持字段元数据查询

#### Factor Engine

职责：

- 基于历史特征计算因子表现
- 识别有效因子集合
- 生成每日因子快照
- 计算股票/行业/概念得分

首期要求：

- 完成 `Layer 1`
- 提供 `daily_factor_snapshots`
- 输出 market regime

#### Agent Pipeline

职责：

- 读取因子快照
- 组装 `FactorContext`
- 并发执行多个 Agent
- 汇总风险与执行建议

首期要求：

- Agent 不再直接以原始数据为主入口
- Agent 输出必须包含因子上下文摘要
- Mode B 调仓建议必须为确定性公式

#### Backtest

职责：

- 支持真实历史信号回放
- 支持历史因子驱动回测
- 保留 simulation 作为兜底模式

#### Settlement

职责：

- `T+5` 结算 Agent 表现
- 回填 Agent 正确率
- 触发动态权重更新

#### Graph

职责：

- 沉淀决策节点
- 回填结果表现
- 支持后续相似案例与经验检索

---

## 8. 数据模型设计

### 8.1 核心表

- `factor_definitions`
- `daily_factor_snapshots`
- `factor_performance`
- `strategy_versions`
- `strategy_experiments`
- `decision_runs`
- `agent_signals`
- `rebalance_orders`
- `agent_performance`
- `agent_weight_configs`
- `candidate_pool`
- `portfolio_nav_history`
- `graph_nodes`

### 8.2 关键关系

- 一个 `decision_run` 对应多个 `agent_signals`
- 一个 `decision_run` 在 Mode B 下可对应多个 `rebalance_orders`
- 一个 `decision_run` 绑定一个 `factor_snapshot`
- 一个 `agent_signal` 对应一个 `agent_performance`
- 一个 `strategy_version` 可关联多个实验记录

### 8.3 模型约束

- `decision_runs.mode` 必须区分 `targeted / rebalance`
- `rebalance_orders` 只允许股票标的
- `graph_nodes` 需要记录 `mode / market_regime / factor_snapshot / settled`
- `agent_weight_configs` 支持 `is_locked`

---

## 9. API 设计原则

### 9.1 保留的域模型

继续保留以下接口域：

- `/decisions`
- `/approvals`
- `/portfolio`
- `/backtest`
- `/graph`
- `/risk`
- `/rules`

新增：

- `/features`
- `/factors`
- `/strategy`
- `/candidate`
- `/settlement`

### 9.2 核心接口

#### 决策触发

- `POST /api/v1/decisions/trigger`

支持：

- `mode=targeted`
- `mode=rebalance`

#### 调仓单查询

- `GET /api/v1/decisions/{id}/orders`
- `GET /api/v1/decisions/{id}/orders/summary`

#### 审批修改

- `PUT /api/v1/approvals/{id}/modify`

#### 特征查询

- `GET /api/v1/features/snapshot`
- `GET /api/v1/features/market`
- `GET /api/v1/features/fields`

#### 因子查询

- `GET /api/v1/factors/daily`
- `GET /api/v1/factors/performance`
- `GET /api/v1/factors/score`
- `POST /api/v1/factors/discover`

#### 策略版本

- `GET /api/v1/strategy/versions`
- `GET /api/v1/strategy/active`
- `POST /api/v1/strategy/versions`
- `PUT /api/v1/strategy/versions/{id}/activate`

---

## 10. 前端信息架构

### 10.1 导航结构

核心交易闭环：

- Dashboard
- Portfolio
- Analyze
- Decisions
- Approval

量化研究：

- Factors
- Strategy
- Backtest

知识与配置：

- Graph
- Rules

### 10.2 页面职责

#### Dashboard

- 市场状态
- 有效因子 Top N
- Agent 准确率
- 净值曲线
- 最近决策与待审批

#### Portfolio

- 股票持仓列表
- 行业分布
- 候选池管理
- 进入 Mode B 的入口

#### Analyze

- `Mode A / Mode B` 切换
- 展示分析输入
- 展示因子快照预览
- 展示 Agent 实时进度

#### Decisions

- 决策列表
- 支持按 mode、状态、日期过滤

#### Decision Detail

- Agent 信号
- 因子归因
- 风险结论
- Mode B 下展示调仓单与组合校验

#### Approval

- 审批列表
- 单笔审批
- Mode B 支持逐行改目标权重

#### Factors

- 当日有效因子
- 因子历史表现
- Layer 2 任务入口

#### Strategy

- 当前策略版本
- 版本历史
- Layer 3 实验记录

#### Backtest

- 三种回测模式切换
- 净值曲线
- 热力图
- 风险指标

#### Graph

- 节点结果可视化
- 因子/市场状态/收益展示

#### Rules

- 自动审批规则
- Agent 权重
- 风控参数
- 风控事件

---

## 11. Layer 2 / Layer 3 首期定位

### 11.1 Layer 2 因子发现

首期必须具备：

- 页面入口
- 任务模型
- 手动触发
- 结果日志
- 人工确认是否启用

首期不要求：

- 自动周期运行
- 自动入库生效
- 自动与主策略闭环联动

### 11.2 Layer 3 策略演进

首期必须具备：

- 页面入口
- 策略版本记录
- 实验记录
- 手动激活版本

首期不要求：

- 自动周期演进
- 自动评估后切换生产版本

---

## 12. 非功能需求

- 查询延迟：特征查询缓存命中时 < 2s
- 因子评估：单次 60 日窗口评估 < 30s
- 因子上下文注入：普通请求 < 5s
- 所有回测必须可重复
- 因子与回测必须防止未来数据泄漏
- 因子执行沙箱禁止外部网络与危险模块
- 所有关键任务必须有状态：`running/completed/failed`

---

## 13. 分期交付建议

### P0 底座

- MySQL schema
- db connection / queries
- config 扩展
- Feature Adapter

### P1 核心服务

- Factor Engine
- scheduler
- nav calculator
- settlement

### P2 API

- decisions / approvals / portfolio / risk / rules 迁移
- 新增 factors / features / strategy / candidate / settlement

### P3 Agent

- pipeline 重构
- 4 个 Agent 接入 FactorContext

### P4 前端

- Factors / Strategy / Decisions 新页面
- Dashboard / Analyze / Portfolio / Approval / Decision 改版

### P5 回测

- 真实信号回测
- 因子驱动回测

### P6 占位扩展

- factor discovery
- strategy evolution

---

## 14. 验收标准

### AC-01 数据层切换

- 系统生产运行只依赖 MySQL
- 核心业务主路径不再依赖 SQLAlchemy ORM
- 能稳定读写因子、决策、调仓单、结算、净值、图谱相关表

### AC-02 多实体研究

- 可对股票、行业、概念发起定向分析
- 决策记录中能识别分析对象类型
- 页面可展示对象基础信息与因子归因

### AC-03 执行层约束

- Mode B 最终输出只包含股票调仓单
- 审批页、持仓页、净值页不出现行业/概念持仓写入

### AC-04 因子快照

- 每个交易日可生成一份 `daily_factor_snapshot`
- 快照中包含有效因子、市场状态、对象得分
- 决策记录可关联实际使用的因子快照日期

### AC-05 Agent 因子化

- Agent 在分析时可读取统一 `FactorContext`
- 决策详情可展示 Agent 信号与因子摘要
- 若因子为空，系统能显式标记“因子证据不足”但不中断流程

### AC-06 调仓确定性

- 相同输入重复触发 Mode B，输出的目标权重一致
- 不允许使用随机数决定权重变化

### AC-07 真实回测

- `signal_based` 回测基于历史已审批信号
- `factor_based` 回测基于历史因子快照
- `simulation` 仅作兜底，并在结果中明确标注

### AC-08 T+5 结算

- 系统能对已完成决策执行 T+5 结算
- 能回填每个 Agent 的表现记录
- 能更新动态权重并支持锁定跳过

### AC-09 图谱回填

- 审批通过后可创建图谱节点
- 结算后可回填收益、状态、因子快照、市场状态

### AC-10 Layer 2 占位能力

- Factors 页面可手动创建因子发现任务
- 可查看任务状态、日志、候选结果
- 可人工确认是否启用候选因子

### AC-11 Layer 3 占位能力

- Strategy 页面可创建实验记录
- 可保存新版本草案
- 可人工激活版本

### AC-12 前端信息架构

- 导航中出现 `Factors / Strategy / Decisions`
- Analyze 支持 `Mode A / Mode B`
- Dashboard 能看到因子状态、Agent 准确率、净值、待审批

### AC-13 回归要求

- 原有审批、风控、组合、图谱主流程不出现功能性倒退
- 后端测试可覆盖关键链路
- 前端构建无类型错误

---

## 15. 待确认项

以下问题留待实现前再细化：

- 行业/概念到股票的映射来源与更新策略
- 因子权重与 Agent 权重在 Mode B 中的最终融合公式
- 候选池维护权限与批量导入方式
- 策略版本 `program_md` 的编辑范围与校验规则
- MySQL 初始迁移、种子数据与历史数据搬迁策略

---

## 16. 实施建议

实现阶段建议遵循以下顺序：

1. 先完成 MySQL schema、连接层与查询层
2. 再接入 Feature Adapter 与 Factor Engine
3. 随后重构 Agent Pipeline 与决策模型
4. 再改造审批、回测、结算与图谱
5. 最后完成前端全链路重构与 Layer 2/3 占位能力

这能保证首期最先打通“真实研究闭环”，而不是先做视觉层改版。

---

## 16. Implementation Status Update (2026-04-03)

The implementation corresponding to this v3 design has been completed and validated with the following outcomes:

- Data foundation and query-layer migration tasks are implemented.
- Factor-aware deterministic decision pipeline is in place.
- Mode A (`targeted`) and Mode B (`rebalance`) decision flows are available end-to-end.
- Stock-only execution semantics are enforced for approvals/orders/portfolio updates.
- Backtest supports `signal_based` and `factor_based` modes.
- T+5 settlement and dynamic agent-weight feedback loop are online.
- Graph nodes now persist factor-aware metadata (`mode`, `factor_snapshot`, `market_regime`).
- Layer 2 manual factor discovery task flow is available (`/api/v1/factors/discover`, `FactorsPage`).
- Layer 3 manual strategy evolution task flow is available (`/api/v1/strategy/experiment`, `StrategyPage`).

Validation snapshot:

- Backend full suite: `cd backend && pytest tests -v` -> PASS
- Frontend build: `cd frontend && npm run build` -> PASS
