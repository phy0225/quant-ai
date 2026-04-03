"""
娴嬭瘯閰嶇疆 鈥?鍐呭瓨 SQLite锛屾瘡涓祴璇曞嚱鏁扮嫭绔嬫暟鎹簱锛屼簰涓嶅共鎵?
"""
from __future__ import annotations
import pytest
import pytest_asyncio
import uuid, json
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


@pytest.fixture
def app_settings():
    from config import settings
    return settings


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    from database import Base
    import models  # noqa: F401 - ensure ORM tables are registered before create_all
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 鎵€鏈夋祴璇曢兘闇€瑕侀粯璁ょ殑 risk_configs 璁板綍锛圲PDATE 璇彞渚濊禆瀹冨瓨鍦級
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
    """Inject test database into HTTP client."""
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

    # 鍒濆鍖栭粯璁ゆ暟鎹?
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


# 鈹€鈹€ 甯哥敤 fixture 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

@pytest_asyncio.fixture
async def pending_approval(client, db_engine):
    """Insert one pending approval record directly for API tests."""
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
            "(id,mode,status,triggered_by,started_at,symbols,candidate_symbols,agent_signals,"
            "hallucination_events,recommendations,final_direction,risk_level) "
            "VALUES (:id,'targeted','completed','user','2026-01-01T10:00:00',"
            "'[\"600519\"]','[]','[]','[]',:recs,'buy','low')"
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
async def completed_rebalance_run(db_engine):
    """插入一条已完成的 rebalance 决策，用于 orders 接口测试。"""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    decision_id = str(uuid.uuid4())
    recs = json.dumps([
        {
            "symbol": "600519",
            "current_weight": 0.10,
            "recommended_weight": 0.18,
            "weight_delta": 0.08,
            "confidence_score": 0.81,
            "reasoning": "increase core holding",
        },
        {
            "symbol": "CSI300",
            "current_weight": 0.00,
            "recommended_weight": 0.05,
            "weight_delta": 0.05,
            "confidence_score": 0.60,
            "reasoning": "non-stock benchmark leg",
        },
    ])
    async with session_factory() as db:
        from sqlalchemy import text
        await db.execute(text(
            "INSERT INTO decision_runs "
            "(id,mode,status,triggered_by,started_at,symbols,candidate_symbols,agent_signals,"
            "hallucination_events,recommendations,final_direction,risk_level) "
            "VALUES (:id,'rebalance','completed','user','2026-01-01T10:00:00',"
            "'[\"600519\",\"CSI300\"]','[\"600519\",\"300750\"]','[]','[]',:recs,'buy','low')"
        ), {"id": decision_id, "recs": recs})
        await db.commit()
    return decision_id


@pytest_asyncio.fixture
async def holding(client):
    r = await client.post("/api/v1/portfolio/", json={
        "symbol": "600519", "symbol_name": "璐靛窞鑼呭彴",
        "weight": 0.18, "cost_price": 1680.0, "quantity": 100,
    })
    return r.json()


@pytest_asyncio.fixture
async def rule(client):
    r = await client.post("/api/v1/rules/", json={
        "name": "灏忓箙璋冧粨瑙勫垯",
        "description": "璋冧粨 < 5% 鑷姩鎵瑰噯",
        "logic_operator": "AND",
        "conditions": [{"field": "max_weight_delta", "operator": "lte", "value": 0.05}],
        "is_active": True,
        "priority": 1,
    })
    return r.json()


@pytest_asyncio.fixture
async def graph_node(client, db_engine, approved_approval):
    """Return one generated graph node after an approval."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as db:
        from sqlalchemy import select
        from models import GraphNode
        result = await db.execute(select(GraphNode).limit(1))
        node = result.scalars().first()
        if node:
            return {"node_id": node.node_id}
    return None