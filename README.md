# Quant AI — Multi-Agent 量化交易系统

基于多 LLM Agent 协作的量化交易决策平台，支持技术/基本面/新闻/情绪四维分析、人工审批工作流、风控熔断机制与历史回测。

---

## 项目结构

```
fullproject/
├── frontend/          # Vue 3 + TypeScript 前端
│   ├── src/
│   │   ├── pages/         # 页面组件（Dashboard、Analyze、Approvals 等）
│   │   ├── components/    # 通用 UI 与业务组件
│   │   ├── api/           # Axios API 封装
│   │   ├── types/         # TypeScript 类型定义
│   │   ├── composables/   # Vue Composables
│   │   ├── store/         # Pinia 状态管理
│   │   ├── router/        # Vue Router
│   │   └── styles/        # 全局样式 & CSS 变量
│   ├── index.html
│   ├── vite.config.ts
│   └── package.json
│
├── backend/           # FastAPI + SQLAlchemy 后端
│   ├── main.py            # 应用入口、路由注册、WebSocket
│   ├── config.py          # 环境变量配置
│   ├── database.py        # 数据库连接 & 初始化
│   ├── models.py          # SQLAlchemy ORM 模型
│   ├── schemas.py         # Pydantic 请求/响应 Schema
│   ├── websocket_manager.py  # WebSocket 广播管理
│   ├── agents/
│   │   ├── base.py        # LLM 客户端抽象（支持 Mock/OpenAI/Anthropic）
│   │   └── pipeline.py    # 6-Agent 编排流水线
│   ├── services/
│   │   ├── backtest.py    # 回测引擎（含手续费/滑点/买持基准）
│   │   ├── graph.py       # 经验图谱服务
│   │   └── risk.py        # 风控服务（熔断/紧急停止）
│   ├── routers/
│   │   ├── decisions.py   # /api/v1/decisions
│   │   ├── approvals.py   # /api/v1/approvals
│   │   ├── backtest.py    # /api/v1/backtest
│   │   ├── risk.py        # /api/v1/risk
│   │   ├── rules.py       # /api/v1/rules
│   │   └── graph.py       # /api/v1/graph
│   ├── requirements.txt
│   └── .env.example
│
└── README.md
```

---

## 快速启动

### 环境要求

| 工具 | 版本 |
|------|------|
| Python | 3.11+ |
| Node.js | 18+ |
| npm | 9+ |

---

### 1. 启动后端

```bash
cd backend

# 1-1. 创建并激活虚拟环境
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows

# 1-2. 安装依赖
pip install -r requirements.txt
# SQLite 异步驱动（必须）
pip install aiosqlite

# 1-3. 配置环境变量
cp .env.example .env
# 编辑 .env，选择 LLM Provider（默认 mock，不需要 API Key 也能运行）

# 1-4. 启动服务（默认端口 8000）
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

后端启动后访问：
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

---

### 2. 启动前端

```bash
cd frontend

# 2-1. 安装依赖
npm install

# 2-2. 配置环境变量（可选，开发环境通过 vite proxy 已自动代理）
cp .env.example .env

# 2-3. 启动开发服务器（默认端口 5173）
npm run dev
```

打开浏览器访问：**http://localhost:5173**

---

### 3. LLM 配置说明

编辑 `backend/.env` 文件，三种模式任选一：

```env
# 模式 1：Mock（默认，无需 API Key，系统自动生成模拟信号）
LLM_PROVIDER=mock

# 模式 2：OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx
LLM_MODEL=gpt-4o

# 模式 3：Anthropic Claude
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
LLM_MODEL=claude-sonnet-4-6
```

**Mock 模式说明**：无需任何 API Key，系统使用随机权重生成模拟 Agent 信号，所有功能（分析触发、审批流程、风控、回测、图谱）均正常运行，适合开发和演示使用。

---

### 4. 生产构建

```bash
# 构建前端静态文件
cd frontend
npm run build
# 产物在 frontend/dist/

# 后端生产启动（关闭 reload，启用多 worker）
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
```

---

## 核心功能说明

### Agent 分析流水线（`/analyze`）

1. 用户输入标的代码（如 `AAPL`）点击「开始分析」
2. 系统并发启动 4 个分析师 Agent：技术分析师、基本面分析师、新闻分析师、情绪分析师
3. 风险管理员 Agent 执行硬性风控规则校验（不受 LLM 输出影响）
4. 交易执行员 Agent 汇总加权投票输出最终 buy/sell/hold 决策
5. 每个 Agent 的输出经幻觉检测（最多重试 3 次），重试次数显示在信号卡片上
6. 分析完成后自动创建审批记录，等待人工审批

### 风控体系（`/rules`）

- **硬性风控参数**（代码规则强制执行，优先级高于一切 Agent 信号）
  - 单标的仓位上限（默认 20%）
  - 日内净值下跌警告线 L1（默认 3%）
  - 日内净值下跌暂停线 L2（默认 6%，需人工重置）
  - 最大回撤紧急停止线 L3（默认 15%）
- **自动审批规则**（满足条件时跳过人工审批）
- **熔断重置**：L1 自动触发，L2/L3 需在规则页面人工授权重置

### 回测引擎（`/backtest`）

- 支持多标的、自定义区间、手续费率（默认千三）、滑点（默认 0.1%）
- 对比基准支持：买持（Buy & Hold）/ 等权 / 市值加权
- 输出 6 项核心指标：累计收益率、年化收益率、夏普比率、最大回撤、胜率、平均持仓天数
- 提供净值曲线图、月度收益热力图、交易成本明细

### 紧急停止密码

开发环境默认密码：`admin123`（生产环境请修改 `services/risk.py` 中的验证逻辑）

---

## API 端点一览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/decisions/trigger | 触发 Agent 分析 |
| GET  | /api/v1/decisions/ | 分析记录列表 |
| GET  | /api/v1/decisions/{id} | 分析详情（含 Agent 信号）|
| GET  | /api/v1/approvals/ | 审批列表（支持状态筛选）|
| GET  | /api/v1/approvals/{id} | 审批详情 |
| POST | /api/v1/approvals/{id}/action | 通过/拒绝审批 |
| PUT  | /api/v1/approvals/{id}/modify | 修改权重后批准 |
| POST | /api/v1/backtest/ | 提交回测任务 |
| GET  | /api/v1/backtest/{id} | 查询回测结果 |
| GET  | /api/v1/risk/status | 风控状态（熔断等级）|
| GET  | /api/v1/risk/params | 风控参数 |
| PUT  | /api/v1/risk/params | 更新风控参数 |
| POST | /api/v1/risk/circuit-breaker/reset | 重置熔断等级 |
| POST | /api/v1/risk/emergency-stop/activate | 激活紧急停止 |
| POST | /api/v1/risk/emergency-stop/deactivate | 解除紧急停止 |
| GET  | /api/v1/rules/ | 自动审批规则列表 |
| POST | /api/v1/rules/ | 创建规则 |
| PUT  | /api/v1/rules/{id} | 更新规则 |
| POST | /api/v1/rules/{id}/toggle | 启用/禁用规则 |
| GET  | /api/v1/graph/stats | 经验图谱统计 |
| GET  | /api/v1/graph/nodes | 图谱节点列表 |
| WS   | /ws | WebSocket 实时推送 |

---

## 常见问题

**Q: 启动报 `ModuleNotFoundError: No module named 'aiosqlite'`**
```bash
pip install aiosqlite
```

**Q: 前端显示"连接断开"**
确认后端已启动在 8000 端口，且 `vite.config.ts` 中 proxy 配置正确。

**Q: 分析一直显示"分析中"不结束**
检查后端日志，如果使用 OpenAI/Anthropic 请确认 API Key 有效。Mock 模式下通常 3-5 秒内完成。

**Q: 回测一直是 pending 状态**
回测使用 `asyncio.create_task` 后台执行，确保后端日志无报错。如需调试可直接调用 `services/backtest.run_backtest()`。
