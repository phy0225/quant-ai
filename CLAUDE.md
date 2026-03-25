# Quant AI — Claude Code 项目说明

## 项目简介
多 Agent 量化交易辅助平台。4个 AI 分析师（技术/基本面/新闻/情绪）协作分析 A 股标的，
输出交易信号，经人工审批后更新持仓。

## 技术栈
- **后端**：Python 3.11 + FastAPI + SQLAlchemy (async) + SQLite
- **前端**：Vue 3 + TypeScript + Vite + TailwindCSS
- **数据**：AKShare（A 股行情/财务/新闻）
- **AI**：任意 OpenAI 兼容 API（默认 Mock 模式）

## 目录结构
```
sdd_full/
├── backend/
│   ├── agents/          # Agent 实现
│   │   ├── cn_technical_agent.py    # 技术分析（纯规则引擎）
│   │   ├── cn_fundamental_agent.py  # 基本面（AKShare 财务数据）
│   │   ├── cn_news_agent.py         # 新闻（东方财富）
│   │   ├── cn_sentiment_agent.py    # 情绪（东财评分+北向+涨跌停）
│   │   ├── pipeline.py              # 调度与加权投票
│   │   ├── portfolio_context.py     # 持仓上下文格式化
│   │   └── base.py                  # LLM 客户端（支持 Mock）
│   ├── routers/         # FastAPI 路由
│   │   ├── decisions.py    # 触发分析、查询决策
│   │   ├── approvals.py    # 审批流程
│   │   ├── portfolio.py    # 持仓管理
│   │   ├── risk.py         # 风控配置
│   │   ├── rules.py        # 自动审批规则
│   │   ├── backtest.py     # 回测
│   │   └── graph.py        # 经验图谱
│   ├── services/        # 外部数据服务
│   │   ├── cn_market_data.py       # AKShare 行情（async）
│   │   ├── cn_fundamental_data.py  # AKShare 财务（async）
│   │   ├── cn_news_data.py         # AKShare 新闻（async）
│   │   └── cn_sentiment_data.py    # AKShare 情绪数据（async）
│   ├── models.py        # SQLAlchemy ORM 模型
│   ├── schemas.py       # Pydantic 请求/响应模型
│   ├── database.py      # 数据库连接和初始化
│   ├── config.py        # 配置（从 .env 读取）
│   ├── main.py          # FastAPI 应用入口
│   └── tests/           # 测试目录
│       ├── conftest.py      # 测试夹具（内存数据库）
│       ├── test_api.py      # API 集成测试
│       └── test_units.py    # 单元测试
└── frontend/
    └── src/
        ├── pages/       # 页面组件
        ├── components/  # 通用组件
        ├── api/         # API 调用层
        ├── types/       # TypeScript 类型定义
        └── router/      # Vue Router 路由配置
```

## 关键业务流程
```
持仓页 → 触发分析（传入标的+持仓）
    → Pipeline 运行 4 个 Agent（各自调 AKShare 拿数据）
    → 加权投票得出 final_direction
    → 创建 ApprovalRecord（status=pending）
    → 审批页 通过/拒绝/修改权重
    → 审批通过 → 更新 PortfolioHolding 表 + 保存快照
```

## 开发命令

### 后端
```powershell
cd backend

# 启动（开发模式）
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 运行所有测试
pytest tests/ -v

# 只跑单元测试（快，无网络依赖）
pytest tests/test_units.py -v

# 只跑 API 测试
pytest tests/test_api.py -v

# 安装测试依赖
pip install -r requirements-test.txt
```

### 前端
```powershell
cd frontend

# 启动
npm run dev

# TypeScript 类型检查
npx tsc --noEmit

# 构建验证
npm run build
```

## 代码规范

### Python / 后端
1. **AKShare 是同步库**，所有调用必须用 `asyncio.to_thread()` 包裹
   ```python
   # ✅ 正确
   async def fetch_something(symbol):
       return await asyncio.to_thread(_fetch_sync, symbol)

   # ❌ 错误 — 会阻塞事件循环
   async def fetch_something(symbol):
       return ak.some_function(symbol)
   ```

2. **AKShare 接口名经常变**，必须做多接口兜底
   ```python
   for func_name in ["new_name", "old_name"]:
       func = getattr(ak, func_name, None)
       if func:
           try: result = func(...); break
           except: continue
   ```

3. **Agent 无数据时**不得调 LLM 编造方向，必须返回 `direction=hold, confidence<=0.25`

4. **新增数据库字段**必须同步更新 `models.py`，测试后确认 `conftest.py` 里的 fixture 能建表

5. **所有路由**必须在 `schemas.py` 里有对应 Pydantic 模型

6. **时间统一用** `datetime.now()`（本地时间），不用 `datetime.utcnow()`

### TypeScript / 前端
1. 新增页面必须在 `router/index.ts` 注册路由
2. API 调用统一放 `src/api/` 目录，不在组件里直接 fetch
3. 新增类型必须在 `src/types/` 里定义

## 配置文件说明
```
backend/.env          # 实际配置（不提交 git）
backend/.env.example  # 配置模板

关键配置项：
  LLM_API_URL=         # 留空用 OpenAI 官方
  LLM_API_KEY=         # 留空启用 Mock 模式
  LLM_MODEL=gpt-4o
  DATA_PROVIDER=akshare  # akshare | tushare | mock
  TUSHARE_TOKEN=         # DATA_PROVIDER=tushare 时填
  DATABASE_URL=sqlite:///./quant_ai.db
```

## 当前已知问题和技术债
- `main.py` 中 `portfolio` router 被 include 了两次（重复导入），需修复
- AKShare 部分接口（北向资金、股评）有时返回格式与文档不符，接口调用失败时已做降级处理
- 回测引擎目前使用 GBM 随机模拟，非真实历史信号回放（迭代计划 v3.1）
- `_make_recommendations` 中调仓幅度使用随机数（迭代计划 v5.x）

## 测试注意事项
- 所有测试使用内存 SQLite，不依赖外部网络
- AKShare 调用在单元测试中用 `unittest.mock.patch` mock 掉
- `sample_approval` fixture 直接插 SQL 避免等待 pipeline 执行
- 测试数据库通过 `conftest.py` 的 `db_engine` fixture 自动创建和销毁

## 迭代需求文档位置
```
sdd_full/迭代计划.md    # 完整迭代规划（v2.0 ~ v8.0）
```
