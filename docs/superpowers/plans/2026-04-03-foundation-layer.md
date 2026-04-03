# Foundation Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace SQLAlchemy/SQLite with asyncmy/MySQL, add feature platform adapter, and wire up the daily scheduled pipeline (factor engine → settlement → NAV calculator).

**Architecture:** All DB access goes through `db/connection.py` (asyncmy pool) via thin query modules in `db/queries/`. Business logic lives in `services/`. The `APScheduler` lifespan in `main.py` drives the daily batch jobs. Existing SQLAlchemy code is removed in-place; no compatibility shim.

**Tech Stack:** Python 3.11, asyncmy 0.2.9, APScheduler 3.10.4, numpy 1.26.4, pandas 2.2.1, FastAPI, pytest + pytest-asyncio, Docker (MySQL 8 for tests)

**Spec:** `docs/specs/2026-04-02-quant-platform-redesign.md` — Sections 2, 6, 7 (P0–P1)

**This plan is Plan 1 of 4.** Plans 2–4 (API+Agents, Frontend, Backtest+Scaffolds) depend on this foundation being complete.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/db/__init__.py` | Create | Package marker |
| `backend/db/schema.sql` | Create | Complete MySQL DDL for all tables |
| `backend/db/connection.py` | Create | asyncmy pool + `get_db_conn()` context manager |
| `backend/db/queries/__init__.py` | Create | Package marker |
| `backend/db/queries/factors.py` | Create | CRUD: factor_definitions, daily_factor_snapshots, factor_performance |
| `backend/db/queries/decisions.py` | Create | CRUD: decision_runs, agent_signals, rebalance_orders |
| `backend/db/queries/approvals.py` | Create | CRUD: approval_records |
| `backend/db/queries/portfolio.py` | Create | CRUD: portfolio_holdings, portfolio_snapshots |
| `backend/db/queries/strategy.py` | Create | CRUD: strategy_versions, strategy_experiments |
| `backend/db/queries/graph.py` | Create | CRUD: graph_nodes |
| `backend/db/queries/risk.py` | Create | CRUD: risk_config, risk_events |
| `backend/db/queries/settlement.py` | Create | Read/write: agent_performance |
| `backend/db/queries/agent_weights.py` | Create | CRUD: agent_weight_configs |
| `backend/db/queries/nav_history.py` | Create | CRUD: portfolio_nav_history |
| `backend/db/queries/backtest.py` | Create | CRUD: backtest_reports |
| `backend/db/queries/candidate.py` | Create | CRUD: candidate_pool |
| `backend/config.py` | Modify | Add DB_HOST/PORT/USER/PASSWORD/NAME + feature platform + scheduler params |
| `backend/database.py` | Modify | Replace SQLAlchemy engine with asyncmy pool init; keep `init_db()` signature |
| `backend/models.py` | Modify | Replace ORM classes with TypedDict documentation types |
| `backend/services/feature_client.py` | Create | FeatureClient: API mode + DB mode, memory cache |
| `backend/services/factor_engine.py` | Create | `run_daily()`: IC calc, regime detection, snapshot write |
| `backend/services/settlement.py` | Create | `run()`: T+5 settle, agent weight recalc |
| `backend/services/nav_calculator.py` | Create | `run()`: NAV update from close prices |
| `backend/services/scheduler.py` | Create | APScheduler AsyncIOScheduler, is_trading_day() |
| `backend/main.py` | Modify | Replace SQLAlchemy lifespan with asyncmy pool + scheduler start/stop |
| `backend/tests/conftest.py` | Modify | MySQL test DB (quant_ai_test) via Docker; remove SQLAlchemy fixtures |
| `backend/tests/test_units.py` | Modify | Add: IC calc, regime detection, is_correct logic, composite score |
| `docker-compose.test.yml` | Create | MySQL 8 container for tests |

---

## Task 1: MySQL Schema

**Files:**
- Create: `backend/db/__init__.py`
- Create: `backend/db/queries/__init__.py`
- Create: `backend/db/schema.sql`

- [ ] **Step 1: Create package markers**

```bash
# In backend/
touch backend/db/__init__.py
touch backend/db/queries/__init__.py
```

- [ ] **Step 2: Write schema.sql**

Create `backend/db/schema.sql` with the full DDL. Copy the exact DDL from `docs/specs/2026-04-02-quant-platform-redesign.md` Section 2 "新增表 DDL". Then append the ALTER statements for existing tables:

```sql
-- Append at end of schema.sql after all CREATE TABLE statements

-- ── 现有表改造（ALTER） ─────────────────────────────────────────────────
ALTER TABLE approval_records
  ADD COLUMN mode ENUM('targeted','rebalance') DEFAULT 'targeted'
  AFTER id;

ALTER TABLE backtest_reports
  ADD COLUMN signal_based BOOLEAN DEFAULT FALSE,
  ADD COLUMN factor_snapshot_id VARCHAR(36);
```

- [ ] **Step 3: Verify schema parses**

```bash
# Requires MySQL 8 running. If not yet available, skip to Task 2 and return here.
mysql -u root -p quant_ai_test < backend/db/schema.sql
echo "Exit code: $?"
```

Expected: `Exit code: 0`

- [ ] **Step 4: Commit**

```bash
git add backend/db/__init__.py backend/db/queries/__init__.py backend/db/schema.sql
git commit -m "feat: add MySQL DDL schema and db package structure"
```

---

## Task 2: asyncmy Connection Pool

**Files:**
- Create: `backend/db/connection.py`

- [ ] **Step 1: Install asyncmy**

```bash
cd backend
pip install asyncmy==0.2.9
```

- [ ] **Step 2: Write db/connection.py**

```python
# backend/db/connection.py
from __future__ import annotations
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import asyncmy
import asyncmy.cursors
from asyncmy.pool import Pool

_pool: Pool | None = None


async def create_pool(
    host: str,
    port: int,
    user: str,
    password: str,
    db: str,
    minsize: int = 2,
    maxsize: int = 10,
) -> Pool:
    global _pool
    _pool = await asyncmy.create_pool(
        host=host,
        port=port,
        user=user,
        password=password,
        db=db,
        charset="utf8mb4",
        autocommit=False,
        minsize=minsize,
        maxsize=maxsize,
    )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        await _pool.wait_closed()
        _pool = None


def get_pool() -> Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialised — call create_pool() first")
    return _pool


@asynccontextmanager
async def get_db_conn() -> AsyncGenerator:
    """Yields a connection; auto-commits on success, rolls back on exception."""
    pool = get_pool()
    async with pool.acquire() as conn:
        try:
            yield conn
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
```

- [ ] **Step 3: Write the unit test**

```python
# backend/tests/test_units.py  (add this test block)
import pytest
import asyncmy

@pytest.mark.asyncio
async def test_get_pool_raises_before_init(monkeypatch):
    """get_pool() must raise when pool is None."""
    import db.connection as dbc
    original = dbc._pool
    dbc._pool = None
    with pytest.raises(RuntimeError, match="not initialised"):
        dbc.get_pool()
    dbc._pool = original  # restore
```

- [ ] **Step 4: Run test**

```bash
cd backend
pytest tests/test_units.py::test_get_pool_raises_before_init -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/db/connection.py backend/tests/test_units.py
git commit -m "feat: asyncmy connection pool with get_db_conn() context manager"
```

---

## Task 3: Config Extension

**Files:**
- Modify: `backend/config.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_units.py  (add)
def test_config_has_db_fields():
    from config import Settings
    s = Settings(
        DB_HOST="testhost", DB_PORT=3307, DB_USER="u",
        DB_PASSWORD="p", DB_NAME="testdb",
        FEATURE_PLATFORM_MODE="api",
    )
    assert s.DB_HOST == "testhost"
    assert s.DB_PORT == 3307
    assert s.FEATURE_PLATFORM_MODE == "api"
    assert s.TRADING_CALENDAR_CACHE_DAYS == 30  # default
```

- [ ] **Step 2: Run test to see it fail**

```bash
pytest tests/test_units.py::test_config_has_db_fields -v
```

Expected: `FAILED` — `Settings` has no attribute `DB_HOST`

- [ ] **Step 3: Update config.py**

```python
# backend/config.py  — replace full file content
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # ── MySQL (asyncmy) ────────────────────────────────────────────
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "quant_user"
    DB_PASSWORD: str = ""
    DB_NAME: str = "quant_ai"

    # ── LLM ───────────────────────────────────────────────────────
    LLM_API_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o"

    # ── Feature Platform ──────────────────────────────────────────
    FEATURE_PLATFORM_MODE: str = "api"   # api | db
    FEATURE_PLATFORM_API_URL: str = ""
    FEATURE_PLATFORM_API_KEY: str = ""
    FEATURE_PLATFORM_DB_URL: str = ""    # MySQL DSN for DB mode

    # ── Data source (AKShare fallback) ────────────────────────────
    DATA_PROVIDER: str = "akshare"
    TUSHARE_TOKEN: str = ""

    # ── Scheduler ─────────────────────────────────────────────────
    TRADING_CALENDAR_CACHE_DAYS: int = 30

    # ── App ───────────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:5173"
    APP_ENV: str = "development"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    @property
    def use_mock(self) -> bool:
        return not bool(self.LLM_API_KEY.strip())

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
```

- [ ] **Step 4: Run test**

```bash
pytest tests/test_units.py::test_config_has_db_fields -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/config.py backend/tests/test_units.py
git commit -m "feat: extend config with MySQL, feature platform, scheduler params"
```

---

## Task 4: models.py → TypedDict

**Files:**
- Modify: `backend/models.py`

The ORM models are replaced with TypedDict classes that serve as documentation. They have no runtime behavior — they're just type hints for dicts returned from db/queries/.

- [ ] **Step 1: Rewrite models.py**

```python
# backend/models.py
"""
TypedDict documentation classes for DB row shapes.
These replace SQLAlchemy ORM models. No runtime behavior.
Actual table DDL is in db/schema.sql.
"""
from __future__ import annotations
from typing import TypedDict, Any


class DecisionRun(TypedDict):
    id: str
    mode: str               # 'targeted' | 'rebalance'
    status: str             # 'running' | 'completed' | 'failed'
    triggered_by: str
    symbols: list
    candidate_symbols: list | None
    current_portfolio: dict | None
    factor_snapshot_id: str | None
    factor_date: str | None
    strategy_version_id: str | None
    market_regime: str | None
    final_direction: str | None
    risk_level: str | None
    error_message: str | None
    started_at: str
    completed_at: str | None


class AgentSignal(TypedDict):
    id: str
    decision_run_id: str
    agent_type: str
    symbol: str | None
    direction: str | None
    confidence: float | None
    reasoning_summary: str | None
    signal_weight: float | None
    data_sources: list | None
    input_snapshot: dict | None
    is_contradictory: bool
    created_at: str


class RebalanceOrder(TypedDict):
    id: str
    decision_run_id: str
    symbol: str
    symbol_name: str | None
    action: str             # 'buy'|'sell'|'hold'|'close'|'new'
    current_weight: float
    target_weight: float
    weight_delta: float
    composite_score: float | None
    score_breakdown: dict | None
    reasoning: str | None
    created_at: str


class ApprovalRecord(TypedDict):
    id: str
    mode: str
    decision_run_id: str
    status: str
    recommendations: list
    reviewed_by: str | None
    comment: str | None
    created_at: str
    updated_at: str | None


class PortfolioHolding(TypedDict):
    id: str
    symbol: str
    symbol_name: str | None
    weight: float
    cost_price: float | None
    current_price: float | None
    quantity: int | None
    market_value: float | None
    pnl_pct: float | None
    created_at: str
    updated_at: str | None


class PortfolioSnapshot(TypedDict):
    id: str
    approval_record_id: str
    holdings: list
    total_value: float | None
    created_at: str


class RiskConfig(TypedDict):
    id: int
    max_position_weight: float
    daily_loss_warning_threshold: float
    daily_loss_suspend_threshold: float
    max_drawdown_emergency: float
    circuit_breaker_level: int
    emergency_stop_active: bool


class RiskEvent(TypedDict):
    id: str
    event_type: str
    severity: str
    description: str
    trigger_value: float | None
    is_resolved: bool
    created_at: str


class AutoApprovalRule(TypedDict):
    id: str
    name: str
    description: str | None
    logic_operator: str
    conditions: list
    is_active: bool
    priority: int
    created_at: str


class BacktestReport(TypedDict):
    id: str
    symbol: str | None
    start_date: str | None
    end_date: str | None
    initial_capital: float | None
    total_return: float | None
    sharpe_ratio: float | None
    max_drawdown: float | None
    nav_curve: list | None
    status: str
    signal_based: bool
    factor_snapshot_id: str | None
    created_at: str


class GraphNode(TypedDict):
    node_id: str
    approval_id: str
    decision_run_id: str | None
    mode: str | None
    trade_date: str | None
    symbols: list | None
    market_regime: str | None
    effective_factors: list | None
    approved: bool
    outcome_return: float
    outcome_sharpe: float
    factor_snapshot: dict | None
    settled: bool
    created_at: str
    settled_at: str | None


class DailyFactorSnapshot(TypedDict):
    id: str
    trade_date: str
    market_regime: str | None
    effective_factors: list
    stock_scores: dict
    industry_scores: dict
    concept_scores: dict
    market_factors: dict
    created_at: str


class FactorDefinition(TypedDict):
    id: str
    factor_key: str
    name: str
    entity_type: str
    domain: str
    source: str
    formula: str | None
    description: str | None
    is_active: bool
    created_at: str


class FactorPerformance(TypedDict):
    id: str
    factor_key: str
    trade_date: str
    ic: float | None
    rank_ic: float | None
    ic_ir: float | None
    direction: int | None
    is_effective: bool
    created_at: str


class AgentPerformance(TypedDict):
    id: str
    decision_run_id: str
    agent_signal_id: str
    agent_type: str
    symbol: str | None
    predicted_direction: str | None
    predicted_at: str | None
    settlement_date: str | None
    actual_return: float | None
    is_correct: bool | None
    factor_snapshot: dict | None
    settled_at: str | None


class AgentWeightConfig(TypedDict):
    id: str
    agent_type: str
    weight: float
    accuracy_30d: float | None
    accuracy_60d: float | None
    is_locked: bool
    last_updated: str


class StrategyVersion(TypedDict):
    id: str
    version: str
    program_md: str | None
    factor_weights: dict | None
    agent_weights: dict | None
    regime_rules: dict | None
    is_active: bool
    performance: dict | None
    created_at: str


class PortfolioNavHistory(TypedDict):
    id: str
    trade_date: str
    nav: float
    total_mv: float | None
    daily_return: float | None
    created_at: str


class CandidatePool(TypedDict):
    id: str
    symbol: str
    symbol_name: str | None
    added_at: str
    note: str | None
```

- [ ] **Step 2: Run existing tests to confirm nothing explodes**

```bash
cd backend
pytest tests/ -v --ignore=tests/test_api.py 2>&1 | head -30
```

Expected: Tests that import models still import without error (TypedDicts are purely passive).

- [ ] **Step 3: Commit**

```bash
git add backend/models.py
git commit -m "refactor: replace SQLAlchemy ORM with TypedDict documentation classes"
```

---

## Task 5: Docker + Test DB Setup

**Files:**
- Create: `docker-compose.test.yml`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Create docker-compose.test.yml**

```yaml
# docker-compose.test.yml  (repo root)
version: "3.9"
services:
  mysql_test:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: test_root
      MYSQL_DATABASE: quant_ai_test
      MYSQL_USER: quant_test
      MYSQL_PASSWORD: quant_test
    ports:
      - "3307:3306"
    command: --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 5s
      timeout: 5s
      retries: 10
```

- [ ] **Step 2: Start the test DB**

```bash
docker compose -f docker-compose.test.yml up -d
docker compose -f docker-compose.test.yml ps
# Wait until healthy (usually ~15s)
```

Expected: `mysql_test` status `healthy`

- [ ] **Step 3: Rewrite conftest.py**

```python
# backend/tests/conftest.py
"""
Test configuration — MySQL quant_ai_test, created fresh per session.
Requires Docker: docker compose -f docker-compose.test.yml up -d
"""
from __future__ import annotations
import asyncio
import json
import os
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

TEST_DB_CONFIG = dict(
    host=os.getenv("TEST_DB_HOST", "127.0.0.1"),
    port=int(os.getenv("TEST_DB_PORT", "3307")),
    user=os.getenv("TEST_DB_USER", "quant_test"),
    password=os.getenv("TEST_DB_PASSWORD", "quant_test"),
    db=os.getenv("TEST_DB_NAME", "quant_ai_test"),
)


@pytest_asyncio.fixture(scope="session")
async def db_pool():
    """Create pool + apply schema once per test session."""
    import asyncmy
    import asyncmy.cursors
    from db import connection as dbc

    pool = await dbc.create_pool(**TEST_DB_CONFIG)

    # Apply schema
    schema_path = os.path.join(os.path.dirname(__file__), "..", "db", "schema.sql")
    with open(schema_path) as f:
        raw = f.read()

    # Split on semicolons, skip blanks and comments
    statements = [
        s.strip() for s in raw.split(";")
        if s.strip() and not s.strip().startswith("--")
    ]

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            for stmt in statements:
                try:
                    await cur.execute(stmt)
                except Exception:
                    pass  # ignore "table already exists" etc.
        await conn.commit()

    yield pool

    # Teardown: drop all test tables
    async with pool.acquire() as conn:
        async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
            await cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = %s", (TEST_DB_CONFIG["db"],)
            )
            tables = [r["table_name"] for r in await cur.fetchall()]
        async with conn.cursor() as cur:
            await cur.execute("SET FOREIGN_KEY_CHECKS=0")
            for t in tables:
                await cur.execute(f"DROP TABLE IF EXISTS `{t}`")
            await cur.execute("SET FOREIGN_KEY_CHECKS=1")
        await conn.commit()

    await dbc.close_pool()


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(db_pool):
    """Truncate all tables before each test for isolation."""
    import asyncmy.cursors
    async with db_pool.acquire() as conn:
        async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
            await cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = %s", (TEST_DB_CONFIG["db"],)
            )
            tables = [r["table_name"] for r in await cur.fetchall()]
        async with conn.cursor() as cur:
            await cur.execute("SET FOREIGN_KEY_CHECKS=0")
            for t in tables:
                await cur.execute(f"TRUNCATE TABLE `{t}`")
            await cur.execute("SET FOREIGN_KEY_CHECKS=1")
        await conn.commit()

    # Seed required defaults
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            # risk_config row id=1 (UPDATE-based routes require it)
            await cur.execute("""
                INSERT IGNORE INTO risk_config
                  (id, max_position_weight, daily_loss_warning_threshold,
                   daily_loss_suspend_threshold, max_drawdown_emergency,
                   circuit_breaker_level, emergency_stop_active)
                VALUES (1, 0.20, 0.03, 0.06, 0.15, 0, FALSE)
            """)
            # 4 default agent weight rows
            for agent in ("technical", "fundamental", "news", "sentiment"):
                await cur.execute("""
                    INSERT IGNORE INTO agent_weight_configs
                      (id, agent_type, weight, is_locked)
                    VALUES (%s, %s, 0.25, FALSE)
                """, (str(uuid.uuid4()), agent))
        await conn.commit()
```

- [ ] **Step 4: Run a smoke test**

```bash
cd backend
pytest tests/test_units.py::test_get_pool_raises_before_init -v
```

Expected: `PASSED` (pool test is pure, no DB needed)

- [ ] **Step 5: Commit**

```bash
git add docker-compose.test.yml backend/tests/conftest.py
git commit -m "test: replace SQLite/SQLAlchemy fixtures with MySQL Docker-based conftest"
```

---

## Task 6: db/queries — Pattern + Factors Module

**Files:**
- Create: `backend/db/queries/factors.py`

This task establishes the query module pattern. All subsequent query modules (Task 7–15) follow the same pattern.

**Pattern rules:**
1. Use `get_db_conn()` for every operation.
2. Use `asyncmy.cursors.DictCursor` for SELECT operations.
3. JSON fields: always `json.dumps()` on write, `json.loads()` on read.
4. Generate UUIDs in Python (`str(uuid.uuid4())`), not in MySQL.
5. `ON DUPLICATE KEY UPDATE` for upserts.

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_units.py  (add)
@pytest.mark.asyncio
async def test_upsert_and_get_daily_snapshot(db_pool):
    import db.connection as dbc
    # db_pool fixture has already set _pool via create_pool
    # Re-point the module's pool to the test pool
    dbc._pool = db_pool

    from db.queries.factors import upsert_daily_snapshot, get_latest_snapshot

    data = {
        "market_regime": "bull_low_vol",
        "effective_factors": [{"factor_key": "momentum_20d", "ic_weight": 0.15}],
        "stock_scores": {"600036": 0.72},
        "industry_scores": {},
        "concept_scores": {},
        "market_factors": {"market_return_5d": 0.018},
    }
    sid = await upsert_daily_snapshot("2026-04-02", data)
    assert sid  # returned an ID

    row = await get_latest_snapshot("2026-04-02")
    assert row is not None
    assert row["market_regime"] == "bull_low_vol"
    assert row["effective_factors"][0]["factor_key"] == "momentum_20d"
    assert row["stock_scores"]["600036"] == pytest.approx(0.72)
```

- [ ] **Step 2: Run test to see it fail**

```bash
pytest tests/test_units.py::test_upsert_and_get_daily_snapshot -v
```

Expected: `FAILED` — `ModuleNotFoundError: db.queries.factors`

- [ ] **Step 3: Write db/queries/factors.py**

```python
# backend/db/queries/factors.py
from __future__ import annotations
import json
import uuid
import asyncmy.cursors
from db.connection import get_db_conn


async def upsert_daily_snapshot(trade_date: str, data: dict) -> str:
    snapshot_id = str(uuid.uuid4())
    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO daily_factor_snapshots
                  (id, trade_date, market_regime, effective_factors,
                   stock_scores, industry_scores, concept_scores, market_factors)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                  id               = id,
                  market_regime    = VALUES(market_regime),
                  effective_factors= VALUES(effective_factors),
                  stock_scores     = VALUES(stock_scores),
                  industry_scores  = VALUES(industry_scores),
                  concept_scores   = VALUES(concept_scores),
                  market_factors   = VALUES(market_factors)
            """, (
                snapshot_id,
                trade_date,
                data.get("market_regime"),
                json.dumps(data.get("effective_factors", [])),
                json.dumps(data.get("stock_scores", {})),
                json.dumps(data.get("industry_scores", {})),
                json.dumps(data.get("concept_scores", {})),
                json.dumps(data.get("market_factors", {})),
            ))
    return snapshot_id


async def get_latest_snapshot(up_to_date: str | None = None) -> dict | None:
    async with get_db_conn() as conn:
        async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
            if up_to_date:
                await cur.execute(
                    "SELECT * FROM daily_factor_snapshots "
                    "WHERE trade_date <= %s ORDER BY trade_date DESC LIMIT 1",
                    (up_to_date,)
                )
            else:
                await cur.execute(
                    "SELECT * FROM daily_factor_snapshots "
                    "ORDER BY trade_date DESC LIMIT 1"
                )
            row = await cur.fetchone()
    if row is None:
        return None
    for field in ("effective_factors", "stock_scores",
                  "industry_scores", "concept_scores", "market_factors"):
        if row.get(field) and isinstance(row[field], (str, bytes)):
            row[field] = json.loads(row[field])
    return row


async def insert_factor_performance(rows: list[dict]) -> None:
    """Bulk-insert factor IC performance rows. Ignores duplicates."""
    if not rows:
        return
    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.executemany("""
                INSERT IGNORE INTO factor_performance
                  (id, factor_key, trade_date, ic, rank_ic, ic_ir,
                   direction, is_effective)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, [
                (
                    str(uuid.uuid4()),
                    r["factor_key"], r["trade_date"],
                    r.get("ic"), r.get("rank_ic"), r.get("ic_ir"),
                    r.get("direction"), r.get("is_effective", False),
                )
                for r in rows
            ])


async def list_active_factor_definitions() -> list[dict]:
    async with get_db_conn() as conn:
        async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
            await cur.execute(
                "SELECT * FROM factor_definitions WHERE is_active = TRUE"
            )
            return list(await cur.fetchall())


async def get_factor_performance_history(
    factor_key: str, days: int = 60
) -> list[dict]:
    async with get_db_conn() as conn:
        async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
            await cur.execute("""
                SELECT * FROM factor_performance
                WHERE factor_key = %s
                ORDER BY trade_date DESC
                LIMIT %s
            """, (factor_key, days))
            return list(await cur.fetchall())
```

- [ ] **Step 4: Run test**

```bash
pytest tests/test_units.py::test_upsert_and_get_daily_snapshot -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/db/queries/factors.py backend/tests/test_units.py
git commit -m "feat: db/queries/factors — daily_factor_snapshots + factor_performance CRUD"
```

---

## Task 7: Remaining db/queries Modules

**Files:**
- Create: `backend/db/queries/decisions.py`
- Create: `backend/db/queries/approvals.py`
- Create: `backend/db/queries/portfolio.py`
- Create: `backend/db/queries/strategy.py`
- Create: `backend/db/queries/graph.py`
- Create: `backend/db/queries/risk.py`
- Create: `backend/db/queries/settlement.py`
- Create: `backend/db/queries/agent_weights.py`
- Create: `backend/db/queries/nav_history.py`
- Create: `backend/db/queries/backtest.py`
- Create: `backend/db/queries/candidate.py`

Follow the **exact same pattern** as `factors.py` for each module. Each module contains only the operations its service/router actually calls. Below are the required function signatures per module.

- [ ] **Step 1: Write db/queries/decisions.py**

```python
# backend/db/queries/decisions.py
from __future__ import annotations
import json, uuid
import asyncmy.cursors
from db.connection import get_db_conn


async def create_decision_run(data: dict) -> str:
    """Insert a new decision_run row; returns the generated id."""
    rid = str(uuid.uuid4())
    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO decision_runs
                  (id, mode, status, triggered_by, symbols, candidate_symbols,
                   current_portfolio, factor_snapshot_id, factor_date,
                   strategy_version_id, market_regime, risk_level)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                rid,
                data["mode"],
                data.get("status", "running"),
                data.get("triggered_by", "user"),
                json.dumps(data.get("symbols", [])),
                json.dumps(data.get("candidate_symbols")) if data.get("candidate_symbols") else None,
                json.dumps(data.get("current_portfolio")) if data.get("current_portfolio") else None,
                data.get("factor_snapshot_id"),
                data.get("factor_date"),
                data.get("strategy_version_id"),
                data.get("market_regime"),
                data.get("risk_level"),
            ))
    return rid


async def update_decision_run(run_id: str, updates: dict) -> None:
    """Patch arbitrary columns on a decision_run row."""
    if not updates:
        return
    # Serialize JSON fields
    for field in ("symbols", "candidate_symbols", "current_portfolio"):
        if field in updates and not isinstance(updates[field], str):
            updates[field] = json.dumps(updates[field])
    set_clause = ", ".join(f"`{k}` = %s" for k in updates)
    values = list(updates.values()) + [run_id]
    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"UPDATE decision_runs SET {set_clause} WHERE id = %s",
                values
            )


async def get_decision_run(run_id: str) -> dict | None:
    async with get_db_conn() as conn:
        async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
            await cur.execute(
                "SELECT * FROM decision_runs WHERE id = %s", (run_id,)
            )
            row = await cur.fetchone()
    if row is None:
        return None
    for field in ("symbols", "candidate_symbols", "current_portfolio"):
        if row.get(field) and isinstance(row[field], (str, bytes)):
            row[field] = json.loads(row[field])
    return row


async def list_decision_runs(limit: int = 20, offset: int = 0) -> list[dict]:
    async with get_db_conn() as conn:
        async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
            await cur.execute(
                "SELECT * FROM decision_runs ORDER BY started_at DESC "
                "LIMIT %s OFFSET %s",
                (limit, offset)
            )
            rows = list(await cur.fetchall())
    for row in rows:
        for field in ("symbols", "candidate_symbols", "current_portfolio"):
            if row.get(field) and isinstance(row[field], (str, bytes)):
                row[field] = json.loads(row[field])
    return rows


async def insert_agent_signal(data: dict) -> str:
    sid = str(uuid.uuid4())
    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO agent_signals
                  (id, decision_run_id, agent_type, symbol, direction,
                   confidence, reasoning_summary, signal_weight,
                   data_sources, input_snapshot, is_contradictory)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                sid,
                data["decision_run_id"],
                data["agent_type"],
                data.get("symbol"),
                data.get("direction"),
                data.get("confidence"),
                data.get("reasoning_summary"),
                data.get("signal_weight"),
                json.dumps(data.get("data_sources")) if data.get("data_sources") else None,
                json.dumps(data.get("input_snapshot")) if data.get("input_snapshot") else None,
                bool(data.get("is_contradictory", False)),
            ))
    return sid


async def list_agent_signals(decision_run_id: str) -> list[dict]:
    async with get_db_conn() as conn:
        async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
            await cur.execute(
                "SELECT * FROM agent_signals WHERE decision_run_id = %s",
                (decision_run_id,)
            )
            rows = list(await cur.fetchall())
    for row in rows:
        for field in ("data_sources", "input_snapshot"):
            if row.get(field) and isinstance(row[field], (str, bytes)):
                row[field] = json.loads(row[field])
    return rows
```

- [ ] **Step 2: Write db/queries/approvals.py**

```python
# backend/db/queries/approvals.py
from __future__ import annotations
import json, uuid
import asyncmy.cursors
from db.connection import get_db_conn


async def create_approval(data: dict) -> str:
    aid = str(uuid.uuid4())
    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO approval_records
                  (id, mode, decision_run_id, status, recommendations)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                aid,
                data.get("mode", "targeted"),
                data["decision_run_id"],
                data.get("status", "pending"),
                json.dumps(data.get("recommendations", [])),
            ))
    return aid


async def get_approval(approval_id: str) -> dict | None:
    async with get_db_conn() as conn:
        async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
            await cur.execute(
                "SELECT * FROM approval_records WHERE id = %s", (approval_id,)
            )
            row = await cur.fetchone()
    if row and row.get("recommendations") and isinstance(row["recommendations"], (str, bytes)):
        row["recommendations"] = json.loads(row["recommendations"])
    return row


async def update_approval_status(
    approval_id: str,
    status: str,
    reviewed_by: str | None = None,
    comment: str | None = None,
) -> None:
    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                UPDATE approval_records
                SET status=%s, reviewed_by=%s, comment=%s, updated_at=NOW()
                WHERE id=%s
            """, (status, reviewed_by, comment, approval_id))


async def list_pending_approvals() -> list[dict]:
    async with get_db_conn() as conn:
        async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
            await cur.execute(
                "SELECT * FROM approval_records WHERE status='pending' "
                "ORDER BY created_at DESC"
            )
            rows = list(await cur.fetchall())
    for row in rows:
        if row.get("recommendations") and isinstance(row["recommendations"], (str, bytes)):
            row["recommendations"] = json.loads(row["recommendations"])
    return rows
```

- [ ] **Step 3: Write db/queries/portfolio.py**

```python
# backend/db/queries/portfolio.py
from __future__ import annotations
import json, uuid
import asyncmy.cursors
from db.connection import get_db_conn


async def list_holdings() -> list[dict]:
    async with get_db_conn() as conn:
        async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
            await cur.execute("SELECT * FROM portfolio_holdings ORDER BY symbol")
            return list(await cur.fetchall())


async def upsert_holding(data: dict) -> str:
    hid = data.get("id") or str(uuid.uuid4())
    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO portfolio_holdings
                  (id, symbol, symbol_name, weight, cost_price,
                   current_price, quantity, market_value, pnl_pct)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                  symbol_name=VALUES(symbol_name),
                  weight=VALUES(weight),
                  cost_price=VALUES(cost_price),
                  current_price=VALUES(current_price),
                  quantity=VALUES(quantity),
                  market_value=VALUES(market_value),
                  pnl_pct=VALUES(pnl_pct),
                  updated_at=NOW()
            """, (
                hid,
                data["symbol"],
                data.get("symbol_name"),
                data.get("weight", 0.0),
                data.get("cost_price"),
                data.get("current_price"),
                data.get("quantity"),
                data.get("market_value"),
                data.get("pnl_pct"),
            ))
    return hid


async def delete_holding(holding_id: str) -> None:
    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM portfolio_holdings WHERE id=%s", (holding_id,)
            )


async def save_snapshot(approval_record_id: str, holdings: list, total_value: float | None) -> str:
    sid = str(uuid.uuid4())
    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO portfolio_snapshots
                  (id, approval_record_id, holdings, total_value)
                VALUES (%s,%s,%s,%s)
            """, (sid, approval_record_id, json.dumps(holdings), total_value))
    return sid
```

- [ ] **Step 4: Write db/queries/agent_weights.py**

```python
# backend/db/queries/agent_weights.py
from __future__ import annotations
import asyncmy.cursors
from db.connection import get_db_conn


async def list_agent_weights() -> list[dict]:
    async with get_db_conn() as conn:
        async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
            await cur.execute("SELECT * FROM agent_weight_configs ORDER BY agent_type")
            return list(await cur.fetchall())


async def update_agent_weight(
    agent_type: str,
    weight: float,
    is_locked: bool | None = None,
    accuracy_30d: float | None = None,
    accuracy_60d: float | None = None,
) -> None:
    updates: dict = {"weight": weight, "last_updated": "NOW()"}
    if is_locked is not None:
        updates["is_locked"] = is_locked
    if accuracy_30d is not None:
        updates["accuracy_30d"] = accuracy_30d
    if accuracy_60d is not None:
        updates["accuracy_60d"] = accuracy_60d

    set_parts = []
    values = []
    for k, v in updates.items():
        if v == "NOW()":
            set_parts.append(f"`{k}` = NOW()")
        else:
            set_parts.append(f"`{k}` = %s")
            values.append(v)
    values.append(agent_type)

    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"UPDATE agent_weight_configs SET {', '.join(set_parts)} "
                f"WHERE agent_type = %s",
                values
            )
```

- [ ] **Step 5a: Write db/queries/strategy.py**

```python
# backend/db/queries/strategy.py
from __future__ import annotations
import json, uuid
import asyncmy.cursors
from db.connection import get_db_conn

_JSON_FIELDS = ("factor_weights", "agent_weights", "regime_rules", "performance")


def _parse_json_fields(row: dict) -> dict:
    for f in _JSON_FIELDS:
        if row.get(f) and isinstance(row[f], (str, bytes)):
            row[f] = json.loads(row[f])
    return row


async def create_strategy_version(data: dict) -> str:
    vid = str(uuid.uuid4())
    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO strategy_versions
                  (id, version, program_md, factor_weights, agent_weights,
                   regime_rules, is_active, performance)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                vid,
                data["version"],
                data.get("program_md"),
                json.dumps(data.get("factor_weights", {})),
                json.dumps(data.get("agent_weights", {})),
                json.dumps(data.get("regime_rules", {})),
                bool(data.get("is_active", False)),
                json.dumps(data.get("performance", {})),
            ))
    return vid


async def get_active_strategy_version() -> dict | None:
    async with get_db_conn() as conn:
        async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
            await cur.execute(
                "SELECT * FROM strategy_versions WHERE is_active = TRUE LIMIT 1"
            )
            row = await cur.fetchone()
    return _parse_json_fields(row) if row else None


async def list_strategy_versions() -> list[dict]:
    async with get_db_conn() as conn:
        async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
            await cur.execute(
                "SELECT * FROM strategy_versions ORDER BY created_at DESC"
            )
            return [_parse_json_fields(r) for r in await cur.fetchall()]


async def activate_strategy_version(version_id: str) -> None:
    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE strategy_versions SET is_active = FALSE"
            )
            await cur.execute(
                "UPDATE strategy_versions SET is_active = TRUE WHERE id = %s",
                (version_id,)
            )


async def create_experiment(data: dict) -> str:
    eid = str(uuid.uuid4())
    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO strategy_experiments
                  (id, base_version_id, hypothesis, proposal, status)
                VALUES (%s,%s,%s,%s,%s)
            """, (
                eid,
                data.get("base_version_id"),
                data.get("hypothesis"),
                json.dumps(data.get("proposal", {})),
                data.get("status", "running"),
            ))
    return eid


async def list_experiments(base_version_id: str | None = None) -> list[dict]:
    async with get_db_conn() as conn:
        async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
            if base_version_id:
                await cur.execute(
                    "SELECT * FROM strategy_experiments "
                    "WHERE base_version_id = %s ORDER BY created_at DESC",
                    (base_version_id,)
                )
            else:
                await cur.execute(
                    "SELECT * FROM strategy_experiments ORDER BY created_at DESC"
                )
            rows = list(await cur.fetchall())
    for r in rows:
        if r.get("proposal") and isinstance(r["proposal"], (str, bytes)):
            r["proposal"] = json.loads(r["proposal"])
    return rows
```

- [ ] **Step 5b: Write db/queries/graph.py**

```python
# backend/db/queries/graph.py
from __future__ import annotations
import json, uuid
import asyncmy.cursors
from db.connection import get_db_conn

_JSON_FIELDS = ("symbols", "effective_factors", "factor_snapshot")


def _parse(row: dict) -> dict:
    for f in _JSON_FIELDS:
        if row.get(f) and isinstance(row[f], (str, bytes)):
            row[f] = json.loads(row[f])
    return row


async def insert_graph_node(data: dict) -> str:
    nid = data.get("node_id") or str(uuid.uuid4())
    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO graph_nodes
                  (node_id, approval_id, decision_run_id, mode, trade_date,
                   symbols, market_regime, effective_factors, approved,
                   outcome_return, factor_snapshot)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                nid,
                data["approval_id"],
                data.get("decision_run_id"),
                data.get("mode"),
                data.get("trade_date"),
                json.dumps(data.get("symbols", [])),
                data.get("market_regime"),
                json.dumps(data.get("effective_factors", [])),
                bool(data.get("approved", False)),
                data.get("outcome_return", 0.0),
                json.dumps(data.get("factor_snapshot", {})),
            ))
    return nid


async def list_graph_nodes(limit: int = 50) -> list[dict]:
    async with get_db_conn() as conn:
        async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
            await cur.execute(
                "SELECT * FROM graph_nodes ORDER BY created_at DESC LIMIT %s",
                (limit,)
            )
            return [_parse(r) for r in await cur.fetchall()]


async def update_graph_node_outcome(
    node_id: str,
    outcome_return: float,
    outcome_sharpe: float,
    settled: bool,
) -> None:
    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                UPDATE graph_nodes
                SET outcome_return=%s, outcome_sharpe=%s,
                    settled=%s, settled_at=NOW()
                WHERE node_id=%s
            """, (outcome_return, outcome_sharpe, settled, node_id))
```

- [ ] **Step 5c: Write db/queries/risk.py**

```python
# backend/db/queries/risk.py
from __future__ import annotations
import json, uuid
import asyncmy.cursors
from db.connection import get_db_conn


async def get_risk_config() -> dict | None:
    async with get_db_conn() as conn:
        async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
            await cur.execute("SELECT * FROM risk_config WHERE id = 1")
            return await cur.fetchone()


async def update_risk_config(updates: dict) -> None:
    if not updates:
        return
    set_clause = ", ".join(f"`{k}` = %s" for k in updates)
    values = list(updates.values()) + [1]
    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"UPDATE risk_config SET {set_clause} WHERE id = %s", values
            )


async def insert_risk_event(data: dict) -> str:
    eid = str(uuid.uuid4())
    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO risk_events
                  (id, event_type, severity, description, trigger_value, is_resolved)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (
                eid,
                data["event_type"],
                data.get("severity", "warning"),
                data.get("description", ""),
                data.get("trigger_value"),
                bool(data.get("is_resolved", False)),
            ))
    return eid


async def list_risk_events(severity: str | None = None, days: int = 7) -> list[dict]:
    async with get_db_conn() as conn:
        async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
            if severity:
                await cur.execute("""
                    SELECT * FROM risk_events
                    WHERE severity = %s
                      AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                    ORDER BY created_at DESC
                """, (severity, days))
            else:
                await cur.execute("""
                    SELECT * FROM risk_events
                    WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                    ORDER BY created_at DESC
                """, (days,))
            return list(await cur.fetchall())
```

- [ ] **Step 5d: Write db/queries/settlement.py**

```python
# backend/db/queries/settlement.py
from __future__ import annotations
import json, uuid
import asyncmy.cursors
from db.connection import get_db_conn


async def insert_performance_row(data: dict) -> str:
    """INSERT IGNORE — idempotent due to UNIQUE KEY uk_signal."""
    pid = str(uuid.uuid4())
    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT IGNORE INTO agent_performance
                  (id, decision_run_id, agent_signal_id, agent_type,
                   symbol, predicted_direction, predicted_at, settlement_date,
                   factor_snapshot)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                pid,
                data["decision_run_id"],
                data["agent_signal_id"],
                data["agent_type"],
                data.get("symbol"),
                data.get("predicted_direction"),
                data.get("predicted_at"),
                data["settlement_date"],
                json.dumps(data.get("factor_snapshot", {})),
            ))
    return pid


async def list_pending_settlements(settle_date: str) -> list[dict]:
    async with get_db_conn() as conn:
        async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
            await cur.execute("""
                SELECT * FROM agent_performance
                WHERE settlement_date = %s AND settled_at IS NULL
            """, (settle_date,))
            rows = list(await cur.fetchall())
    for r in rows:
        if r.get("factor_snapshot") and isinstance(r["factor_snapshot"], (str, bytes)):
            r["factor_snapshot"] = json.loads(r["factor_snapshot"])
    return rows


async def bulk_update_settlement(rows: list[dict]) -> None:
    if not rows:
        return
    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.executemany("""
                UPDATE agent_performance
                SET actual_return=%s, is_correct=%s, settled_at=%s
                WHERE id=%s
            """, [
                (r["actual_return"], r["is_correct"], r["settled_at"], r["id"])
                for r in rows
            ])


async def get_agent_accuracy(settle_date: str, days: int = 30) -> dict[str, float]:
    async with get_db_conn() as conn:
        async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
            await cur.execute("""
                SELECT agent_type,
                       SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) AS correct_count,
                       COUNT(*) AS total_count
                FROM agent_performance
                WHERE settled_at >= DATE_SUB(%s, INTERVAL %s DAY)
                  AND is_correct IS NOT NULL
                GROUP BY agent_type
            """, (settle_date, days))
            rows = await cur.fetchall()
    return {
        r["agent_type"]: (
            r["correct_count"] / r["total_count"] if r["total_count"] else 0.0
        )
        for r in rows
    }
```

- [ ] **Step 5e: Write db/queries/nav_history.py**

```python
# backend/db/queries/nav_history.py
from __future__ import annotations
import uuid
import asyncmy.cursors
from db.connection import get_db_conn


async def upsert_nav(
    trade_date: str,
    nav: float,
    total_mv: float | None,
    daily_return: float | None,
) -> None:
    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO portfolio_nav_history
                  (id, trade_date, nav, total_mv, daily_return)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                  nav=VALUES(nav),
                  total_mv=VALUES(total_mv),
                  daily_return=VALUES(daily_return)
            """, (str(uuid.uuid4()), trade_date, nav, total_mv, daily_return))


async def list_nav_history(days: int = 90) -> list[dict]:
    async with get_db_conn() as conn:
        async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
            await cur.execute("""
                SELECT * FROM portfolio_nav_history
                WHERE trade_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                ORDER BY trade_date ASC
            """, (days,))
            return list(await cur.fetchall())
```

- [ ] **Step 5f: Write db/queries/backtest.py**

```python
# backend/db/queries/backtest.py
from __future__ import annotations
import json, uuid
import asyncmy.cursors
from db.connection import get_db_conn

_JSON_FIELDS = ("nav_curve",)


def _parse(row: dict) -> dict:
    for f in _JSON_FIELDS:
        if row.get(f) and isinstance(row[f], (str, bytes)):
            row[f] = json.loads(row[f])
    return row


async def create_report(data: dict) -> str:
    rid = str(uuid.uuid4())
    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO backtest_reports
                  (id, symbol, start_date, end_date, initial_capital,
                   status, signal_based, factor_snapshot_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                rid,
                data.get("symbol"),
                data.get("start_date"),
                data.get("end_date"),
                data.get("initial_capital"),
                data.get("status", "running"),
                bool(data.get("signal_based", False)),
                data.get("factor_snapshot_id"),
            ))
    return rid


async def get_report(report_id: str) -> dict | None:
    async with get_db_conn() as conn:
        async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
            await cur.execute(
                "SELECT * FROM backtest_reports WHERE id = %s", (report_id,)
            )
            row = await cur.fetchone()
    return _parse(row) if row else None


async def update_report(report_id: str, updates: dict) -> None:
    if not updates:
        return
    for f in _JSON_FIELDS:
        if f in updates and not isinstance(updates[f], str):
            updates[f] = json.dumps(updates[f])
    set_clause = ", ".join(f"`{k}` = %s" for k in updates)
    values = list(updates.values()) + [report_id]
    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"UPDATE backtest_reports SET {set_clause} WHERE id = %s", values
            )


async def list_reports(limit: int = 20) -> list[dict]:
    async with get_db_conn() as conn:
        async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
            await cur.execute(
                "SELECT * FROM backtest_reports ORDER BY created_at DESC LIMIT %s",
                (limit,)
            )
            return [_parse(r) for r in await cur.fetchall()]
```

- [ ] **Step 5g: Write db/queries/candidate.py**

```python
# backend/db/queries/candidate.py
from __future__ import annotations
import uuid
import asyncmy.cursors
from db.connection import get_db_conn


async def list_candidates() -> list[dict]:
    async with get_db_conn() as conn:
        async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
            await cur.execute("SELECT * FROM candidate_pool ORDER BY added_at DESC")
            return list(await cur.fetchall())


async def add_candidate(
    symbol: str,
    symbol_name: str | None = None,
    note: str | None = None,
) -> str:
    cid = str(uuid.uuid4())
    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT IGNORE INTO candidate_pool (id, symbol, symbol_name, note)
                VALUES (%s, %s, %s, %s)
            """, (cid, symbol, symbol_name, note))
    return cid


async def remove_candidate(symbol: str) -> None:
    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM candidate_pool WHERE symbol = %s", (symbol,)
            )

- [ ] **Step 6: Write tests for two more modules**

```python
# backend/tests/test_units.py  (add)
@pytest.mark.asyncio
async def test_agent_weights_crud(db_pool):
    import db.connection as dbc
    dbc._pool = db_pool
    from db.queries.agent_weights import list_agent_weights, update_agent_weight

    # conftest seeds 4 agent rows
    rows = await list_agent_weights()
    assert len(rows) == 4
    agent_types = {r["agent_type"] for r in rows}
    assert agent_types == {"technical", "fundamental", "news", "sentiment"}

    await update_agent_weight("technical", weight=0.30, accuracy_30d=0.62)
    rows = await list_agent_weights()
    tech = next(r for r in rows if r["agent_type"] == "technical")
    assert tech["weight"] == pytest.approx(0.30)
    assert tech["accuracy_30d"] == pytest.approx(0.62)


@pytest.mark.asyncio
async def test_decision_run_lifecycle(db_pool):
    import db.connection as dbc
    dbc._pool = db_pool
    from db.queries.decisions import (
        create_decision_run, get_decision_run, update_decision_run
    )

    rid = await create_decision_run({
        "mode": "targeted",
        "symbols": ["600036"],
        "risk_level": "low",
    })
    assert rid

    run = await get_decision_run(rid)
    assert run["status"] == "running"
    assert run["symbols"] == ["600036"]

    await update_decision_run(rid, {"status": "completed", "final_direction": "buy"})
    run = await get_decision_run(rid)
    assert run["status"] == "completed"
    assert run["final_direction"] == "buy"
```

- [ ] **Step 7: Run tests**

```bash
pytest tests/test_units.py::test_agent_weights_crud tests/test_units.py::test_decision_run_lifecycle -v
```

Expected: Both `PASSED`

- [ ] **Step 8: Commit**

```bash
git add backend/db/queries/
git commit -m "feat: complete db/queries layer — all 11 CRUD modules"
```

---

## Task 8: database.py Migration

**Files:**
- Modify: `backend/database.py`

Replace the SQLAlchemy engine with asyncmy pool initialisation. Keep `init_db()` as the public API so `main.py` doesn't need to change yet.

- [ ] **Step 1: Rewrite database.py**

```python
# backend/database.py
"""
Database bootstrap — replaces SQLAlchemy with asyncmy pool.
Called by main.py lifespan and tests/conftest.py.
"""
from __future__ import annotations
from config import settings
from db.connection import create_pool, close_pool


async def init_db() -> None:
    """Create the asyncmy pool. Must be called before any DB query."""
    await create_pool(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        db=settings.DB_NAME,
    )
    await _seed_defaults()


async def shutdown_db() -> None:
    await close_pool()


async def _seed_defaults() -> None:
    """Insert required seed rows if they don't already exist."""
    import uuid
    from db.connection import get_db_conn

    async with get_db_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT IGNORE INTO risk_config
                  (id, max_position_weight, daily_loss_warning_threshold,
                   daily_loss_suspend_threshold, max_drawdown_emergency,
                   circuit_breaker_level, emergency_stop_active)
                VALUES (1, 0.20, 0.03, 0.06, 0.15, 0, FALSE)
            """)
            for agent in ("technical", "fundamental", "news", "sentiment"):
                await cur.execute("""
                    INSERT IGNORE INTO agent_weight_configs
                      (id, agent_type, weight, is_locked)
                    VALUES (%s, %s, 0.25, FALSE)
                """, (str(uuid.uuid4()), agent))
```

- [ ] **Step 2: Commit**

```bash
git add backend/database.py
git commit -m "refactor: database.py — replace SQLAlchemy engine with asyncmy pool init"
```

---

## Task 9: services/feature_client.py

**Files:**
- Create: `backend/services/feature_client.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_units.py  (add)
def test_feature_client_mock_snapshot():
    """FeatureClient API mode returns correct structure."""
    import importlib, sys
    # Use API mode with a mock httpx response
    from unittest.mock import AsyncMock, patch, MagicMock
    from services.feature_client import FeatureClient

    client = FeatureClient(mode="api", api_url="http://fake", api_key="key")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"600036": {"momentum_20d": 0.05, "pe_ttm": 12.3}}
    mock_resp.raise_for_status = MagicMock()

    import asyncio
    async def run():
        with patch.object(client._http, "get", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.fetch_snapshot(["600036"], "2026-04-02")
            assert "600036" in result
            assert result["600036"]["momentum_20d"] == 0.05

    asyncio.get_event_loop().run_until_complete(run())


def test_feature_client_missing_config_raises():
    from services.feature_client import FeatureClient
    import pytest
    with pytest.raises(ValueError, match="api_url"):
        FeatureClient(mode="api", api_url="", api_key="")
```

- [ ] **Step 2: Run tests to fail**

```bash
pytest tests/test_units.py::test_feature_client_mock_snapshot tests/test_units.py::test_feature_client_missing_config_raises -v
```

Expected: `FAILED` — `ModuleNotFoundError: services.feature_client`

- [ ] **Step 3: Write services/feature_client.py**

```python
# backend/services/feature_client.py
"""
FeatureClient — adapts the external Feature Platform.
FEATURE_PLATFORM_MODE=api  → HTTP requests (default)
FEATURE_PLATFORM_MODE=db   → MySQL direct connection (same pool as business DB)

Memory cache: prefetch_all() loads today's data at 08:30 and stores it here.
Queries during market hours hit the cache; fallback to live calls if miss.
"""
from __future__ import annotations
from datetime import date, datetime
from typing import Any
import httpx


class FeatureClient:
    def __init__(
        self,
        mode: str,
        api_url: str = "",
        api_key: str = "",
        db_url: str = "",
    ):
        if mode == "api" and not api_url:
            raise ValueError("api_url is required when mode='api'")
        if mode == "db" and not db_url:
            raise ValueError("db_url is required when mode='db'")
        self._mode = mode
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._db_url = db_url
        self._http = httpx.AsyncClient(
            headers={"X-API-Key": api_key} if api_key else {},
            timeout=10.0,
        )
        self._cache: dict[str, Any] = {}  # keyed by (date, data_type)

    # ── Public API ──────────────────────────────────────────────────────

    async def fetch_snapshot(
        self,
        symbols: list[str],
        trade_date: str,
        fields: list[str] | None = None,
    ) -> dict[str, dict]:
        """Returns {symbol: {factor_key: value}} for requested symbols/date."""
        cache_key = f"snapshot:{trade_date}"
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            result = {s: cached.get(s, {}) for s in symbols}
            if fields:
                result = {s: {k: v for k, v in d.items() if k in fields}
                          for s, d in result.items()}
            return result

        if self._mode == "api":
            return await self._api_fetch_snapshot(symbols, trade_date, fields)
        return await self._db_fetch_snapshot(symbols, trade_date, fields)

    async def fetch_market(self, trade_date: str) -> dict:
        """Returns market-level features for the given date."""
        cache_key = f"market:{trade_date}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if self._mode == "api":
            return await self._api_fetch_market(trade_date)
        return await self._db_fetch_market(trade_date)

    async def fetch_industry(self, trade_date: str) -> dict[str, dict]:
        """Returns {industry_code: {factor_key: value}}."""
        if self._mode == "api":
            return await self._api_fetch_entity("industry", trade_date)
        return await self._db_fetch_entity("industry", trade_date)

    async def fetch_concept(self, trade_date: str) -> dict[str, dict]:
        """Returns {concept_code: {factor_key: value}}."""
        if self._mode == "api":
            return await self._api_fetch_entity("concept", trade_date)
        return await self._db_fetch_entity("concept", trade_date)

    async def fetch_history(
        self,
        symbols: list[str],
        start: str,
        end: str,
        fields: list[str] | None = None,
    ) -> dict[str, list[dict]]:
        """Returns {symbol: [{trade_date, factor_key: value, ...}]}."""
        if self._mode == "api":
            return await self._api_fetch_history(symbols, start, end, fields)
        return await self._db_fetch_history(symbols, start, end, fields)

    async def prefetch_all(self, trade_date: str) -> None:
        """08:30 job: load entire universe into memory cache for today."""
        # Fetch all available symbols from the feature platform
        try:
            if self._mode == "api":
                resp = await self._http.get(
                    f"{self._api_url}/snapshot",
                    params={"date": trade_date}
                )
                resp.raise_for_status()
                data = resp.json()
            else:
                data = await self._db_fetch_snapshot([], trade_date, None)

            self._cache[f"snapshot:{trade_date}"] = data

            market = await self.fetch_market(trade_date)
            self._cache[f"market:{trade_date}"] = market
        except Exception as exc:
            # Non-fatal: log and continue; queries will fall back to live calls
            import logging
            logging.getLogger(__name__).warning(
                "prefetch_all failed for %s: %s", trade_date, exc
            )

    async def close(self) -> None:
        await self._http.aclose()

    # ── API mode internals ──────────────────────────────────────────────

    async def _api_fetch_snapshot(
        self, symbols: list[str], trade_date: str, fields: list[str] | None
    ) -> dict[str, dict]:
        params: dict = {"date": trade_date}
        if symbols:
            params["symbols"] = ",".join(symbols)
        if fields:
            params["fields"] = ",".join(fields)
        resp = await self._http.get(f"{self._api_url}/snapshot", params=params)
        resp.raise_for_status()
        return resp.json()

    async def _api_fetch_market(self, trade_date: str) -> dict:
        resp = await self._http.get(
            f"{self._api_url}/market", params={"date": trade_date}
        )
        resp.raise_for_status()
        return resp.json()

    async def _api_fetch_entity(self, entity_type: str, trade_date: str) -> dict[str, dict]:
        resp = await self._http.get(
            f"{self._api_url}/{entity_type}", params={"date": trade_date}
        )
        resp.raise_for_status()
        return resp.json()

    async def _api_fetch_history(
        self, symbols: list[str], start: str, end: str, fields: list[str] | None
    ) -> dict[str, list[dict]]:
        params: dict = {"start": start, "end": end}
        if symbols:
            params["symbols"] = ",".join(symbols)
        if fields:
            params["fields"] = ",".join(fields)
        resp = await self._http.get(f"{self._api_url}/history", params=params)
        resp.raise_for_status()
        return resp.json()

    # ── DB mode internals ───────────────────────────────────────────────

    async def _db_fetch_snapshot(
        self, symbols: list[str], trade_date: str, fields: list[str] | None
    ) -> dict[str, dict]:
        # DB mode: direct query against feature platform's MySQL
        # Implementation depends on the feature platform's actual schema.
        # Placeholder returns empty — to be implemented when schema is known.
        return {}

    async def _db_fetch_market(self, trade_date: str) -> dict:
        return {}

    async def _db_fetch_entity(self, entity_type: str, trade_date: str) -> dict[str, dict]:
        return {}

    async def _db_fetch_history(
        self, symbols: list[str], start: str, end: str, fields: list[str] | None
    ) -> dict[str, list[dict]]:
        return {}


def make_feature_client() -> FeatureClient:
    """Factory using settings. Call once at startup."""
    from config import settings
    return FeatureClient(
        mode=settings.FEATURE_PLATFORM_MODE,
        api_url=settings.FEATURE_PLATFORM_API_URL,
        api_key=settings.FEATURE_PLATFORM_API_KEY,
        db_url=settings.FEATURE_PLATFORM_DB_URL,
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_units.py::test_feature_client_mock_snapshot tests/test_units.py::test_feature_client_missing_config_raises -v
```

Expected: Both `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/services/feature_client.py backend/tests/test_units.py
git commit -m "feat: FeatureClient — API/DB mode adapter with memory cache and prefetch"
```

---

## Task 10: services/factor_engine.py

**Files:**
- Create: `backend/services/factor_engine.py`

- [ ] **Step 1: Install numpy/pandas**

```bash
pip install numpy==1.26.4 pandas==2.2.1
```

- [ ] **Step 2: Write unit tests for pure logic**

```python
# backend/tests/test_units.py  (add)
def test_detect_regime_bull_low_vol():
    from services.factor_engine import _detect_regime
    assert _detect_regime({"market_return_5d": 0.015, "market_volatility_20d": 0.02}) == "bull_low_vol"

def test_detect_regime_bear_high_vol():
    from services.factor_engine import _detect_regime
    assert _detect_regime({"market_return_5d": -0.012, "market_volatility_20d": 0.03}) == "bear_high_vol"

def test_detect_regime_sideways():
    from services.factor_engine import _detect_regime
    assert _detect_regime({"market_return_5d": 0.005, "market_volatility_20d": 0.02}) == "sideways"

def test_compute_rank_ic():
    from services.factor_engine import _compute_rank_ic
    import numpy as np
    # Perfect positive rank correlation
    factor_vals = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    returns     = np.array([0.01, 0.02, 0.03, 0.04, 0.05])
    ic = _compute_rank_ic(factor_vals, returns)
    assert ic == pytest.approx(1.0, abs=0.01)

def test_compute_rank_ic_insufficient_data():
    from services.factor_engine import _compute_rank_ic
    import numpy as np
    ic = _compute_rank_ic(np.array([1.0, 2.0]), np.array([0.01, 0.02]))
    assert ic == 0.0  # too few samples

def test_filter_effective_factors():
    from services.factor_engine import _filter_effective_factors
    factors = [
        {"factor_key": "momentum_20d", "ic_series": [0.05]*20},   # IC_IR high
        {"factor_key": "pe_ttm",        "ic_series": [0.01]*20},   # IC too low
        {"factor_key": "rsi_14",        "ic_series": [-0.04]*20},  # negative IC, valid
    ]
    result = _filter_effective_factors(factors)
    keys = {f["factor_key"] for f in result}
    assert "momentum_20d" in keys
    assert "pe_ttm" not in keys
    assert "rsi_14" in keys
```

- [ ] **Step 3: Run tests to fail**

```bash
pytest tests/test_units.py -k "regime or rank_ic or effective_factor" -v
```

Expected: All `FAILED` — module not found

- [ ] **Step 4: Write services/factor_engine.py**

```python
# backend/services/factor_engine.py
"""
Layer 1 Factor Screening Engine.
Runs daily at 08:45 via scheduler.

Responsibilities:
  1. Pull T-60 to T-5 feature history from FeatureClient
  2. Compute RankIC for each factor vs price_return_5d
  3. Filter by IC_THRESHOLD and IC_IR_THRESHOLD
  4. Write daily_factor_snapshots + factor_performance rows
"""
from __future__ import annotations
import logging
from datetime import date, timedelta
from typing import TYPE_CHECKING

import numpy as np
from scipy import stats as scipy_stats

if TYPE_CHECKING:
    from services.feature_client import FeatureClient

log = logging.getLogger(__name__)

# ── Tunable constants ──────────────────────────────────────────────────────────
IC_THRESHOLD    = 0.03   # |IC| must exceed this
IC_IR_THRESHOLD = 0.40   # IC / std(IC) must exceed this (rolling 20 bars)
ROLLING_WINDOW  = 60     # trading days of history to compute IC
MIN_SAMPLES     = 10     # minimum cross-section size for valid IC


# ── Public entry point ─────────────────────────────────────────────────────────

async def run_daily(trade_date: str, feature_client: "FeatureClient") -> None:
    """Main job: compute IC, write snapshot and performance rows."""
    from db.queries.factors import (
        upsert_daily_snapshot,
        insert_factor_performance,
        list_active_factor_definitions,
    )

    log.info("factor_engine.run_daily start: %s", trade_date)

    # 1. Get active factor definitions
    factor_defs = await list_active_factor_definitions()
    if not factor_defs:
        log.warning("No active factor definitions found — skipping")
        return

    factor_keys = [f["factor_key"] for f in factor_defs]

    # 2. Fetch historical features T-ROLLING_WINDOW to T-5
    end_hist   = _offset_trading_days(trade_date, -5)
    start_hist = _offset_trading_days(trade_date, -ROLLING_WINDOW)
    history = await feature_client.fetch_history(
        symbols=[],  # empty = all universe
        start=start_hist,
        end=end_hist,
        fields=factor_keys + ["price_return_5d"],
    )

    # 3. Compute IC for each factor
    ic_results = _compute_all_ic(history, factor_keys)

    # 4. Filter effective factors
    effective = _filter_effective_factors(ic_results)

    # 5. Fetch market features to detect regime
    market_features = await feature_client.fetch_market(trade_date)
    regime = _detect_regime(market_features)

    # 6. Fetch current-day stock features
    stock_features = await feature_client.fetch_snapshot([], trade_date, fields=factor_keys)
    industry_features = await feature_client.fetch_industry(trade_date)
    concept_features  = await feature_client.fetch_concept(trade_date)

    # 7. Normalise IC weights
    if effective:
        total_ic = sum(abs(f["mean_ic"]) for f in effective)
        for f in effective:
            f["ic_weight"] = round(abs(f["mean_ic"]) / total_ic, 4) if total_ic else 0.0

    # 8. Compute composite scores per stock
    stock_scores = _compute_composite_scores(stock_features, effective)

    # 9. Write to DB
    await upsert_daily_snapshot(trade_date, {
        "market_regime":     regime,
        "effective_factors": effective,
        "stock_scores":      stock_scores,
        "industry_scores":   {},  # TODO: compute when needed
        "concept_scores":    {},
        "market_factors":    market_features,
    })

    perf_rows = [
        {
            "factor_key":   r["factor_key"],
            "trade_date":   trade_date,
            "ic":           r.get("mean_ic"),
            "rank_ic":      r.get("mean_ic"),
            "ic_ir":        r.get("ic_ir"),
            "direction":    1 if r.get("mean_ic", 0) > 0 else -1,
            "is_effective": r in effective,
        }
        for r in ic_results
    ]
    await insert_factor_performance(perf_rows)
    log.info("factor_engine.run_daily done: %d effective factors, regime=%s",
             len(effective), regime)


# ── Pure helpers (unit-testable) ───────────────────────────────────────────────

def _detect_regime(market_features: dict) -> str:
    """Classify market into one of 5 regimes."""
    ret5  = market_features.get("market_return_5d", 0.0)
    vol20 = market_features.get("market_volatility_20d", 0.0)

    is_bull    = ret5 >  0.01
    is_bear    = ret5 < -0.01
    is_highvol = vol20 >= 0.025

    if is_bull and is_highvol:
        return "bull_high_vol"
    if is_bull:
        return "bull_low_vol"
    if is_bear and is_highvol:
        return "bear_high_vol"
    if is_bear:
        return "bear_low_vol"
    return "sideways"


def _compute_rank_ic(factor_vals: np.ndarray, returns: np.ndarray) -> float:
    """Spearman rank IC between factor values and forward returns."""
    mask = ~(np.isnan(factor_vals) | np.isnan(returns))
    if mask.sum() < MIN_SAMPLES:
        return 0.0
    corr, _ = scipy_stats.spearmanr(factor_vals[mask], returns[mask])
    return float(corr) if not np.isnan(corr) else 0.0


def _compute_all_ic(
    history: dict[str, list[dict]],
    factor_keys: list[str],
) -> list[dict]:
    """
    For each factor, compute mean IC and IC_IR across the history window.
    history shape: {symbol: [{trade_date, factor_key: value, price_return_5d: value}]}
    Returns list of {factor_key, mean_ic, ic_ir, ic_series}.
    """
    # Pivot: date -> {symbol: {factor: value, return: value}}
    by_date: dict[str, dict[str, dict]] = {}
    for symbol, records in history.items():
        for rec in records:
            d = rec.get("trade_date") or rec.get("date", "")
            by_date.setdefault(d, {})[symbol] = rec

    results = []
    for fk in factor_keys:
        ic_series = []
        for day_data in by_date.values():
            fv = np.array([
                float(v.get(fk, np.nan)) for v in day_data.values()
            ])
            rv = np.array([
                float(v.get("price_return_5d", np.nan)) for v in day_data.values()
            ])
            ic = _compute_rank_ic(fv, rv)
            ic_series.append(ic)

        if not ic_series:
            continue
        arr = np.array(ic_series)
        mean_ic = float(np.mean(arr))
        std_ic  = float(np.std(arr)) if len(arr) > 1 else 1e-9
        ic_ir   = mean_ic / std_ic if std_ic > 0 else 0.0
        results.append({
            "factor_key": fk,
            "mean_ic":    round(mean_ic, 4),
            "ic_ir":      round(ic_ir, 4),
            "ic_series":  [round(v, 4) for v in arr.tolist()],
        })
    return results


def _filter_effective_factors(ic_results: list[dict]) -> list[dict]:
    """Keep factors where |mean_ic| >= IC_THRESHOLD and |ic_ir| >= IC_IR_THRESHOLD."""
    effective = []
    for r in ic_results:
        ic_series = r.get("ic_series", [])
        mean_ic = r.get("mean_ic", 0.0)
        # Recompute IC_IR from ic_series if present
        if ic_series:
            arr = np.array(ic_series)
            std_ic = float(np.std(arr)) if len(arr) > 1 else 1e-9
            ic_ir = abs(float(np.mean(arr))) / std_ic if std_ic > 0 else 0.0
        else:
            ic_ir = abs(r.get("ic_ir", 0.0))

        if abs(mean_ic) >= IC_THRESHOLD and ic_ir >= IC_IR_THRESHOLD:
            effective.append(r)
    return effective


def _compute_composite_scores(
    stock_features: dict[str, dict],
    effective_factors: list[dict],
) -> dict[str, float]:
    """Weighted sum of normalised factor values per stock."""
    if not effective_factors or not stock_features:
        return {}

    scores: dict[str, float] = {}
    for symbol, features in stock_features.items():
        score = 0.0
        for fac in effective_factors:
            fk = fac["factor_key"]
            w  = fac.get("ic_weight", 0.0)
            v  = features.get(fk)
            if v is not None:
                direction = 1 if fac.get("mean_ic", 0) > 0 else -1
                score += direction * w * float(v)
        scores[symbol] = round(score, 4)
    return scores


def _offset_trading_days(trade_date: str, offset: int) -> str:
    """Approximate offset in calendar days (1 trading day ≈ 1.4 calendar days)."""
    d = date.fromisoformat(trade_date)
    d += timedelta(days=int(offset * 1.4))
    return d.isoformat()
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_units.py -k "regime or rank_ic or effective_factor" -v
```

Expected: All `PASSED`

- [ ] **Step 6: Commit**

```bash
git add backend/services/factor_engine.py backend/tests/test_units.py
git commit -m "feat: factor_engine — IC computation, regime detection, daily snapshot write"
```

---

## Task 11: services/settlement.py

**Files:**
- Create: `backend/services/settlement.py`

- [ ] **Step 1: Write unit tests for is_correct logic**

```python
# backend/tests/test_units.py  (add)
def test_is_correct_buy():
    from services.settlement import _is_correct
    assert _is_correct("buy",  0.008)  is True
    assert _is_correct("buy",  0.003)  is False
    assert _is_correct("buy", -0.010)  is False

def test_is_correct_sell():
    from services.settlement import _is_correct
    assert _is_correct("sell", -0.008) is True
    assert _is_correct("sell",  0.001) is False

def test_is_correct_hold():
    from services.settlement import _is_correct
    assert _is_correct("hold",  0.003)  is True
    assert _is_correct("hold", -0.003)  is True
    assert _is_correct("hold",  0.010)  is False

def test_compute_new_weights():
    from services.settlement import _compute_new_weights
    # All agents at 45-65% range → maintain 25%
    accuracies = {
        "technical": 0.55, "fundamental": 0.60,
        "news": 0.50, "sentiment": 0.58,
    }
    weights = _compute_new_weights(accuracies, locked={})
    assert abs(sum(weights.values()) - 1.0) < 0.001
    for w in weights.values():
        assert 0.0 < w <= 0.35
```

- [ ] **Step 2: Run tests to fail**

```bash
pytest tests/test_units.py -k "is_correct or compute_new_weights" -v
```

Expected: `FAILED`

- [ ] **Step 3: Write services/settlement.py**

```python
# backend/services/settlement.py
"""
T+5 settlement service.
Runs daily at 16:30 via scheduler.

Responsibilities:
  1. Find agent_performance rows where settlement_date = today
  2. Fetch actual price_return_5d from feature platform
  3. Compute is_correct for each prediction
  4. Every 20 trading days: recalculate agent weights
  5. Backfill graph_nodes.outcome_return
"""
from __future__ import annotations
import logging
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.feature_client import FeatureClient

log = logging.getLogger(__name__)

CORRECT_THRESHOLD = 0.005   # ±0.5 % boundary for buy/sell/hold judgement
WEIGHT_RECALC_EVERY = 20    # trading days between weight updates

# Agent weight caps by accuracy tier
CAP_LOW  = 0.10   # accuracy < 45%
CAP_MID  = 0.25   # accuracy 45-65%
CAP_HIGH = 0.35   # accuracy > 65%


async def run(settle_date: str, feature_client: "FeatureClient") -> None:
    from db.queries.settlement import list_pending_settlements, bulk_update_settlement
    from db.queries.agent_weights import list_agent_weights, update_agent_weight
    from db.queries.graph import update_graph_node_outcome

    log.info("settlement.run start: %s", settle_date)

    pending = await list_pending_settlements(settle_date)
    if not pending:
        log.info("No pending settlements for %s", settle_date)
        return

    # Group symbols for batch price fetch
    symbols = list({r["symbol"] for r in pending if r.get("symbol")})
    if symbols:
        price_data = await feature_client.fetch_snapshot(
            symbols, settle_date, fields=["price_return_5d"]
        )
    else:
        price_data = {}

    settled_rows = []
    for row in pending:
        symbol = row.get("symbol")
        actual_return = (
            price_data.get(symbol, {}).get("price_return_5d")
            if symbol else None
        )
        correct = (
            _is_correct(row["predicted_direction"], actual_return)
            if actual_return is not None and row.get("predicted_direction")
            else None
        )
        settled_rows.append({
            "id":            row["id"],
            "actual_return": actual_return,
            "is_correct":    correct,
            "settled_at":    settle_date,
        })

    await bulk_update_settlement(settled_rows)
    log.info("Settled %d records", len(settled_rows))

    # Every 20 trading days: recalculate agent weights
    if _is_weight_recalc_day(settle_date):
        await _recalculate_agent_weights(settle_date)

    # Backfill graph node outcomes
    await _backfill_graph_outcomes(settle_date, price_data)

    # WebSocket broadcast
    try:
        from websocket_manager import manager
        await manager.broadcast({
            "type": "settlement_completed",
            "date": settle_date,
            "settled_count": len(settled_rows),
        })
    except Exception:
        pass  # WS is non-critical


async def _recalculate_agent_weights(settle_date: str) -> None:
    from db.queries.settlement import get_agent_accuracy
    from db.queries.agent_weights import list_agent_weights, update_agent_weight

    weights_cfg = await list_agent_weights()
    locked = {r["agent_type"]: r["is_locked"] for r in weights_cfg}

    accuracies_30 = await get_agent_accuracy(settle_date, days=30)
    accuracies_60 = await get_agent_accuracy(settle_date, days=60)

    new_weights = _compute_new_weights(accuracies_30, locked)

    for agent_type, weight in new_weights.items():
        await update_agent_weight(
            agent_type,
            weight=weight,
            accuracy_30d=accuracies_30.get(agent_type),
            accuracy_60d=accuracies_60.get(agent_type),
        )
    log.info("Agent weights recalculated: %s", new_weights)


async def _backfill_graph_outcomes(settle_date: str, price_data: dict) -> None:
    from db.queries.graph import update_graph_node_outcome
    from db.connection import get_db_conn
    import asyncmy.cursors, json

    async with get_db_conn() as conn:
        async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
            await cur.execute(
                "SELECT node_id, symbols FROM graph_nodes "
                "WHERE settled = FALSE AND trade_date <= %s",
                (settle_date,)
            )
            nodes = list(await cur.fetchall())

    for node in nodes:
        syms = json.loads(node["symbols"]) if isinstance(node["symbols"], str) else node["symbols"] or []
        if not syms:
            continue
        returns = [
            price_data.get(s, {}).get("price_return_5d", 0.0) for s in syms
        ]
        avg_return = sum(returns) / len(returns) if returns else 0.0
        await update_graph_node_outcome(
            node["node_id"],
            outcome_return=round(avg_return, 4),
            outcome_sharpe=0.0,   # sharpe requires more history; updated later
            settled=True,
        )


# ── Pure helpers ──────────────────────────────────────────────────────────────

def _is_correct(direction: str, actual_return: float) -> bool:
    if direction == "buy":
        return actual_return > CORRECT_THRESHOLD
    if direction == "sell":
        return actual_return < -CORRECT_THRESHOLD
    if direction == "hold":
        return abs(actual_return) <= CORRECT_THRESHOLD
    return False


def _compute_new_weights(
    accuracies: dict[str, float],
    locked: dict[str, bool],
) -> dict[str, float]:
    """Apply accuracy tiers, then normalise unlocked weights."""
    caps: dict[str, float] = {}
    for agent, acc in accuracies.items():
        if locked.get(agent):
            caps[agent] = None  # preserve existing weight
        elif acc < 0.45:
            caps[agent] = CAP_LOW
        elif acc > 0.65:
            caps[agent] = CAP_HIGH
        else:
            caps[agent] = CAP_MID

    # Assign capped weights
    raw: dict[str, float] = {a: c for a, c in caps.items() if c is not None}

    total = sum(raw.values())
    if total == 0:
        return {a: 0.25 for a in accuracies}

    return {a: round(w / total, 4) for a, w in raw.items()}


def _is_weight_recalc_day(trade_date: str) -> bool:
    """True every WEIGHT_RECALC_EVERY trading days (approximated by calendar)."""
    d = date.fromisoformat(trade_date)
    # Simple proxy: recalc on dates divisible by ~28 calendar days
    return d.toordinal() % (WEIGHT_RECALC_EVERY * 2) < 2
```

- [ ] **Step 4: Run tests** (`get_agent_accuracy` is already in db/queries/settlement.py from Task 7 Step 5d)

```bash
pytest tests/test_units.py -k "is_correct or compute_new_weights" -v
```

Expected: All `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/services/settlement.py backend/tests/test_units.py
git commit -m "feat: settlement service — T+5 is_correct logic, agent weight recalculation"
```

---

## Task 12: services/nav_calculator.py

**Files:**
- Create: `backend/services/nav_calculator.py`

- [ ] **Step 1: Write test**

```python
# backend/tests/test_units.py  (add)
def test_compute_nav():
    from services.nav_calculator import _compute_nav
    # prev_nav=1.0, holding returns +2% avg → new NAV = 1.02
    holdings = [
        {"symbol": "600036", "weight": 0.5, "current_price": 102.0, "cost_price": 100.0},
        {"symbol": "000001", "weight": 0.5, "current_price": 51.0,  "cost_price": 50.0},
    ]
    new_nav, daily_return = _compute_nav(prev_nav=1.0, holdings=holdings)
    assert daily_return == pytest.approx(0.02, abs=0.001)
    assert new_nav == pytest.approx(1.02, abs=0.001)
```

- [ ] **Step 2: Run test to fail**

```bash
pytest tests/test_units.py::test_compute_nav -v
```

Expected: `FAILED`

- [ ] **Step 3: Write services/nav_calculator.py**

```python
# backend/services/nav_calculator.py
"""
Daily NAV calculator. Runs at 16:00 via scheduler.

Price source priority:
  1. feature_client.fetch_snapshot(holdings, date, fields=["close_price"])
     — requires feature platform to update by 16:00 on trade day T
  2. AKShare stock_zh_a_spot_em fallback if feature platform not ready
"""
from __future__ import annotations
import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.feature_client import FeatureClient

log = logging.getLogger(__name__)


async def run(trade_date: str, feature_client: "FeatureClient") -> None:
    from db.queries.portfolio import list_holdings, upsert_holding
    from db.queries.nav_history import upsert_nav, list_nav_history

    holdings = await list_holdings()
    if not holdings:
        log.info("No holdings — skipping NAV calculation for %s", trade_date)
        return

    symbols = [h["symbol"] for h in holdings]

    # 1. Fetch close prices
    close_prices = await _fetch_close_prices(symbols, trade_date, feature_client)

    # 2. Update portfolio_holdings with current prices
    for holding in holdings:
        cp = close_prices.get(holding["symbol"])
        if cp is None:
            continue
        cost = holding.get("cost_price") or cp
        pnl_pct = (cp - cost) / cost if cost else 0.0
        qty = holding.get("quantity") or 0
        mv  = cp * qty if qty else None
        await upsert_holding({
            **holding,
            "current_price": cp,
            "market_value":  mv,
            "pnl_pct":       round(pnl_pct, 4),
        })

    # 3. Compute NAV
    prev_records = await list_nav_history(days=2)
    prev_nav = prev_records[-1]["nav"] if prev_records else 1.0

    updated_holdings = await list_holdings()  # re-read with updated prices
    new_nav, daily_return = _compute_nav(prev_nav, updated_holdings)

    total_mv = sum(
        (h.get("market_value") or 0.0) for h in updated_holdings
    )

    # 4. Write to portfolio_nav_history
    await upsert_nav(
        trade_date=trade_date,
        nav=new_nav,
        total_mv=total_mv if total_mv else None,
        daily_return=daily_return,
    )
    log.info("NAV updated: date=%s nav=%.4f return=%.4f", trade_date, new_nav, daily_return)


async def _fetch_close_prices(
    symbols: list[str],
    trade_date: str,
    feature_client: "FeatureClient",
) -> dict[str, float]:
    """Try feature platform first, fall back to AKShare."""
    try:
        data = await feature_client.fetch_snapshot(
            symbols, trade_date, fields=["close_price"]
        )
        prices = {s: float(v["close_price"]) for s, v in data.items() if v.get("close_price")}
        if prices:
            return prices
    except Exception as exc:
        log.warning("Feature platform price fetch failed: %s — falling back to AKShare", exc)

    return await _akshare_close_prices(symbols)


async def _akshare_close_prices(symbols: list[str]) -> dict[str, float]:
    """AKShare fallback — runs in thread to avoid blocking event loop."""
    import asyncio

    def _sync_fetch() -> dict[str, float]:
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            df = df[df["代码"].isin(symbols)]
            return dict(zip(df["代码"], df["最新价"].astype(float)))
        except Exception as e:
            log.error("AKShare fallback failed: %s", e)
            return {}

    return await asyncio.to_thread(_sync_fetch)


# ── Pure helper ──────────────────────────────────────────────────────────────

def _compute_nav(
    prev_nav: float,
    holdings: list[dict],
) -> tuple[float, float]:
    """
    Weighted average return across holdings.
    Returns (new_nav, daily_return).
    """
    total_weight = sum(h.get("weight", 0.0) for h in holdings)
    if total_weight == 0:
        return prev_nav, 0.0

    weighted_return = 0.0
    for h in holdings:
        cp   = h.get("current_price")
        cost = h.get("cost_price")
        w    = h.get("weight", 0.0)
        if cp is not None and cost and cost > 0:
            pnl = (cp - cost) / cost
            weighted_return += w * pnl

    # Normalise by total weight (in case weights don't sum to 1)
    daily_return = weighted_return / total_weight
    new_nav = round(prev_nav * (1 + daily_return), 6)
    return new_nav, round(daily_return, 6)
```

- [ ] **Step 4: Run test**

```bash
pytest tests/test_units.py::test_compute_nav -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/services/nav_calculator.py backend/tests/test_units.py
git commit -m "feat: nav_calculator — close price fetch with feature client/AKShare fallback"
```

---

## Task 13: services/scheduler.py + main.py

**Files:**
- Create: `backend/services/scheduler.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Install APScheduler**

```bash
pip install apscheduler==3.10.4
```

- [ ] **Step 2: Write unit test for is_trading_day**

```python
# backend/tests/test_units.py  (add)
def test_is_trading_day_weekend():
    from services.scheduler import is_trading_day
    # 2026-04-04 is Saturday
    assert is_trading_day("2026-04-04") is False

def test_is_trading_day_weekday_fallback():
    from services.scheduler import is_trading_day
    # 2026-04-02 is Thursday — treat as trading day when no AKShare data
    assert is_trading_day("2026-04-02") is True
```

- [ ] **Step 3: Write services/scheduler.py**

```python
# backend/services/scheduler.py
"""
APScheduler integration.
All jobs call is_trading_day() at the start.
Trading calendar is cached locally; refreshed once per month from AKShare.
"""
from __future__ import annotations
import asyncio
import logging
from datetime import date, datetime
from pathlib import Path
import json

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger(__name__)

_CALENDAR_CACHE_FILE = Path(__file__).parent.parent / ".trading_calendar_cache.json"
_calendar: set[str] | None = None
_feature_client = None   # injected at startup


def init_scheduler(feature_client) -> AsyncIOScheduler:
    global _feature_client
    _feature_client = feature_client

    scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")

    scheduler.add_job(
        _job_prefetch, CronTrigger(day_of_week="mon-fri", hour=8, minute=30),
        id="prefetch_all", replace_existing=True,
    )
    scheduler.add_job(
        _job_factor_engine, CronTrigger(day_of_week="mon-fri", hour=8, minute=45),
        id="factor_engine", replace_existing=True,
    )
    scheduler.add_job(
        _job_nav_calculator, CronTrigger(day_of_week="mon-fri", hour=16, minute=0),
        id="nav_calculator", replace_existing=True,
    )
    scheduler.add_job(
        _job_settlement, CronTrigger(day_of_week="mon-fri", hour=16, minute=30),
        id="settlement", replace_existing=True,
    )
    scheduler.add_job(
        _refresh_calendar, CronTrigger(day="1", hour=7, minute=0),
        id="refresh_calendar", replace_existing=True,
    )
    return scheduler


# ── Job wrappers ──────────────────────────────────────────────────────────────

async def _job_prefetch():
    today = date.today().isoformat()
    if not is_trading_day(today):
        return
    try:
        await _feature_client.prefetch_all(today)
    except Exception as exc:
        log.error("prefetch_all failed: %s", exc)


async def _job_factor_engine():
    today = date.today().isoformat()
    if not is_trading_day(today):
        return
    try:
        from services.factor_engine import run_daily
        await run_daily(today, _feature_client)
    except Exception as exc:
        log.error("factor_engine job failed: %s", exc)


async def _job_nav_calculator():
    today = date.today().isoformat()
    if not is_trading_day(today):
        return
    try:
        from services.nav_calculator import run
        await run(today, _feature_client)
    except Exception as exc:
        log.error("nav_calculator job failed: %s", exc)


async def _job_settlement():
    today = date.today().isoformat()
    if not is_trading_day(today):
        return
    try:
        from services.settlement import run
        await run(today, _feature_client)
    except Exception as exc:
        log.error("settlement job failed: %s", exc)


# ── Trading calendar ──────────────────────────────────────────────────────────

def is_trading_day(trade_date: str) -> bool:
    """True if trade_date is a Chinese A-share trading day."""
    _load_calendar_if_needed()
    d = date.fromisoformat(trade_date)
    if d.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    if _calendar:
        return trade_date in _calendar
    # No calendar data: treat all weekdays as trading days
    return True


async def _refresh_calendar():
    """Monthly job: refresh AKShare trading calendar and save to disk."""
    try:
        import asyncio
        calendar_data = await asyncio.to_thread(_fetch_calendar_sync)
        _CALENDAR_CACHE_FILE.write_text(
            json.dumps({"dates": sorted(calendar_data), "updated": date.today().isoformat()})
        )
        global _calendar
        _calendar = set(calendar_data)
        log.info("Trading calendar refreshed: %d days", len(calendar_data))
    except Exception as exc:
        log.warning("Calendar refresh failed: %s", exc)


def _fetch_calendar_sync() -> list[str]:
    import akshare as ak
    df = ak.tool_trade_date_hist_sina()
    return df["trade_date"].astype(str).tolist()


def _load_calendar_if_needed():
    global _calendar
    if _calendar is not None:
        return
    if _CALENDAR_CACHE_FILE.exists():
        try:
            data = json.loads(_CALENDAR_CACHE_FILE.read_text())
            _calendar = set(data.get("dates", []))
        except Exception:
            pass
```

- [ ] **Step 4: Update main.py lifespan**

Read the current `main.py` first, then edit only the lifespan section:

```python
# backend/main.py  — replace or add lifespan context manager
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────
    from database import init_db, shutdown_db
    await init_db()

    from services.feature_client import make_feature_client
    from services.scheduler import init_scheduler
    _feature_client = make_feature_client()
    app.state.feature_client = _feature_client

    scheduler = init_scheduler(_feature_client)
    scheduler.start()
    app.state.scheduler = scheduler

    yield

    # ── Shutdown ──────────────────────────────────────────────────────
    scheduler.shutdown(wait=False)
    await _feature_client.close()
    await shutdown_db()


app = FastAPI(title="Quant AI Platform", lifespan=lifespan)
# ... rest of app unchanged
```

- [ ] **Step 5: Run scheduler tests**

```bash
pytest tests/test_units.py -k "trading_day" -v
```

Expected: Both `PASSED`

- [ ] **Step 6: Commit**

```bash
git add backend/services/scheduler.py backend/main.py backend/tests/test_units.py
git commit -m "feat: APScheduler wired into FastAPI lifespan — 4 daily jobs + calendar"
```

---

## Task 14: Update requirements.txt and Final Smoke Test

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Update requirements.txt**

Add to `backend/requirements.txt`:
```
asyncmy==0.2.9
apscheduler==3.10.4
numpy==1.26.4
pandas==2.2.1
scipy==1.13.0
httpx==0.27.0
```

- [ ] **Step 2: Run full unit test suite**

```bash
cd backend
pytest tests/test_units.py -v 2>&1 | tail -20
```

Expected: All tests `PASSED`, none `ERROR`

- [ ] **Step 3: Start the test DB if not already running, run integration smoke test**

```bash
docker compose -f docker-compose.test.yml up -d
cd backend
pytest tests/ -v -k "not test_api" --timeout=30 2>&1 | tail -30
```

Expected: All `PASSED`

- [ ] **Step 4: Final commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add asyncmy/apscheduler/numpy/pandas/scipy to requirements.txt"
```

---

## Self-Review Checklist

After completing all tasks, verify these points:

- [ ] `db/schema.sql` contains DDL for all 17 tables listed in spec Section 2 (including `ALTER TABLE` for approval_records + backtest_reports)
- [ ] `db/connection.py` `get_db_conn()` rolls back on exception, commits on success
- [ ] All `db/queries/` modules use `INSERT IGNORE` or `ON DUPLICATE KEY` for safe re-runs
- [ ] `agent_performance` inserts use `INSERT IGNORE` (UNIQUE KEY `uk_signal` enforces idempotency)
- [ ] `_detect_regime()` thresholds match spec: ±1% for return, 2.5% for volatility
- [ ] `_is_correct()` thresholds match spec: ±0.5%
- [ ] `FeatureClient` raises `ValueError` when required config is missing
- [ ] `is_trading_day()` returns `False` for weekends even when cache is empty
- [ ] `main.py` lifespan starts scheduler and feature client, shuts both down cleanly
- [ ] `conftest.py` seeds 4 agent_weight rows + 1 risk_config row before each test
- [ ] No SQLAlchemy import anywhere in `db/`, `services/`, or `main.py`

---

*Plan 1 complete. Proceed to Plan 2 (Backend API + Agent Layer) after all items above pass.*
