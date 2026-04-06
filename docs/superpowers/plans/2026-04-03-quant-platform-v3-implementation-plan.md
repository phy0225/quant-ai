# Quant Platform v3 实现计划

**日期**: 2026-04-03
**版本**: v1.0
**状态**: 待执行
**对应设计**: `docs/specs/2026-04-03-quant-platform-v3-design.md`

---

## 1. 计划目标

本计划用于指导 Quant Platform v3 的完整落地实施。

本次实施目标不是单纯改 UI，也不是只做数据迁移，而是完成以下主线闭环：

- MySQL 底座切换
- 特征接入统一化
- `Layer 1` 因子引擎落地
- Agent 决策因子化
- `Mode A / Mode B` 双模式决策
- 股票执行单与审批流重构
- 真实回测
- `T+5` 结算与 Agent 动态权重
- 图谱回填
- `Layer 2/3` 占位能力落地

---

## 2. 实施原则

1. 先打通真实闭环，再做体验增强  
   优先保证研究、决策、审批、回测、结算链路可用。

2. 先后端底座，后前端改版  
   先稳定数据结构和接口，再推进页面全面升级。

3. 一次切换 MySQL，不保留旧栈主路径  
   避免双栈长期并存带来的维护成本。

4. 先 Layer 1，后 Layer 2/3 自动化  
   首期只保证 Layer 2/3 可进入、可记录、可人工操作。

5. 所有阶段必须可验收  
   每一阶段都要有明确产物、接口和验证方式。

---

## 3. 总体阶段

### Phase 0: 底座与模型

目标：

- 完成 MySQL schema、连接层、查询层
- 完成核心业务模型重建
- 为后续 API 和服务迁移提供稳定基础

交付内容：

- `db/schema.sql`
- `db/connection.py`
- `db/queries/*`
- `config.py` MySQL/Feature/Scheduler 配置
- 初始种子数据脚本

验收标准：

- 服务可以连通 MySQL 并完成基础读写
- 关键表结构创建成功
- 种子数据可初始化默认 Agent 权重、基础规则、初始风险配置

### Phase 1: 特征与因子引擎

目标：

- 建立统一特征接入层
- 建立每日因子快照生成能力

交付内容：

- `services/feature_client.py`
- `services/factor_engine.py`
- `services/nav_calculator.py`
- `services/scheduler.py`

验收标准：

- 能按日期查询股票、行业、概念、市场特征
- 能生成 `daily_factor_snapshots`
- 能识别市场状态并写入快照

### Phase 2: API 与业务模型迁移

目标：

- 将核心业务 API 迁移到新数据层
- 重建决策、审批、组合、规则、风控接口

交付内容：

- `routers/decisions.py`
- `routers/approvals.py`
- `routers/portfolio.py`
- `routers/risk.py`
- `routers/rules.py`
- 新增 `routers/features.py`
- 新增 `routers/factors.py`
- 新增 `routers/strategy.py`
- 新增 `routers/candidate.py`
- 新增 `routers/settlement.py`

验收标准：

- 现有主路径接口可在 MySQL 下运行
- `Mode A / Mode B` 请求模型可被新接口支持
- 候选池、因子、策略等新接口可读写

### Phase 3: Agent 与决策重构

目标：

- 完成 Agent Pipeline 因子化重构
- 去除随机调仓逻辑
- 建立双模式决策输出结构

交付内容：

- `agents/pipeline.py`
- `agents/*_agent.py`
- `agents/factor_context` 或等效上下文构造模块

验收标准：

- Agent 能读取统一 `FactorContext`
- Mode A 支持多实体研究
- Mode B 输出股票调仓单
- 相同输入下调仓结果完全一致

### Phase 4: 审批、图谱、结算闭环

目标：

- 完成审批对新调仓模型的适配
- 完成图谱回填
- 完成 `T+5` 结算与 Agent 权重更新

交付内容：

- `services/settlement.py`
- `services/graph.py`
- 审批修改与结算回填逻辑

验收标准：

- 审批通过后写入正确的股票持仓快照
- 图谱节点能记录 `mode / market_regime / factor_snapshot`
- 结算任务可更新 Agent 正确率与权重

### Phase 5: 真实回测

目标：

- 将回测改造为真实历史信号/因子驱动

交付内容：

- `services/backtest.py`
- `routers/backtest.py`

验收标准：

- `signal_based` 可基于历史已审批信号回测
- `factor_based` 可基于历史因子快照回测
- `simulation` 成为显式兜底模式

### Phase 6: 前端重构

目标：

- 将页面升级为研究-决策-审批-验证闭环产品

交付内容：

- 新增 `FactorsPage.vue`
- 新增 `StrategyPage.vue`
- 新增 `DecisionListPage.vue`
- 重构 `DashboardPage.vue`
- 重构 `PortfolioPage.vue`
- 重构 `AnalyzePage.vue`
- 重构 `ApprovalDetailPage.vue`
- 重构 `DecisionDetailPage.vue`
- 重构 `BacktestPage.vue`
- 扩展 `RulesPage.vue`
- 更新 `router/index.ts`
- 更新各 API 与 types 文件

验收标准：

- 导航支持 `Factors / Strategy / Decisions`
- Analyze 支持 `Mode A / Mode B`
- Dashboard 展示因子、净值、Agent 准确率、待审批

### Phase 7: Layer 2/3 占位落地

目标：

- 提供首期可见、可操作但不自动闭环的因子发现与策略演进能力

交付内容：

- `services/factor_discovery.py`
- `services/strategy_evolution.py`
- 对应页面入口与任务列表

验收标准：

- 能手动触发任务
- 能记录状态与日志
- 能人工确认是否启用结果

---

## 4. 工作分解结构

### 4.1 后端任务

#### A. 数据层

- 设计并落地 MySQL schema
- 实现连接池和上下文管理
- 为各业务域创建 queries 模块
- 编写初始化脚本与种子数据
- 清理 ORM 主路径依赖

#### B. 配置与启动

- 增加 MySQL 配置项
- 增加 Feature Platform 配置项
- 增加 APScheduler 配置项
- 在 `main.py` 中集成 scheduler lifespan

#### C. 特征与因子

- 实现 Feature Adapter API/DB 双模式
- 定义字段元数据查询
- 实现因子筛选与快照生成
- 实现 market regime 识别

#### D. 决策引擎

- 实现 `FactorContext` 装配
- 改造 4 个 Agent 读取因子上下文
- 在 Pipeline 中实现 Mode A/Mode B 分支
- 实现确定性调仓公式
- 输出结构中加入因子归因与快照引用

#### E. 审批、组合、图谱

- 改造审批修改接口适配股票调仓单
- 改造组合接口支持候选池与表现摘要
- 扩展图谱节点结构

#### F. 回测与结算

- 重写回测主逻辑
- 实现 signal-based / factor-based / simulation 三模式
- 实现 T+5 结算任务
- 实现 Agent 权重更新逻辑

#### G. Layer 2/3 占位

- 创建任务记录模型
- 创建手动触发接口
- 创建状态查询接口

### 4.2 前端任务

#### A. 信息架构

- 重构侧边栏
- 增加 Decisions / Factors / Strategy 路由
- 调整页面分组与跳转路径

#### B. Analyze

- 增加 Mode A/Mode B 切换
- 支持多实体分析输入
- 支持股票候选池与目标仓位配置
- 显示实时进度、因子快照与结果摘要

#### C. Decision / Approval

- 增加决策列表页
- 重构决策详情页
- 支持 Mode B 调仓单展示
- 支持审批时逐项改权重与约束反馈

#### D. Portfolio / Dashboard

- 展示持仓、行业分布、候选池
- 展示因子状态、Agent 准确率、净值曲线、待审批

#### E. Factors / Strategy

- 展示有效因子与历史表现
- 展示 Layer 2 任务
- 展示策略版本与实验记录

#### F. Backtest / Rules / Graph

- 支持三种回测模式
- Rules 页增加 Agent 权重与风控事件
- Graph 页展示因子与市场状态相关信息

### 4.3 测试任务

- 重建测试数据库配置
- 为查询层补单元测试
- 为 Factor Engine 补单元测试
- 为 Pipeline 补确定性测试
- 为回测与结算补服务测试
- 为 Mode A/Mode B 补 API 集成测试
- 为前端关键路径补类型与构建验证

---

## 5. 推荐执行顺序

### Step 1

先完成数据层与配置层。

原因：

- 后续所有服务都依赖新 schema
- 一次性切换 MySQL 是本次版本的硬边界

### Step 2

再完成 Feature Adapter 与 Factor Engine。

原因：

- Agent 因子化改造依赖 `daily_factor_snapshots`
- `Mode A / Mode B` 都依赖统一特征层

### Step 3

再迁移 API 与业务模型。

原因：

- 决策、审批、组合接口要先切到新数据层

### Step 4

随后重构 Agent Pipeline 与审批闭环。

原因：

- 这是从“演示分析”升级到“可执行决策”的核心步骤

### Step 5

再重写回测与结算。

原因：

- 它们依赖新决策模型和审批记录

### Step 6

最后统一重构前端页面。

原因：

- 避免页面先改、接口又频繁变更

### Step 7

最后补齐 Layer 2/3 占位能力。

原因：

- 它们首期不是主链路，不应阻塞闭环上线

---

## 6. 里程碑定义

### Milestone 1: MySQL 底座可运行

完成标志：

- 服务启动可连 MySQL
- 关键表创建成功
- 种子数据初始化完成

### Milestone 2: 每日因子快照可生成

完成标志：

- 可生成 `daily_factor_snapshots`
- 可读取多实体特征
- 能识别 market regime

### Milestone 3: 新决策链路可跑通

完成标志：

- Mode A 可分析多实体
- Mode B 可输出股票调仓单
- 审批可处理新结构

### Milestone 4: 真实闭环成立

完成标志：

- 审批通过后持仓和图谱正确写入
- T+5 结算可运行
- Agent 权重可动态更新

### Milestone 5: 真实回测成立

完成标志：

- signal-based 与 factor-based 回测可运行
- simulation 成为显式兜底

### Milestone 6: 前端产品形态完成

完成标志：

- 新导航上线
- Factors / Strategy / Decisions 页面可用
- Analyze / Approval / Dashboard / Backtest 页面完成重构

### Milestone 7: 首期发布就绪

完成标志：

- Layer 2/3 占位能力可访问
- 测试通过
- 文档补齐

---

## 7. 风险与应对

### 风险 1: MySQL 一次性切换影响面大

影响：

- 容易在早期引入大面积回归

应对：

- 先完成 schema + queries + 基础读写测试
- 迁移期间优先保留接口语义稳定

### 风险 2: 多实体研究到股票执行的映射复杂

影响：

- 容易导致 Mode B 输出不可解释

应对：

- 首期使用明确可见的映射规则
- 在结果页展示行业/概念映射得分来源

### 风险 3: 因子引擎与 Agent 重构同时进行

影响：

- 容易让分析链路长时间不可用

应对：

- 先做 FactorContext 兼容空因子模式
- 保证 Agent 在无因子时也能运行，但显式降级

### 风险 4: 真实回测依赖历史数据完整性

影响：

- 数据不足会导致回测结论失真

应对：

- 在报告中加入 warning
- 不足数据时降级到明确标记的 simulation

### 风险 5: 前端改动面广

影响：

- 容易出现路由、类型、接口不同步

应对：

- 后端接口先稳定
- 前端按页面域逐步切换

---

## 8. 阶段验收清单

### Phase 0 验收

- MySQL schema 可初始化
- 默认风险配置与 Agent 权重可写入
- 查询层基本 CRUD 可用

### Phase 1 验收

- 特征平台接口可查询多实体
- 每日快照可落库
- market regime 正常输出

### Phase 2 验收

- `/decisions` `/approvals` `/portfolio` `/rules` `/risk` 可用
- `/features` `/factors` `/strategy` `/candidate` `/settlement` 可用

### Phase 3 验收

- Mode A 多实体分析成功
- Mode B 股票调仓单生成成功
- 权重建议不再使用随机数

### Phase 4 验收

- 审批、持仓、图谱回填打通
- T+5 结算打通
- Agent 权重更新打通

### Phase 5 验收

- signal-based 回测成功
- factor-based 回测成功
- simulation 结果被清晰标识

### Phase 6 验收

- 页面与导航完成改版
- 关键交互链路通畅
- 构建通过

### Phase 7 验收

- Layer 2/3 页面与任务入口可用
- 状态、日志、手动确认流程可用

---

## 9. 实施建议

建议将开发组织为三条主线并行，但按依赖顺序收敛：

- 主线 A：数据库与后端服务
- 主线 B：Agent、回测、结算闭环
- 主线 C：前端页面与交互改版

其中：

- A 必须先完成底座
- B 可在 A 稳定后加速推进
- C 应在接口稳定后集中推进

如果资源有限，优先级建议如下：

1. 数据层
2. 因子与 Agent
3. 审批与结算
4. 回测
5. 前端重构
6. Layer 2/3 占位

---

## 10. 发布前检查

- MySQL 初始化脚本已验证
- 关键后端链路测试通过
- 前端 `build` 通过
- 决策、审批、回测、结算链路完成冒烟验证
- 风险配置、默认权重、候选池种子数据已准备
- 文档已更新到最新设计与计划

---

## 11. 下一步建议

基于本计划，下一步最适合继续拆成三个可执行任务包：

- 数据库与后端基础设施任务包
- 决策闭环与回测结算任务包
- 前端改版任务包

如果需要，可以继续把本计划拆成更细的开发 backlog，精确到文件级任务列表。
