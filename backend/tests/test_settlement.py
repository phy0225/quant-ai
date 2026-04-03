import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from models import AgentPerformance, AgentWeightConfig, DecisionRun
from services import settlement as settlement_svc


@pytest.mark.asyncio
async def test_settlement_marks_agent_correctness(db_engine):
    sf = async_sessionmaker(db_engine, expire_on_commit=False)
    async with sf() as db:
        run = DecisionRun(
            id=str(uuid.uuid4()),
            mode="targeted",
            status="completed",
            symbols=["600519"],
            candidate_symbols=[],
            agent_signals=[],
            hallucination_events=[],
            recommendations=[],
        )
        db.add(run)
        db.add(
            AgentPerformance(
                id=str(uuid.uuid4()),
                decision_run_id=run.id,
                agent_signal_id=str(uuid.uuid4()),
                agent_type="technical",
                symbol="600519",
                predicted_direction="buy",
                settlement_date="2026-04-08",
            )
        )
        await db.commit()

    async with sf() as db:
        result = await settlement_svc.run(db, "2026-04-08")
        assert result["settled_count"] > 0

    async with sf() as db:
        row = (await db.execute(select(AgentPerformance))).scalars().first()
        assert row is not None
        assert row.actual_return is not None
        assert row.is_correct is not None
        assert row.settled_at is not None


@pytest.mark.asyncio
async def test_settlement_updates_dynamic_agent_weights(db_engine):
    sf = async_sessionmaker(db_engine, expire_on_commit=False)
    async with sf() as db:
        run = DecisionRun(
            id=str(uuid.uuid4()),
            mode="targeted",
            status="completed",
            symbols=["600519"],
            candidate_symbols=[],
            agent_signals=[],
            hallucination_events=[],
            recommendations=[],
        )
        db.add(run)
        db.add_all(
            [
                AgentPerformance(
                    id=str(uuid.uuid4()),
                    decision_run_id=run.id,
                    agent_signal_id=str(uuid.uuid4()),
                    agent_type="technical",
                    symbol="600519",
                    predicted_direction="buy",
                    settlement_date="2026-04-08",
                    actual_return=0.03,
                ),
                AgentPerformance(
                    id=str(uuid.uuid4()),
                    decision_run_id=run.id,
                    agent_signal_id=str(uuid.uuid4()),
                    agent_type="news",
                    symbol="600519",
                    predicted_direction="sell",
                    settlement_date="2026-04-08",
                    actual_return=-0.02,
                ),
            ]
        )
        await db.commit()

    async with sf() as db:
        await settlement_svc.run(db, "2026-04-08")

    async with sf() as db:
        weights = (await db.execute(select(AgentWeightConfig))).scalars().all()
        assert len(weights) >= 2
        assert all(w.weight > 0 for w in weights)


@pytest.mark.asyncio
async def test_rules_agent_weights_endpoint(client, db_engine):
    sf = async_sessionmaker(db_engine, expire_on_commit=False)
    async with sf() as db:
        run = DecisionRun(
            id=str(uuid.uuid4()),
            mode="targeted",
            status="completed",
            symbols=["000001"],
            candidate_symbols=[],
            agent_signals=[],
            hallucination_events=[],
            recommendations=[],
        )
        db.add(run)
        db.add(
            AgentPerformance(
                id=str(uuid.uuid4()),
                decision_run_id=run.id,
                agent_signal_id=str(uuid.uuid4()),
                agent_type="fundamental",
                symbol="000001",
                predicted_direction="buy",
                settlement_date="2026-04-08",
                actual_return=0.01,
            )
        )
        await db.commit()

    async with sf() as db:
        await settlement_svc.run(db, "2026-04-08")

    resp = await client.get("/api/v1/rules/agent-weights")
    assert resp.status_code == 200
    payload = resp.json()
    assert "items" in payload
    assert any(item["agent_type"] == "fundamental" for item in payload["items"])

