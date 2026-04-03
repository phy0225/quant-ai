# Quant Platform v3 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Quant Platform v3 as a real research-to-decision closed loop with MySQL storage, Layer 1 factor snapshots, factor-aware agents, dual decision modes, stock-only execution, real backtesting, and T+5 settlement.

**Architecture:** Replace the current SQLite/SQLAlchemy-centered demo flow with a MySQL query-layer architecture built around `decision_runs`, `agent_signals`, `rebalance_orders`, `daily_factor_snapshots`, and `agent_performance`. Keep research inputs multi-entity (`stock`, `industry`, `concept`, `market`) while constraining execution, approvals, holdings, NAV, and settlement to stocks only. Deliver Layer 2/3 as visible manual-entry task systems, not autonomous production loops.

**Tech Stack:** FastAPI, Vue 3, TypeScript, MySQL, asyncmy, APScheduler, pytest, Vite

---

## File Structure

### Backend data and infrastructure

- Create: `backend/db/schema.sql`
- Create: `backend/db/connection.py`
- Create: `backend/db/queries/decisions.py`
- Create: `backend/db/queries/approvals.py`
- Create: `backend/db/queries/factors.py`
- Create: `backend/db/queries/portfolio.py`
- Create: `backend/db/queries/strategy.py`
- Create: `backend/db/queries/graph.py`
- Create: `backend/db/queries/risk.py`
- Create: `backend/db/queries/settlement.py`
- Create: `backend/db/queries/backtest.py`
- Create: `backend/db/queries/agent_weights.py`
- Create: `backend/db/queries/nav_history.py`
- Modify: `backend/config.py`
- Modify: `backend/main.py`
- Modify: `backend/database.py`

### Backend services

- Create: `backend/services/feature_client.py`
- Create: `backend/services/factor_engine.py`
- Create: `backend/services/nav_calculator.py`
- Create: `backend/services/settlement.py`
- Create: `backend/services/scheduler.py`
- Create: `backend/services/factor_discovery.py`
- Create: `backend/services/strategy_evolution.py`
- Modify: `backend/services/backtest.py`
- Modify: `backend/services/graph.py`

### Backend decision engine

- Create: `backend/agents/factor_context.py`
- Modify: `backend/agents/pipeline.py`
- Modify: `backend/agents/cn_technical_agent.py`
- Modify: `backend/agents/cn_fundamental_agent.py`
- Modify: `backend/agents/cn_news_agent.py`
- Modify: `backend/agents/cn_sentiment_agent.py`
- Modify: `backend/schemas.py`
- Modify: `backend/models.py`

### Backend routers

- Create: `backend/routers/features.py`
- Create: `backend/routers/factors.py`
- Create: `backend/routers/strategy.py`
- Create: `backend/routers/candidate.py`
- Create: `backend/routers/settlement.py`
- Modify: `backend/routers/decisions.py`
- Modify: `backend/routers/approvals.py`
- Modify: `backend/routers/portfolio.py`
- Modify: `backend/routers/rules.py`
- Modify: `backend/routers/risk.py`
- Modify: `backend/routers/backtest.py`
- Modify: `backend/routers/graph.py`

### Frontend pages and APIs

- Create: `frontend/src/pages/FactorsPage.vue`
- Create: `frontend/src/pages/StrategyPage.vue`
- Create: `frontend/src/pages/DecisionListPage.vue`
- Create: `frontend/src/api/factors.ts`
- Create: `frontend/src/api/strategy.ts`
- Create: `frontend/src/api/settlement.ts`
- Create: `frontend/src/types/factor.ts`
- Create: `frontend/src/types/strategy.ts`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/ui/Sidebar.vue`
- Modify: `frontend/src/pages/DashboardPage.vue`
- Modify: `frontend/src/pages/PortfolioPage.vue`
- Modify: `frontend/src/pages/AnalyzePage.vue`
- Modify: `frontend/src/pages/ApprovalListPage.vue`
- Modify: `frontend/src/pages/ApprovalDetailPage.vue`
- Modify: `frontend/src/pages/DecisionDetailPage.vue`
- Modify: `frontend/src/pages/BacktestPage.vue`
- Modify: `frontend/src/pages/GraphPage.vue`
- Modify: `frontend/src/pages/RulesPage.vue`
- Modify: `frontend/src/api/decisions.ts`
- Modify: `frontend/src/api/approvals.ts`
- Modify: `frontend/src/api/portfolio.ts`
- Modify: `frontend/src/api/graph.ts`
- Modify: `frontend/src/types/decision.ts`
- Modify: `frontend/src/types/portfolio.ts`

### Tests

- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_api.py`
- Modify: `backend/tests/test_units.py`
- Create: `backend/tests/test_factor_engine.py`
- Create: `backend/tests/test_settlement.py`
- Create: `backend/tests/test_backtest_modes.py`
- Create: `backend/tests/test_mode_b_pipeline.py`

---

## Chunk 1: Data Foundation

### Task 1: Create MySQL schema and connection layer

**Files:**
- Create: `backend/db/schema.sql`
- Create: `backend/db/connection.py`
- Modify: `backend/config.py`
- Test: `backend/tests/conftest.py`

- [x] **Step 1: Write the failing config test**

```python
def test_mysql_config_has_required_fields(settings):
    assert settings.db_host
    assert settings.db_port == 3306
    assert settings.db_user
    assert settings.db_name
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend; pytest tests/conftest.py -v`
Expected: FAIL with missing MySQL settings or missing fixture attributes

- [x] **Step 3: Add MySQL config and connection primitives**

```python
class Settings(BaseSettings):
    db_host: str
    db_port: int = 3306
    db_user: str
    db_password: str = ""
    db_name: str

async def create_pool():
    return await asyncmy.create_pool(...)
```

- [x] **Step 4: Add initial schema**

```sql
CREATE TABLE decision_runs (...);
CREATE TABLE agent_signals (...);
CREATE TABLE rebalance_orders (...);
CREATE TABLE daily_factor_snapshots (...);
CREATE TABLE agent_performance (...);
```

- [x] **Step 5: Run config test and basic schema smoke test**

Run: `cd backend; pytest tests/conftest.py -v`
Expected: PASS

- [x] **Step 6: Commit**

```bash
git add backend/config.py backend/db/schema.sql backend/db/connection.py backend/tests/conftest.py
git commit -m "feat: add mysql schema and connection layer"
```

### Task 2: Create query modules for the new business model

**Files:**
- Create: `backend/db/queries/decisions.py`
- Create: `backend/db/queries/approvals.py`
- Create: `backend/db/queries/factors.py`
- Create: `backend/db/queries/portfolio.py`
- Create: `backend/db/queries/strategy.py`
- Create: `backend/db/queries/graph.py`
- Create: `backend/db/queries/risk.py`
- Create: `backend/db/queries/settlement.py`
- Create: `backend/db/queries/backtest.py`
- Create: `backend/db/queries/agent_weights.py`
- Create: `backend/db/queries/nav_history.py`
- Test: `backend/tests/test_units.py`

- [x] **Step 1: Write failing repository tests**

```python
def test_insert_and_fetch_decision_run(query_helpers):
    decision_id = query_helpers.insert_decision_run(mode="targeted", symbols=["600036"])
    row = query_helpers.get_decision_run(decision_id)
    assert row["mode"] == "targeted"
```

- [x] **Step 2: Run the repository tests to verify they fail**

Run: `cd backend; pytest tests/test_units.py -k decision_run -v`
Expected: FAIL with import or function not found

- [x] **Step 3: Implement focused query modules**

```python
async def insert_decision_run(conn, payload): ...
async def list_approvals(conn, status=None): ...
async def get_factor_snapshot(conn, trade_date): ...
```

- [x] **Step 4: Re-run repository tests**

Run: `cd backend; pytest tests/test_units.py -k decision_run -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add backend/db/queries backend/tests/test_units.py
git commit -m "feat: add mysql query modules for v3 domain"
```

---

## Chunk 2: Feature and Factor Foundation

### Task 3: Implement feature client for multi-entity reads

**Files:**
- Create: `backend/services/feature_client.py`
- Modify: `backend/config.py`
- Test: `backend/tests/test_units.py`

- [x] **Step 1: Write the failing service test**

```python
@pytest.mark.asyncio
async def test_feature_client_fetches_snapshot_for_multiple_entity_types(feature_client):
    result = await feature_client.fetch_snapshot(["600036"], "2026-04-02")
    assert "600036" in result
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend; pytest tests/test_units.py -k feature_client -v`
Expected: FAIL with service missing

- [x] **Step 3: Write minimal implementation**

```python
class FeatureClient:
    async def fetch_snapshot(self, symbols, date, fields=None): ...
    async def fetch_market(self, date): ...
    async def fetch_industry(self, date): ...
    async def fetch_concept(self, date): ...
```

- [x] **Step 4: Re-run feature client tests**

Run: `cd backend; pytest tests/test_units.py -k feature_client -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add backend/services/feature_client.py backend/config.py backend/tests/test_units.py
git commit -m "feat: add feature client for multi-entity data access"
```

### Task 4: Implement Layer 1 factor engine and daily snapshots

**Files:**
- Create: `backend/services/factor_engine.py`
- Create: `backend/tests/test_factor_engine.py`
- Create: `backend/routers/factors.py`
- Create: `backend/db/queries/factors.py`
- Test: `backend/tests/test_factor_engine.py`

- [x] **Step 1: Write the failing factor engine test**

```python
@pytest.mark.asyncio
async def test_run_daily_creates_factor_snapshot(factor_engine, seeded_feature_history):
    snapshot = await factor_engine.run_daily("2026-04-02")
    assert snapshot["trade_date"] == "2026-04-02"
    assert "effective_factors" in snapshot
```

- [x] **Step 2: Run the factor engine test to verify it fails**

Run: `cd backend; pytest tests/test_factor_engine.py -v`
Expected: FAIL with module not found

- [x] **Step 3: Implement minimal factor engine**

```python
IC_THRESHOLD = 0.03
IC_IR_THRESHOLD = 0.40

async def run_daily(trade_date: str):
    history = ...
    effective = ...
    regime = _detect_regime(...)
    return {"trade_date": trade_date, "effective_factors": effective, "market_regime": regime}
```

- [x] **Step 4: Add factor API read path**

```python
@router.get("/daily")
async def get_daily_factor_snapshot(date: str): ...
```

- [x] **Step 5: Re-run factor engine tests**

Run: `cd backend; pytest tests/test_factor_engine.py -v`
Expected: PASS

- [x] **Step 6: Commit**

```bash
git add backend/services/factor_engine.py backend/tests/test_factor_engine.py backend/routers/factors.py backend/db/queries/factors.py
git commit -m "feat: add layer1 factor engine and snapshot api"
```

### Task 5: Add scheduler, NAV calculator, and daily jobs

**Files:**
- Create: `backend/services/nav_calculator.py`
- Create: `backend/services/scheduler.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_units.py`

- [x] **Step 1: Write the failing scheduler smoke test**

```python
def test_scheduler_registers_factor_nav_and_settlement_jobs():
    jobs = build_scheduler().get_jobs()
    assert any(job.id == "factor_engine_daily" for job in jobs)
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend; pytest tests/test_units.py -k scheduler -v`
Expected: FAIL

- [x] **Step 3: Implement scheduler and NAV calculator**

```python
def build_scheduler():
    scheduler.add_job(...)
    return scheduler
```

- [x] **Step 4: Wire scheduler into FastAPI lifespan**

```python
@asynccontextmanager
async def lifespan(app):
    scheduler.start()
    yield
    scheduler.shutdown()
```

- [x] **Step 5: Re-run scheduler tests**

Run: `cd backend; pytest tests/test_units.py -k scheduler -v`
Expected: PASS

- [x] **Step 6: Commit**

```bash
git add backend/services/nav_calculator.py backend/services/scheduler.py backend/main.py backend/tests/test_units.py
git commit -m "feat: add daily scheduler and nav calculator"
```

---

## Chunk 3: Decision Engine and APIs

### Task 6: Define v3 request/response schemas and mode-aware router models

**Files:**
- Modify: `backend/schemas.py`
- Modify: `backend/routers/decisions.py`
- Test: `backend/tests/test_api.py`

- [x] **Step 1: Write failing API schema tests**

```python
def test_decision_trigger_accepts_targeted_mode(api_client):
    response = api_client.post("/api/v1/decisions/trigger", json={"mode": "targeted", "symbols": ["600036"]})
    assert response.status_code != 422
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend; pytest tests/test_api.py -k targeted_mode -v`
Expected: FAIL with validation mismatch

- [x] **Step 3: Add mode-aware schemas**

```python
class DecisionTriggerRequest(BaseModel):
    mode: Literal["targeted", "rebalance"]
    symbols: list[str] | None = None
    candidate_symbols: list[str] | None = None
```

- [x] **Step 4: Re-run schema tests**

Run: `cd backend; pytest tests/test_api.py -k targeted_mode -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add backend/schemas.py backend/routers/decisions.py backend/tests/test_api.py
git commit -m "feat: add mode-aware decision schemas"
```

### Task 7: Build factor context and refactor the pipeline for deterministic outputs

**Files:**
- Create: `backend/agents/factor_context.py`
- Modify: `backend/agents/pipeline.py`
- Modify: `backend/agents/cn_technical_agent.py`
- Modify: `backend/agents/cn_fundamental_agent.py`
- Modify: `backend/agents/cn_news_agent.py`
- Modify: `backend/agents/cn_sentiment_agent.py`
- Create: `backend/tests/test_mode_b_pipeline.py`

- [x] **Step 1: Write the failing deterministic pipeline test**

```python
@pytest.mark.asyncio
async def test_mode_b_same_input_produces_same_rebalance_orders(run_pipeline):
    first = await run_pipeline(...)
    second = await run_pipeline(...)
    assert first["orders"] == second["orders"]
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend; pytest tests/test_mode_b_pipeline.py -v`
Expected: FAIL because current pipeline uses random weights

- [x] **Step 3: Implement factor context builder**

```python
async def build_factor_context(symbols, candidate_symbols=None, trade_date=None):
    return {"factor_date": trade_date, "scored_stocks": {...}, "market_regime": "..."}
```

- [x] **Step 4: Replace random recommendation logic**

```python
weight_delta = max_delta * abs(factor_score - 0.5) * 2 * avg_conf
```

- [x] **Step 5: Inject factor summaries into each agent**

```python
prompt_context["factor_context"] = context["factor_context"]
```

- [x] **Step 6: Re-run deterministic pipeline tests**

Run: `cd backend; pytest tests/test_mode_b_pipeline.py -v`
Expected: PASS

- [x] **Step 7: Commit**

```bash
git add backend/agents backend/tests/test_mode_b_pipeline.py
git commit -m "feat: refactor pipeline to use factor context and deterministic orders"
```

### Task 8: Implement mode-aware decision, approval, and candidate APIs

**Files:**
- Modify: `backend/routers/decisions.py`
- Modify: `backend/routers/approvals.py`
- Modify: `backend/routers/portfolio.py`
- Create: `backend/routers/candidate.py`
- Test: `backend/tests/test_task8_api.py`

- [x] **Step 1: Write the failing API tests for Mode B orders**

```python
def test_get_decision_orders_returns_stock_only_rows(api_client, completed_rebalance_run):
    response = api_client.get(f"/api/v1/decisions/{completed_rebalance_run}/orders")
    assert response.status_code == 200
    assert all("symbol" in row for row in response.json())
```

- [x] **Step 2: Run API tests to verify they fail**

Run: `cd backend; pytest tests/test_task8_api.py -v`
Expected: FAIL

- [x] **Step 3: Implement order and modify endpoints**

```python
@router.get("/{id}/orders")
async def get_orders(id: str): ...

@router.put("/{approval_id}/modify")
async def modify_orders(...): ...
```

- [x] **Step 4: Add candidate pool endpoints**

```python
@router.get("/")
async def list_candidates(): ...
```

- [x] **Step 5: Re-run API tests**

Run: `cd backend; pytest tests/test_task8_api.py -v`
Expected: PASS

- [x] **Step 6: Commit**

```bash
git add backend/routers/decisions.py backend/routers/approvals.py backend/routers/portfolio.py backend/routers/candidate.py backend/tests/test_api.py
git commit -m "feat: add mode b orders approvals and candidate pool apis"
```

---

## Chunk 4: Settlement, Graph, and Backtesting

### Task 9: Implement T+5 settlement and dynamic agent weights

**Files:**
- Create: `backend/services/settlement.py`
- Modify: `backend/routers/rules.py`
- Modify: `backend/routers/risk.py`
- Create: `backend/routers/settlement.py`
- Create: `backend/tests/test_settlement.py`

- [x] **Step 1: Write failing settlement tests**

```python
@pytest.mark.asyncio
async def test_settlement_marks_agent_correctness(settlement_service, pending_agent_performance):
    result = await settlement_service.run("2026-04-08")
    assert result["settled_count"] > 0
```

- [x] **Step 2: Run settlement tests to verify they fail**

Run: `cd backend; pytest tests/test_settlement.py -v`
Expected: FAIL

- [x] **Step 3: Implement settlement service**

```python
async def run(settle_date: str):
    pending = ...
    updated = ...
    return {"settled_count": len(updated)}
```

- [x] **Step 4: Add rules endpoint for agent weights**

```python
@router.get("/agent-weights")
async def get_agent_weights(): ...
```

- [x] **Step 5: Re-run settlement tests**

Run: `cd backend; pytest tests/test_settlement.py tests/test_task10_graph.py tests/test_backtest_modes.py -v`
Expected: PASS

- [x] **Step 6: Commit**

```bash
git add backend/services/settlement.py backend/routers/rules.py backend/routers/risk.py backend/routers/settlement.py backend/tests/test_settlement.py
git commit -m "feat: add t-plus-5 settlement and dynamic agent weights"
```

### Task 10: Extend graph nodes to capture factor-aware outcomes

**Files:**
- Modify: `backend/services/graph.py`
- Modify: `backend/routers/graph.py`
- Test: `backend/tests/test_task10_graph.py`

- [x] **Step 1: Write the failing graph test**

```python
def test_graph_node_contains_mode_and_factor_snapshot(api_client, approved_rebalance_node):
    response = api_client.get("/api/v1/graph/nodes")
    first = response.json()["items"][0]
    assert "mode" in first
    assert "factor_snapshot" in first
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend; pytest tests/test_task10_graph.py -v`
Expected: FAIL

- [x] **Step 3: Update graph write/read models**

```python
node = {
    "mode": approval.mode,
    "factor_snapshot": snapshot,
    "market_regime": regime,
}
```

- [x] **Step 4: Re-run graph tests**

Run: `cd backend; pytest tests/test_task10_graph.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
  git add backend/services/graph.py backend/routers/graph.py backend/tests/test_task10_graph.py
git commit -m "feat: extend graph nodes with factor-aware metadata"
```

### Task 11: Replace mock backtest with signal-based and factor-based modes

**Files:**
- Modify: `backend/services/backtest.py`
- Modify: `backend/routers/backtest.py`
- Create: `backend/tests/test_backtest_modes.py`

- [x] **Step 1: Write failing backtest mode tests**

```python
def test_signal_based_backtest_uses_historical_decisions(backtest_service):
    result = backtest_service.run_backtest(..., backtest_mode="signal_based")
    assert result["mode"] == "signal_based"
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd backend; pytest tests/test_backtest_modes.py -v`
Expected: FAIL

- [x] **Step 3: Implement signal-based and factor-based paths**

```python
async def _run_signal_based(...): ...
async def _run_factor_based(...): ...
def _run_simulation(...): ...
```

- [x] **Step 4: Update router to pass mode**

```python
metrics = await run_backtest(..., backtest_mode=payload.backtest_mode)
```

- [x] **Step 5: Re-run backtest tests**

Run: `cd backend; pytest tests/test_settlement.py tests/test_task10_graph.py tests/test_backtest_modes.py -v`
Expected: PASS

- [x] **Step 6: Commit**

```bash
git add backend/services/backtest.py backend/routers/backtest.py backend/tests/test_backtest_modes.py
git commit -m "feat: add real signal-based and factor-based backtests"
```

---

## Chunk 5: Frontend Productization

### Task 12: Add routes and navigation for Decisions, Factors, and Strategy

**Files:**
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/ui/Sidebar.vue`
- Create: `frontend/src/pages/DecisionListPage.vue`
- Create: `frontend/src/pages/FactorsPage.vue`
- Create: `frontend/src/pages/StrategyPage.vue`
- Test: `frontend/package.json`

- [x] **Step 1: Write the failing route smoke expectation in plan notes**

```ts
// expected routes
"/decisions"
"/factors"
"/strategy"
```

- [x] **Step 2: Run build to confirm current routes are incomplete**

Run: `cd frontend; npm run build`
Expected: Existing build passes, but new pages/routes do not exist yet

- [x] **Step 3: Add the new routes and page stubs**

```ts
{ path: "/decisions", component: () => import("@/pages/DecisionListPage.vue") }
```

- [x] **Step 4: Re-run frontend build**

Run: `cd frontend; npm run build`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add frontend/src/router/index.ts frontend/src/components/ui/Sidebar.vue frontend/src/pages/DecisionListPage.vue frontend/src/pages/FactorsPage.vue frontend/src/pages/StrategyPage.vue
git commit -m "feat: add decisions factors and strategy navigation"
```

### Task 13: Rebuild Analyze for Mode A and Mode B

**Files:**
- Modify: `frontend/src/pages/AnalyzePage.vue`
- Modify: `frontend/src/api/decisions.ts`
- Modify: `frontend/src/types/decision.ts`

- [x] **Step 1: Write a failing interface expectation**

```ts
type DecisionTriggerRequest = {
  mode: "targeted" | "rebalance"
}
```

- [x] **Step 2: Run build to surface type mismatch**

Run: `cd frontend; npm run build`
Expected: FAIL after introducing the new API contract until the page is updated

- [x] **Step 3: Implement tabbed mode-aware Analyze page**

```vue
<button @click="mode = 'targeted'">鐎规艾鎮滈崚鍡樼€?/button>
<button @click="mode = 'rebalance'">缂佸嫬鎮庣拫鍐х波</button>
```

- [x] **Step 4: Re-run build**

Run: `cd frontend; npm run build`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add frontend/src/pages/AnalyzePage.vue frontend/src/api/decisions.ts frontend/src/types/decision.ts
git commit -m "feat: rebuild analyze page for targeted and rebalance modes"
```

### Task 14: Rebuild decision, approval, portfolio, and dashboard views

**Files:**
- Modify: `frontend/src/pages/DashboardPage.vue`
- Modify: `frontend/src/pages/PortfolioPage.vue`
- Modify: `frontend/src/pages/ApprovalListPage.vue`
- Modify: `frontend/src/pages/ApprovalDetailPage.vue`
- Modify: `frontend/src/pages/DecisionDetailPage.vue`
- Modify: `frontend/src/api/approvals.ts`
- Modify: `frontend/src/api/portfolio.ts`
- Modify: `frontend/src/types/portfolio.ts`

- [x] **Step 1: Introduce the failing API shape assumptions**

```ts
type RebalanceOrder = {
  symbol: string
  target_weight: number
}
```

- [x] **Step 2: Run build to verify the current pages do not satisfy new shapes**

Run: `cd frontend; npm run build`
Expected: FAIL or require page updates once new types are wired in

- [x] **Step 3: Update portfolio and approvals to stock-only execution semantics**

```vue
<tr v-for="order in rebalanceOrders" :key="order.symbol">
```

- [x] **Step 4: Update dashboard and decision detail to display factor and accuracy cards**

```vue
<StatusCard title="閺堝鏅ラ崶鐘茬摍" :value="effectiveFactorCount" />
```

- [x] **Step 5: Re-run build**

Run: `cd frontend; npm run build`
Expected: PASS

- [x] **Step 6: Commit**

```bash
git add frontend/src/pages/DashboardPage.vue frontend/src/pages/PortfolioPage.vue frontend/src/pages/ApprovalListPage.vue frontend/src/pages/ApprovalDetailPage.vue frontend/src/pages/DecisionDetailPage.vue frontend/src/api/approvals.ts frontend/src/api/portfolio.ts frontend/src/types/portfolio.ts
git commit -m "feat: rebuild dashboard portfolio approvals and decision detail for v3"
```

### Task 15: Add factor, strategy, rules, graph, and backtest product views

**Files:**
- Create: `frontend/src/api/factors.ts`
- Create: `frontend/src/api/strategy.ts`
- Create: `frontend/src/api/settlement.ts`
- Create: `frontend/src/types/factor.ts`
- Create: `frontend/src/types/strategy.ts`
- Modify: `frontend/src/pages/BacktestPage.vue`
- Modify: `frontend/src/pages/GraphPage.vue`
- Modify: `frontend/src/pages/RulesPage.vue`

- [x] **Step 1: Write the failing type stubs in the new API modules**

```ts
export interface FactorSnapshotResponse {
  trade_date: string
  effective_factors: Array<{ factor_key: string; ic_ir: number }>
}
```

- [x] **Step 2: Run build to verify missing modules**

Run: `cd frontend; npm run build`
Expected: FAIL until modules and imports are complete

- [x] **Step 3: Implement factor and strategy API clients and views**

```ts
export const factorsApi = { daily: (...) => apiClient.get(...) }
```

- [x] **Step 4: Update Backtest, Graph, and Rules for v3 semantics**

```vue
<select v-model="backtestMode">
  <option value="signal_based">閸樺棗褰舵穱鈥冲娇</option>
</select>
```

- [x] **Step 5: Re-run build**

Run: `cd frontend; npm run build`
Expected: PASS

- [x] **Step 6: Commit**

```bash
git add frontend/src/api/factors.ts frontend/src/api/strategy.ts frontend/src/api/settlement.ts frontend/src/types/factor.ts frontend/src/types/strategy.ts frontend/src/pages/BacktestPage.vue frontend/src/pages/GraphPage.vue frontend/src/pages/RulesPage.vue
git commit -m "feat: add factor strategy and v3 validation views"
```

---

## Chunk 6: Layer 2/3 Occupancy and Final Validation

### Task 16: Add Layer 2 factor discovery manual task flow

**Files:**
- Create: `backend/services/factor_discovery.py`
- Modify: `backend/routers/factors.py`
- Modify: `frontend/src/pages/FactorsPage.vue`
- Test: `backend/tests/test_api.py`

- [x] **Step 1: Write the failing task creation test**

```python
def test_create_factor_discovery_task(api_client):
    response = api_client.post("/api/v1/factors/discover", json={"research_direction": "閾诲秷绁担娆擃杺娑撳氦鍋傛禒宄板彠缁?})
    assert response.status_code == 200
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend; pytest tests/test_api.py -k factor_discover -v`
Expected: FAIL

- [x] **Step 3: Add manual task service and API**

```python
async def run_discovery(research_direction: str, task_id: str): ...
```

- [x] **Step 4: Expose the task UI in Factors**

```vue
<textarea v-model="researchDirection" />
```

- [x] **Step 5: Re-run tests and frontend build**

Run: `cd backend; pytest tests/test_api.py -k factor_discover -v`
Expected: PASS

Run: `cd frontend; npm run build`
Expected: PASS

- [x] **Step 6: Commit**

```bash
git add backend/services/factor_discovery.py backend/routers/factors.py frontend/src/pages/FactorsPage.vue backend/tests/test_api.py
git commit -m "feat: add manual factor discovery task flow"
```

### Task 17: Add Layer 3 strategy evolution manual task flow

**Files:**
- Create: `backend/services/strategy_evolution.py`
- Modify: `backend/routers/strategy.py`
- Modify: `frontend/src/pages/StrategyPage.vue`
- Test: `backend/tests/test_api.py`

- [x] **Step 1: Write the failing strategy experiment test**

```python
def test_create_strategy_experiment(api_client):
    response = api_client.post("/api/v1/strategy/experiment", json={"base_version_id": "v1", "hypothesis": "increase factor weight"})
    assert response.status_code == 200
```

- [x] **Step 2: Run the test to verify it fails**

Run: `cd backend; pytest tests/test_api.py -k strategy_experiment -v`
Expected: FAIL

- [x] **Step 3: Implement manual experiment service and endpoints**

```python
async def run_evolution(base_version_id: str, experiment_id: str): ...
```

- [x] **Step 4: Add version and experiment views**

```vue
<button @click="createExperiment">閸掓稑缂撶€圭偤鐛?/button>
```

- [x] **Step 5: Re-run tests and frontend build**

Run: `cd backend; pytest tests/test_api.py -k strategy_experiment -v`
Expected: PASS

Run: `cd frontend; npm run build`
Expected: PASS

- [x] **Step 6: Commit**

```bash
git add backend/services/strategy_evolution.py backend/routers/strategy.py frontend/src/pages/StrategyPage.vue backend/tests/test_api.py
git commit -m "feat: add manual strategy evolution task flow"
```

### Task 18: Run full validation and prepare handoff

**Files:**
- Modify: `README.md`
- Modify: `docs/specs/2026-04-03-quant-platform-v3-design.md`
- Modify: `docs/superpowers/plans/2026-04-03-quant-platform-v3.md`

- [x] **Step 1: Run the backend suite**

Run: `cd backend; pytest tests/ -v`
Expected: PASS

- [x] **Step 2: Run the frontend build**

Run: `cd frontend; npm run build`
Expected: PASS

- [x] **Step 3: Run a manual smoke checklist**

```text
1. Trigger Mode A targeted analysis for a stock
2. Trigger Mode B rebalance for a portfolio
3. Modify an approval order
4. Run signal-based backtest
5. Trigger settlement
6. Open Factors and Strategy pages
```

- [x] **Step 4: Update documentation**

```markdown
- Add MySQL setup instructions
- Add feature platform env documentation
- Add v3 page and API summary
```

- [x] **Step 5: Commit**

```bash
git add README.md docs/specs/2026-04-03-quant-platform-v3-design.md docs/superpowers/plans/2026-04-03-quant-platform-v3.md
git commit -m "docs: finalize v3 implementation handoff"
```

---

Plan complete and saved to `docs/superpowers/plans/2026-04-03-quant-platform-v3.md`. Ready to execute?

