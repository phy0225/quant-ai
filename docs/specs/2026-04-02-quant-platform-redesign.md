# Quant AI 平台重设计规格文档

**日期**：2026-04-02
**版本**：v1.0
**状态**：待实施

---

## 背景与目标

### 当前问题

现有平台（sdd_full v2.x）存在三个根本性缺陷：

1. **信号来源不可信**：Agent 直接调 AKShare 原始数据 + LLM 拍方向，无统计验证依据
2. **回测与信号脱节**：回测使用 GBM 随机模拟，与历史 Agent 信号完全无关
3. **持仓调整视角单一**：只支持对指定标的做定向分析，无法输出组合级调仓方案

### 目标

基于特征平台（已有）的四类实体特征数据（股票/市场/行业/概念），构建：

- **因子筛选引擎**：每日计算 RankIC，动态筛选有效因子集合
- **Agent 决策层重构**：Agent 基于有统计依据的因子上下文做推理，不再依赖原始指标
- **双模式决策**：Mode A 定向分析 + Mode B 组合调仓
- **真实回测**：基于历史因子值和历史信号回放
- **演进机制脚手架**：Layer 2（LLM 因子发现）+ Layer 3（策略自动演进）
- **经验图谱**：记录因子组合 + 市场状态 + 决策结果，支持后续模型迭代

### 技术约束

- 在现有 `sdd_full`（FastAPI + Vue 3）基础上改造
- 业务数据库换 MySQL，去除 SQLAlchemy，使用 `asyncmy` 裸 SQL
- 特征平台已有，支持 API 请求或数据库直连（可配置切换）

---

## Section 1：整体架构

### 分层全景图

```
┌────────────────────────────────────────────────────────────┐
│                        前端（Vue 3）                         │
│  Dashboard  Portfolio  Analyze  Decisions  Approval         │
│  Factors    Strategy   Backtest  Graph     Rules            │
└──────────────────────────┬─────────────────────────────────┘
                           │ REST + WebSocket
┌──────────────────────────▼─────────────────────────────────┐
│                    FastAPI 应用层                            │
│  /decisions  /approvals  /portfolio  /candidate             │
│  /factors    /strategy   /settlement /backtest              │
│  /graph      /risk       /rules                             │
└──┬───────────────┬──────────────┬────────────────┬──────────┘
   │               │              │                │
   ▼               ▼              ▼                ▼
┌──────┐    ┌──────────────┐  ┌───────┐    ┌────────────┐
│MySQL │    │  因子引擎     │  │Agent  │    │特征平台     │
│业务库│    │  (Layer 1-3) │  │决策层 │    │Adapter     │
└──────┘    └──────────────┘  └───────┘    └────────────┘
```

### 六个核心模块

| 模块 | 职责 | 文件位置 |
|------|------|---------|
| 特征平台 Adapter | 对接特征平台（HTTP API 或 DB 直连，可配置切换） | `services/feature_client.py` |
| 因子筛选引擎 Layer 1 | 每日 RankIC 计算，筛选有效因子集合，识别市场状态 | `services/factor_engine.py` |
| LLM 因子发现 Layer 2 | LLM 生成复合因子表达式 → 回测验证 → 合并因子池（脚手架） | `services/factor_discovery.py` |
| 策略演进 Layer 3 | program.md 管理，策略版本迭代（脚手架） | `services/strategy_evolution.py` |
| Agent 决策层 | 接收因子上下文 → 多实体联动推理 → 输出可溯源决策 | `agents/` |
| 回测 + 结算 + 图谱 | 历史因子值回测，T+5 结算，经验沉淀 | `services/backtest.py` `services/settlement.py` |

### 每日数据流时序

```
08:30  特征平台预拉取（feature_client.prefetch_all）
08:45  因子引擎运行（IC计算 → daily_factor_snapshots）
09:00  市场开盘，Pipeline 可用
15:30  市场收盘
16:00  每日净值计算（nav_calculator）
16:30  T+5 结算（settlement）
每周一  Layer 2 因子发现（可配置）
每月初  Layer 3 策略演进（可配置）
```

### 现有代码处置策略

**保留 + 迁移（MySQL/asyncmy，逻辑不变）**
- FastAPI 路由结构、WebSocket manager
- approval_records 流程、portfolio_holdings/snapshots
- risk_config/risk_events、auto_approval_rules

**重构（接口不变，内部逻辑替换）**
- agents/pipeline.py → FactorContext 注入 + asyncio.gather 并发
- 4 个 Agent → 从 FactorContext 读取，不再直接调 AKShare
- services/backtest.py → 替换 GBM，基于历史因子值

**新增**
- services/feature_client.py、factor_engine.py、settlement.py
- services/nav_calculator.py、factor_discovery.py、strategy_evolution.py、scheduler.py
- routers/factors.py、strategy.py、candidate.py、settlement.py
- db/ 层（connection + queries）

---

## Section 2：MySQL 数据模型

### 新增表 DDL

```sql
-- 因子定义
CREATE TABLE factor_definitions (
  id            VARCHAR(36)  PRIMARY KEY,
  factor_key    VARCHAR(100) NOT NULL UNIQUE,
  name          VARCHAR(200) NOT NULL,
  entity_type   ENUM('stock','market','industry','concept') NOT NULL,
  domain        ENUM('price','fundamental','capital','sentiment') NOT NULL,
  source        ENUM('builtin','llm_discovered') DEFAULT 'builtin',
  formula       TEXT,
  description   TEXT,
  is_active     BOOLEAN DEFAULT TRUE,
  created_at    DATETIME DEFAULT NOW(),
  updated_at    DATETIME DEFAULT NOW() ON UPDATE NOW()
);

-- 每日因子快照
CREATE TABLE daily_factor_snapshots (
  id               VARCHAR(36)  PRIMARY KEY,
  trade_date       DATE         NOT NULL,
  market_regime    VARCHAR(20),
  effective_factors JSON,
  stock_scores     JSON,
  industry_scores  JSON,
  concept_scores   JSON,
  market_factors   JSON,
  created_at       DATETIME DEFAULT NOW(),
  UNIQUE KEY uk_date (trade_date)
);

-- 因子绩效历史
CREATE TABLE factor_performance (
  id           VARCHAR(36) PRIMARY KEY,
  factor_key   VARCHAR(100) NOT NULL,
  trade_date   DATE NOT NULL,
  ic           FLOAT,
  rank_ic      FLOAT,
  ic_ir        FLOAT,
  direction    TINYINT,
  is_effective BOOLEAN,
  created_at   DATETIME DEFAULT NOW(),
  UNIQUE KEY uk_factor_date (factor_key, trade_date)
);

-- 策略版本
CREATE TABLE strategy_versions (
  id              VARCHAR(36) PRIMARY KEY,
  version         VARCHAR(20) NOT NULL,
  program_md      TEXT,
  factor_weights  JSON,
  agent_weights   JSON,
  regime_rules    JSON,
  is_active       BOOLEAN DEFAULT FALSE,
  performance     JSON,
  created_at      DATETIME DEFAULT NOW()
);

-- 策略演进实验
CREATE TABLE strategy_experiments (
  id              VARCHAR(36) PRIMARY KEY,
  base_version_id VARCHAR(36),
  hypothesis      TEXT,
  proposal        JSON,
  new_version_id  VARCHAR(36),
  status          VARCHAR(20) DEFAULT 'running',
  created_at      DATETIME DEFAULT NOW()
);

-- 决策任务（重构）
CREATE TABLE decision_runs (
  id                  VARCHAR(36)  PRIMARY KEY,
  mode                ENUM('targeted','rebalance') NOT NULL,
  status              ENUM('running','completed','failed') DEFAULT 'running',
  triggered_by        VARCHAR(100) DEFAULT 'user',
  symbols             JSON,
  candidate_symbols   JSON,
  current_portfolio   JSON,
  factor_snapshot_id  VARCHAR(36),
  factor_date         DATE,         -- 实际使用的因子快照日期，fallback时与started_at日期不同
  strategy_version_id VARCHAR(36),
  market_regime       VARCHAR(20),
  final_direction     VARCHAR(10),  -- Mode A 专用，Mode B 为 NULL
  risk_level          VARCHAR(10),
  error_message       TEXT,
  started_at          DATETIME DEFAULT NOW(),
  completed_at        DATETIME
);

-- Agent 信号（从 JSON 拆为独立表）
CREATE TABLE agent_signals (
  id                VARCHAR(36) PRIMARY KEY,
  decision_run_id   VARCHAR(36) NOT NULL,
  agent_type        VARCHAR(50) NOT NULL,
  symbol            VARCHAR(20),
  direction         VARCHAR(10),
  confidence        FLOAT,
  reasoning_summary TEXT,
  signal_weight     FLOAT,
  data_sources      JSON,
  input_snapshot    JSON,
  is_contradictory  BOOLEAN DEFAULT FALSE,
  created_at        DATETIME DEFAULT NOW()
);

-- 调仓单（Mode B 专用）
CREATE TABLE rebalance_orders (
  id               VARCHAR(36) PRIMARY KEY,
  decision_run_id  VARCHAR(36) NOT NULL,
  symbol           VARCHAR(20) NOT NULL,
  symbol_name      VARCHAR(100),
  action           ENUM('buy','sell','hold','close','new') NOT NULL,
  current_weight   FLOAT DEFAULT 0,
  target_weight    FLOAT NOT NULL,
  weight_delta     FLOAT NOT NULL,
  composite_score  FLOAT,
  score_breakdown  JSON,
  reasoning        TEXT,
  created_at       DATETIME DEFAULT NOW()
);

-- Agent 绩效结算
CREATE TABLE agent_performance (
  id                  VARCHAR(36) PRIMARY KEY,
  decision_run_id     VARCHAR(36) NOT NULL,
  agent_signal_id     VARCHAR(36) NOT NULL,
  agent_type          VARCHAR(50) NOT NULL,
  symbol              VARCHAR(20),
  predicted_direction VARCHAR(10),
  predicted_at        DATETIME,
  settlement_date     DATE,
  actual_return       FLOAT,
  is_correct          BOOLEAN,
  factor_snapshot     JSON,
  settled_at          DATETIME
);

-- Agent 动态权重
CREATE TABLE agent_weight_configs (
  id           VARCHAR(36) PRIMARY KEY,
  agent_type   VARCHAR(50) NOT NULL UNIQUE,
  weight       FLOAT NOT NULL DEFAULT 0.25,
  accuracy_30d FLOAT,
  accuracy_60d FLOAT,
  is_locked    BOOLEAN DEFAULT FALSE,
  last_updated DATETIME DEFAULT NOW()
);

-- 自选股池
CREATE TABLE candidate_pool (
  id          VARCHAR(36) PRIMARY KEY,
  symbol      VARCHAR(20) NOT NULL UNIQUE,
  symbol_name VARCHAR(100),
  added_at    DATETIME DEFAULT NOW(),
  note        TEXT
);

-- 组合净值历史
CREATE TABLE portfolio_nav_history (
  id           VARCHAR(36) PRIMARY KEY,
  trade_date   DATE NOT NULL UNIQUE,
  nav          FLOAT NOT NULL,
  total_mv     FLOAT,
  daily_return FLOAT,
  created_at   DATETIME DEFAULT NOW()
);

-- 图谱节点（扩展）
CREATE TABLE graph_nodes (
  node_id           VARCHAR(36) PRIMARY KEY,
  approval_id       VARCHAR(36) NOT NULL,
  decision_run_id   VARCHAR(36),
  mode              ENUM('targeted','rebalance'),
  trade_date        DATE,
  symbols           JSON,
  market_regime     VARCHAR(20),
  effective_factors JSON,
  approved          BOOLEAN DEFAULT FALSE,
  outcome_return    FLOAT DEFAULT 0.0,
  outcome_sharpe    FLOAT DEFAULT 0.0,
  factor_snapshot   JSON,
  settled           BOOLEAN DEFAULT FALSE,
  created_at        DATETIME DEFAULT NOW(),
  settled_at        DATETIME
);
```

### 现有表改造

| 表 | 操作 | 说明 |
|----|------|------|
| approval_records | 新增 mode 字段 | 区分 Mode A/B |
| portfolio_holdings | 保留迁移 | 无结构改动 |
| portfolio_snapshots | 保留迁移 | 无结构改动 |
| risk_config | 保留迁移 | 无结构改动 |
| risk_events | 保留迁移 | 无结构改动 |
| auto_approval_rules | 保留迁移 | 无结构改动 |
| backtest_reports | 新增字段 | signal_based(BOOL) + factor_snapshot_id |

### 数据库连接层

```
database.py → asyncmy 连接池（替换 SQLAlchemy）
db/connection.py → 连接池封装 + get_db_conn() 上下文管理器
db/queries/
  decisions.py / approvals.py / factors.py / portfolio.py
  strategy.py / graph.py / risk.py
  settlement.py / backtest.py / agent_weights.py
```

---

## Section 3：API 接口设计

### 完整接口清单

```
/api/v1/
├── features/          特征平台 Adapter
├── factors/           因子管理
├── strategy/          策略版本
├── decisions/         决策任务（Mode A/B）
├── approvals/         审批流程
├── portfolio/         持仓管理
├── candidate/         自选股池
├── backtest/          回测
├── settlement/        T+5 结算
├── graph/             经验图谱
├── risk/              风控配置
└── rules/             自动审批规则
```

### 关键接口详情

#### 决策触发（核心）

```
POST /api/v1/decisions/trigger

Mode A（定向分析）：
{
  "mode": "targeted",
  "symbols": ["600036", "000001"],
  "current_portfolio": {"600036": 0.10}  // 可选，不传则从DB读
}

Mode B（组合调仓）：
{
  "mode": "rebalance",
  "current_portfolio": {"600036": 0.10, "600519": 0.15},
  "candidate_symbols": ["000858", "000001"],  // 可选，不传则用自选股池
  "target_position_ratio": 0.90
}

→ 立即返回 { decision_run_id, status: "running" }
```

#### 调仓单（Mode B 专用）

```
GET /api/v1/decisions/{id}/orders
→ [{ symbol, action, current_weight, target_weight,
     weight_delta, composite_score, score_breakdown, reasoning }]

GET /api/v1/decisions/{id}/orders/summary
→ { buy_count, sell_count, close_count, new_count,
     weight_turnover, constraint_checks }
```

#### 审批修改（Mode B）

```
PUT /api/v1/approvals/{id}/modify
{
  "modified_orders": [{ "symbol": "600036", "target_weight": 0.12 }],
  "reviewed_by": "trader01",
  "comment": "适当降低仓位"
}
```

#### 因子管理

```
GET  /api/v1/factors/daily?date=2026-04-02
GET  /api/v1/factors/performance?factor_key=momentum_20d&days=60
GET  /api/v1/factors/score?symbols=600036,000001&date=2026-04-02
POST /api/v1/factors/discover    { research_direction, constraints }
```

#### 策略演进

```
GET  /api/v1/strategy/versions
GET  /api/v1/strategy/active
POST /api/v1/strategy/versions   { program_md, factor_weights, ... }
PUT  /api/v1/strategy/versions/{id}/activate
POST /api/v1/strategy/experiment  { base_version_id, hypothesis }
GET  /api/v1/strategy/experiments?version_id=xxx
```

#### Agent 权重（Rules 模块）

```
GET /api/v1/rules/agent-weights
PUT /api/v1/rules/agent-weights/{agent_type}  { weight, is_locked }
```

#### 风控事件

```
GET /api/v1/risk/events?severity=critical&days=7
```

### WebSocket 事件

```
decision_completed          { decision_id, mode, final_direction | orders_count }
approval_updated            { approval_id, status }
factor_updated              { trade_date, effective_count, market_regime }
settlement_completed        { date, settled_count, avg_accuracy }
risk_alert                  { level, reason, trigger_value }
backtest_completed          { report_id, total_return, sharpe_ratio }
factor_discovery_completed  { task_id, found, results }
strategy_experiment_completed { experiment_id, new_version_id, summary }
```

---

## Section 4：Agent 决策层重构

### 核心变化

```
旧：Agent 自己拉数据 + 自己算指标 + LLM 拍方向
新：Agent 接收因子上下文（已验证的因子值）→ LLM 解读信号 → 输出因子归因
```

### Pipeline 流程

```
Step 1  准备上下文（同步）
        ① 读 daily_factor_snapshot（含 fallback：最近3日）
        ② 读 portfolio_holdings
        ③ 读 active strategy_version
        ④ 调特征平台 Adapter 拉特征向量
        ⑤ 组装 FactorContext（scored_stocks=None）

Step 2  Factor Scorer（Mode B 专用）
        遍历持仓+候选池，计算 composite_score
        写入 factor_context.scored_stocks

Step 3  4 个 Agent 并发（asyncio.gather）
        TechnicalAgent   → 价格/动量/波动因子
        FundamentalAgent → 基本面/估值因子
        NewsAgent        → 舆情因子 + AKShare 新闻文本
        SentimentAgent   → 资金流向因子

Step 4  矛盾检测
        reasoning 含反向关键词 → is_contradictory=True

Step 5  Risk Agent
        检查 risk_config 约束；Mode B 验证权重合计

Step 6  Executor（加权投票）
        Mode A：weights 从 agent_weight_configs 读取 → final_direction
        Mode B：composite_score → 组合优化器 → rebalance_orders

Step 7  写入 agent_performance 待结算行
        Pipeline 完成（decision_run 状态变 completed）后，
        为每条 agent_signal 创建一条 agent_performance 记录：
          predicted_direction = agent_signal.direction
          predicted_at        = agent_signal.created_at
          settlement_date     = started_at + 5 个交易日（via is_trading_day 日历）
          actual_return / is_correct = NULL（等待每日结算任务填写）
```

### FactorContext 结构

```python
@dataclass
class FactorContext:
    trade_date:        str
    market_regime:     str          # bull_low_vol | bear_high_vol | sideways ...
    effective_factors: list[dict]   # [{factor_key, domain, direction, ic_weight}]
    stock_features:    dict[str, dict]   # {symbol: {factor_key: value}}
    industry_features: dict[str, dict]
    concept_features:  dict[str, dict]
    market_features:   dict
    scored_stocks:     list[dict] | None  # Mode B，Step 2 填充
    strategy_version_id: str
    factor_weights:    dict
    regime_rules:      dict
```

### 组合优化器（Mode B）

```python
# 用因子得分比例分配仓位，strong_buy 给 1.3x 加成
adjusted_score = score × (1.3 if action_hint == "strong_buy" else 1.0)
target = (adjusted_score / total_adjusted_score) × target_position_ratio
target = min(target, max_single_weight)
# 归一化：缩放所有 target 使总和 = target_position_ratio
```

### daily_factor_snapshot 不存在时的 fallback

```
若当日 snapshot 不存在 → 用最近 3 个交易日内最新的 snapshot
decision_run 打标 factor_date ≠ trade_date
审批页显示警告："因子数据非最新，请谨慎审批"
```

### Mode A 多标的处理

```
每个 Agent 对每只标的单独输出一条 signal（agent_signals 表有 symbol 字段）
Executor 按 symbol 分组投票，每只股票独立得出 final_direction
approval 包含多条 recommendation，逐只审批
```

### Agent 并发执行

```python
results = await asyncio.gather(
    technical_agent.analyze(factor_context),
    fundamental_agent.analyze(factor_context),
    news_agent.analyze(factor_context),
    sentiment_agent.analyze(factor_context),
    return_exceptions=True
)
# 单个 Agent 失败不影响其他，fallback 信号标记 is_contradictory=False, confidence=0.20
```

---

## Section 5：前端页面设计

### 导航结构

```
核心交易流程
├── Dashboard       总览：持仓市值、因子状态、待审批、净值曲线
├── Portfolio       持仓管理（策略出发点）
├── Analyze         触发分析（Mode A/B 入口）
├── Decisions       决策列表/详情
└── Approval        审批队列

量化研究
├── Factors         因子管理（IC历史、Layer 2）
├── Strategy        策略演进（program.md、Layer 3）
└── Backtest        回测

知识与配置
├── Graph           经验图谱
└── Rules           自动审批规则 + Agent权重 + 风控参数
```

### 页面核心设计

#### Dashboard
- 市场状态卡片（regime）+ 持仓概览 + 待审批角标
- 当日有效因子 Top5（IC权重排序）
- Agent 准确率卡片（近60日，可点击跳转Rules）
- 净值曲线（策略 vs 沪深300，7/30/90日切换）
- 最近决策记录（最近5条）+ 风控状态指示器

#### Portfolio
- 持仓列表（代码/名称/权重/成本价/现价/浮盈%/市值）
- 持仓分布饼图（行业维度）
- 自选股池管理（Mode B 候选标的）
- 底部"AI 组合调仓建议"按钮 → 跳转 Analyze Mode B

#### Analyze
- **Tab 切换**：定向分析 / 组合调仓
- Mode A：标的多选输入 + 当日因子状态预览 + 触发按钮
- Mode B：持仓只读展示 + 候选标的 + 目标仓位滑块 + 触发按钮
- 分析进行中：实时显示各 Agent 完成状态（WebSocket）
- 底部：历史分析记录（最近10条，支持重分析）

#### Decisions
- 列表：mode 标签 / 时间 / 标的 / 方向或调仓概要
- Mode A 详情：因子上下文 + 4个Agent信号卡片（含矛盾警告）+ 因子归因
- Mode B 详情：调仓单列表（action色标）+ 持仓变化预览 + 约束验证结果

#### Approval
- 列表：mode标签 / 标的概要 / 等待时长 / 批量拒绝
- Mode A 审批：可修改单个标的权重，约束实时验证
- Mode B 审批：逐行修改 target_weight（可改为0跳过），约束面板实时反馈

#### Factors
- 当日有效因子列表（factor_key / IC / direction / weight / 30日IC_IR）
- 点击行展开 IC 历史曲线
- Layer 2 触发区（输入研究方向 → 发现结果 + 人工确认启用）
- 因子池全量列表（内置 + LLM 发现，含 formula）

#### Strategy
- 当前激活版本卡片 + program.md 编辑器
- 版本历史列表（对比/恢复）
- Layer 3 实验记录列表

#### Backtest
- 模式选择：基于历史信号 / 基于历史因子值 / GBM模拟（兜底）
- 信号不足10条时显示警告
- 结果：净值曲线 + 月度收益热力图 + 关键指标
- 导出 JSON + 复制参数重跑

#### Graph
- 图谱可视化（节点颜色=outcome_return，大小=置信度）
- 节点详情（factors_used / regime / outcome）
- 未结算节点灰色标注
- 相似案例查询（输入当前因子组合）

#### Rules
- Tab：自动审批规则 / Agent权重 / 风控参数 / 风控事件
- Agent权重 Tab：准确率展示 + 锁定开关 + 下次更新时间
- 风控事件 Tab：时间 / 级别 / 描述 / 是否解决

---

## Section 6：后台服务设计

### services/feature_client.py

```python
# 支持两种模式，.env 配置切换
# FEATURE_PLATFORM_MODE=api  → HTTP 请求
# FEATURE_PLATFORM_MODE=db   → MySQL 直连

class FeatureClient:
    async def fetch_snapshot(self, symbols, date, fields=None) -> dict[str, dict]
    async def fetch_history(self, symbols, start, end, fields=None) -> dict[str, list[dict]]
    async def fetch_market(self, date) -> dict
    async def fetch_industry(self, date) -> dict[str, dict]
    async def fetch_concept(self, date) -> dict[str, dict]
    async def prefetch_all(self, date)  # 08:30 预拉取，写内存缓存
```

### services/factor_engine.py

```python
IC_THRESHOLD    = 0.03   # IC 绝对值下限
IC_IR_THRESHOLD = 0.40   # IC_IR 下限（近20日）
ROLLING_WINDOW  = 60     # IC 计算滚动窗口（天）

async def run_daily(trade_date: str):
    # 1. 拉取历史特征数据（T-60 到 T-5）
    # 2. 计算每个因子的 RankIC 序列（与 price_return_5d 相关性）
    # 3. 筛选有效因子（IC + IC_IR 双阈值）
    # 4. IC 归一化为权重
    # 5. 识别市场状态（market_return_5d + market_volatility_20d）
    # 6. 拉取当日所有标的因子值
    # 7. 写入 daily_factor_snapshots + factor_performance

def _detect_regime(market_features) -> str:
    # bull_high_vol | bull_low_vol | bear_high_vol | bear_low_vol | sideways
    # 基于 market_return_5d（±1%阈值）和 market_volatility_20d（2.5%阈值）
```

### services/settlement.py

```python
async def run(settle_date: str):
    # 1. 查找 settlement_date = today 的待结算记录
    # 2. 批量拉取实际收益（feature_client.fetch_snapshot price_return_5d）
    # 3. 逐条判断 is_correct
    #    buy  正确条件：actual_return >  0.005
    #    sell 正确条件：actual_return < -0.005
    #    hold 正确条件：|actual_return| <= 0.005
    # 4. 批量写入结算结果
    # 5. 每20交易日触发 Agent 权重重算
    #    acc < 45% → weight 上限 10%
    #    acc 45-65% → 维持基础权重 25%
    #    acc > 65% → weight 可达 35%
    #    所有权重归一化，跳过 is_locked=True 的 Agent
    # 6. 回填 graph_nodes.outcome_return
    # 7. WebSocket broadcast: settlement_completed
```

### services/nav_calculator.py

```python
async def run(trade_date: str):
    # 1. 读持仓 × 收盘价 → total_mv
    # 2. 更新 portfolio_holdings 实时字段（current_price / market_value / pnl_pct）
    # 3. 计算 NAV = prev_nav × (1 + daily_return)
    # 4. 写入 portfolio_nav_history
    # 注：NAV 计算暂不处理资金流入流出，后续迭代完善
```

### services/scheduler.py

```python
# APScheduler AsyncIOScheduler
# 所有 job 开头调用 is_trading_day() 校验（处理法定节假日）
# 交易日历从 AKShare 获取，本地缓存（每月更新一次）

任务表：
  08:30 mon-fri  prefetch_all
  08:45 mon-fri  factor_engine.run_daily
  16:00 mon-fri  nav_calculator.run
  16:30 mon-fri  settlement.run
  08:00 mon      factor_discovery（每周，可配置）
  08:00 月第一交易日  strategy_evolution（可配置）

# lifespan 集成
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    yield
    scheduler.shutdown()
```

### services/factor_discovery.py（Layer 2 脚手架）

```python
# 一期：LLM生成因子表达式 → 子进程沙箱执行 → IC验证 → 人工确认启用
# 二期：引入 QuantaAlpha 轨迹进化机制，多轮自动改进

async def run_discovery(research_direction: str, task_id: str):
    # 1. LLM 生成3个候选复合因子（基于特征平台已有字段）
    # 2. 子进程沙箱执行（asyncio.wait_for timeout=10s，无网络/文件写权限）
    # 3. 计算历史 IC（基于60日历史数据）
    # 4. IC 通过阈值 → 写 factor_definitions（is_active=False，等人工确认）
    # 5. WebSocket broadcast: factor_discovery_completed
```

### services/strategy_evolution.py（Layer 3 脚手架）

```python
# 一期：LLM读取 program.md + 历史绩效 → 提议策略改进 → 创建新版本（is_active=False）
# 二期：引入 autoresearch 实验循环，自动回测验证，人工只审查日志

async def run_evolution(base_version_id: str, experiment_id: str):
    # 1. 读取 program.md + 近期因子绩效 + 近50条图谱节点
    # 2. LLM 提议因子权重调整 + 市场状态规则优化
    # 3. 创建新策略版本（is_active=False，等人工在 Strategy 页激活）
    # 4. 写入 strategy_experiments 记录
    # 5. WebSocket broadcast: strategy_experiment_completed
```

---

## Section 7：存量代码改造计划

### 后端文件处置

| 文件 | 操作 | 说明 |
|------|------|------|
| database.py | 重写 | SQLAlchemy → asyncmy 连接池 |
| models.py | 降级 | ORM 模型 → TypedDict 文档类 |
| schemas.py | 扩展 | 新增 Mode A/B Pydantic 模型 |
| config.py | 扩展 | 新增特征平台/MySQL/APScheduler 配置 |
| main.py | 修改 | 修复重复路由；加 scheduler lifespan |
| websocket_manager.py | 保留 | 无改动 |
| routers/decisions.py | 重构 | Mode A/B；接新 pipeline |
| routers/approvals.py | 重构 | Mode B 调仓单审批；约束验证 |
| routers/portfolio.py | 扩展 | 新增 /summary /performance /snapshots |
| routers/risk.py | 扩展 | 新增 GET /risk/events |
| routers/rules.py | 扩展 | 新增 agent-weights 端点 |
| routers/backtest.py | 重构 | 修复 Session Bug；接新回测引擎 |
| routers/graph.py | 扩展 | 适配新 graph_nodes schema |
| routers/factors.py | 新增 | |
| routers/features.py | 新增 | 特征平台代理接口（透传 feature_client） |
| routers/strategy.py | 新增 | |
| routers/candidate.py | 新增 | |
| routers/settlement.py | 新增 | |
| agents/base.py | 保留 | LLM 客户端无改动 |
| agents/pipeline.py | 重写 | FactorContext 注入；asyncio.gather |
| agents/cn_technical_agent.py | 重构 | 从 FactorContext 读取 |
| agents/cn_fundamental_agent.py | 重构 | 同上 |
| agents/cn_news_agent.py | 重构 | 保留 AKShare 新闻；新增因子上下文 |
| agents/cn_sentiment_agent.py | 重构 | 从 FactorContext 读取 |
| agents/portfolio_context.py | 保留 | 无改动 |
| services/cn_market_data.py | 降低使用 | 仅作 fallback |
| services/cn_fundamental_data.py | 降低使用 | 同上 |
| services/cn_news_data.py | 保留 | NewsAgent 仍需新闻文本 |
| services/cn_sentiment_data.py | 降低使用 | 同上 |
| services/backtest.py | 重写 | 替换 GBM；基于历史因子值 |
| services/graph.py | 扩展 | 写入 factor_snapshot/regime 字段 |
| services/feature_client.py | 新增 | |
| services/factor_engine.py | 新增 | |
| services/settlement.py | 新增 | |
| services/nav_calculator.py | 新增 | |
| services/factor_discovery.py | 新增 | |
| services/strategy_evolution.py | 新增 | |
| services/scheduler.py | 新增 | |
| db/connection.py | 新增 | asyncmy 连接池封装 |
| db/schema.sql | 新增 | 完整 MySQL DDL |
| db/queries/decisions.py | 新增 | |
| db/queries/approvals.py | 新增 | |
| db/queries/factors.py | 新增 | |
| db/queries/portfolio.py | 新增 | |
| db/queries/strategy.py | 新增 | |
| db/queries/graph.py | 新增 | |
| db/queries/risk.py | 新增 | |
| db/queries/settlement.py | 新增 | |
| db/queries/backtest.py | 新增 | |
| db/queries/agent_weights.py | 新增 | |
| db/queries/nav_history.py | 新增 | portfolio_nav_history 读写 |
| tests/conftest.py | 更新 | MySQL 测试库（Docker Compose）|
| tests/test_api.py | 更新 | 覆盖新 API 端点 |
| tests/test_units.py | 更新 | 覆盖因子引擎、结算逻辑 |

### 前端文件处置

| 文件 | 操作 | 说明 |
|------|------|------|
| pages/DashboardPage.vue | 重构 | 市场状态；因子概览；净值曲线 |
| pages/PortfolioPage.vue | 重构 | 持仓汇总；行业分布；自选股池 |
| pages/AnalyzePage.vue | 重构 | Mode A/B Tab；因子预览；WS进度 |
| pages/ApprovalListPage.vue | 扩展 | Mode 筛选；调仓单概要 |
| pages/ApprovalDetailPage.vue | 重构 | Mode B 逐行修改；约束实时验证 |
| pages/DecisionDetailPage.vue | 重构 | 因子归因卡片；Mode B 调仓单视图 |
| pages/BacktestPage.vue | 扩展 | 模式选择；信号来源标注 |
| pages/GraphPage.vue | 扩展 | 因子/状态/收益展示 |
| pages/RulesPage.vue | 扩展 | Agent权重 Tab；风控事件 Tab |
| pages/FactorsPage.vue | 新增 | |
| pages/StrategyPage.vue | 新增 | |
| pages/DecisionListPage.vue | 新增 | |
| pages/WeightManagementPage.vue | 合并删除 | 功能合并进 RulesPage |
| router/index.ts | 更新 | 新增 /factors /strategy /decisions 路由 |
| api/decisions.ts | 重构 | Mode A/B 参数；/orders 端点 |
| api/approvals.ts | 重构 | Mode B modify |
| api/portfolio.ts | 扩展 | summary/performance/candidate |
| api/graph.ts | 更新 | 适配新 graph_nodes 字段 |
| api/factors.ts | 新增 | |
| api/strategy.ts | 新增 | |
| api/settlement.ts | 新增 | |
| types/decision.ts | 更新 | mode/rebalance_orders 字段 |
| types/factor.ts | 新增 | |
| types/strategy.ts | 新增 | |
| types/portfolio.ts | 扩展 | |

### 新增依赖

```
backend/requirements.txt：
  asyncmy==0.2.9
  apscheduler==3.10.4
  numpy==1.26.4
  pandas==2.2.1
  RestrictedPython==7.1

backend/.env 新增：
  DATABASE_URL=mysql+asyncmy://user:pass@host:3306/quant_ai
  FEATURE_PLATFORM_MODE=api          # api | db
  FEATURE_PLATFORM_API_URL=
  FEATURE_PLATFORM_API_KEY=
  FEATURE_PLATFORM_DB_URL=
  TRADING_CALENDAR_CACHE_DAYS=30
```

### 改造优先级与交付顺序

```
P0  基础层（其他一切依赖它）
  1. db/schema.sql + db/connection.py
  2. config.py 扩展
  3. services/feature_client.py
  4. models.py 降级为 TypedDict
  5. 种子数据初始化：向 agent_weight_configs 写入4个Agent默认行
     (technical/fundamental/news/sentiment，weight=0.25，is_locked=False)

P1  核心服务层
  5. services/factor_engine.py
  6. services/scheduler.py（接入 main.py lifespan）
  7. services/nav_calculator.py
  8. services/settlement.py

P2  API 层
  9. 现有路由迁移（decisions/approvals/portfolio/risk/rules）
  10. 新路由（factors/strategy/candidate/settlement）

P3  Agent 层
  11. agents/pipeline.py 重写
  12. 4 个 Agent 重构

P4  前端层
  13. 新页面（Factors/Strategy/DecisionList）
  14. 重构页面（Dashboard/Analyze/Portfolio/Approval/Decision）

P5  回测层
  15. services/backtest.py 重写

P6  迭代层（脚手架，最后交付）
  16. services/factor_discovery.py
  17. services/strategy_evolution.py
```

---

## 测试策略

```
单元测试（test_units.py）
  mock db 层，不依赖真实 DB
  覆盖：IC计算逻辑、结算判断、组合优化器、market_regime 识别

集成测试（test_api.py）
  依赖测试 MySQL 库（quant_ai_test）
  CI 通过 Docker Compose 启动 MySQL 容器
  覆盖：Mode A/B 触发、审批流程、因子快照查询
```

---

*核心原则：因子有统计依据（Layer 1）→ Agent 做有据可查的推理 → 决策可溯源到具体因子 → 结果回填图谱 → 驱动策略演进（Layer 2/3）。顺序不能颠倒。*
