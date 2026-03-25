"""
测试配置 — 内存 SQLite，每个测试函数独立数据库，互不干扰
"""
from __future__ import annotations
import pytest
import pytest_asyncio
import uuid, json
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    from database import Base
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 所有测试都需要默认的 risk_configs 记录（UPDATE 语句依赖它存在）
    sf = async_sessionmaker(engine, expire_on_commit=False)
    async with sf() as db:
        from models import RiskConfig
        from sqlalchemy import select
        result = await db.execute(select(RiskConfig))
        if not result.scalars().first():
            db.add(RiskConfig(
                id=1,
                max_position_weight=0.20,
                daily_loss_warning_threshold=0.03,
                daily_loss_suspend_threshold=0.06,
                max_drawdown_emergency=0.15,
                circuit_breaker_level=0,
                emergency_stop_active=False,
            ))
            await db.commit()

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(db_engine):
    """注入测试数据库的 HTTP 客户端"""
    from database import get_db
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

    from main import app
    app.dependency_overrides[get_db] = override_get_db

    # 初始化默认数据
    async with session_factory() as db:
        from models import RiskConfig
        from sqlalchemy import select
        result = await db.execute(select(RiskConfig))
        if not result.scalars().first():
            db.add(RiskConfig(
                id=1,
                max_position_weight=0.20,
                daily_loss_warning_threshold=0.03,
                daily_loss_suspend_threshold=0.06,
                max_drawdown_emergency=0.15,
                circuit_breaker_level=0,
                emergency_stop_active=False,
            ))
            await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ── 常用 fixture ──────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def pending_approval(client, db_engine):
    """直接插入一条待审批记录（跳过 pipeline 耗时）"""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    decision_id = str(uuid.uuid4())
    approval_id = str(uuid.uuid4())
    recs = json.dumps([{
        "symbol": "600519",
        "current_weight": 0.18,
        "recommended_weight": 0.20,
        "weight_delta": 0.02,
        "confidence_score": 0.72,
        "similar_cases": [],
    }])
    async with session_factory() as db:
        from sqlalchemy import text
        await db.execute(text(
            "INSERT INTO decision_runs "
            "(id,status,triggered_by,started_at,symbols,agent_signals,"
            "hallucination_events,recommendations,final_direction,risk_level) "
            "VALUES (:id,'completed','user','2026-01-01T10:00:00',"
            "'[\"600519\"]','[]','[]',:recs,'buy','low')"
        ), {"id": decision_id, "recs": recs})
        await db.execute(text(
            "INSERT INTO approval_records "
            "(id,decision_run_id,status,recommendations,created_at) "
            "VALUES (:id,:did,'pending',:recs,'2026-01-01T10:00:00')"
        ), {"id": approval_id, "did": decision_id, "recs": recs})
        await db.commit()
    return {"decision_id": decision_id, "approval_id": approval_id}


@pytest_asyncio.fixture
async def approved_approval(client, pending_approval):
    aid = pending_approval["approval_id"]
    await client.post(f"/api/v1/approvals/{aid}/action", json={
        "action": "approved", "reviewed_by": "tester"
    })
    return pending_approval


@pytest_asyncio.fixture
async def holding(client):
    r = await client.post("/api/v1/portfolio/", json={
        "symbol": "600519", "symbol_name": "贵州茅台",
        "weight": 0.18, "cost_price": 1680.0, "quantity": 100,
    })
    return r.json()


@pytest_asyncio.fixture
async def rule(client):
    r = await client.post("/api/v1/rules/", json={
        "name": "小幅调仓规则",
        "description": "调仓 < 5% 自动批准",
        "logic_operator": "AND",
        "conditions": [{"field": "max_weight_delta", "operator": "lte", "value": 0.05}],
        "is_active": True,
        "priority": 1,
    })
    return r.json()


@pytest_asyncio.fixture
async def graph_node(client, db_engine, approved_approval):
    """审批通过后会自动生成图谱节点，返回节点信息"""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as db:
        from sqlalchemy import select
        from models import GraphNode
        result = await db.execute(select(GraphNode).limit(1))
        node = result.scalars().first()
        if node:
            return {"node_id": node.node_id}
    return None