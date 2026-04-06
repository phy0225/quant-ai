import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker


@pytest.mark.asyncio
async def test_graph_node_contains_mode_and_factor_snapshot(client, db_engine):
    sf = async_sessionmaker(db_engine, expire_on_commit=False)
    decision_id = str(uuid.uuid4())
    approval_id = str(uuid.uuid4())
    recs = json.dumps(
        [
            {
                "symbol": "600519",
                "current_weight": 0.12,
                "recommended_weight": 0.2,
                "weight_delta": 0.08,
                "confidence_score": 0.77,
                "similar_cases": [],
            }
        ]
    )

    async with sf() as db:
        await db.execute(
            text(
                "INSERT INTO decision_runs "
                "(id,mode,status,triggered_by,started_at,symbols,candidate_symbols,agent_signals,"
                "hallucination_events,recommendations,final_direction,risk_level) "
                "VALUES (:id,'rebalance','completed','user','2026-01-01T10:00:00',"
                "'[\"600519\"]','[\"600519\",\"300750\"]','[]','[]',:recs,'buy','low')"
            ),
            {"id": decision_id, "recs": recs},
        )
        await db.execute(
            text(
                "INSERT INTO approval_records "
                "(id,decision_run_id,status,recommendations,created_at) "
                "VALUES (:id,:did,'pending',:recs,'2026-01-01T10:00:00')"
            ),
            {"id": approval_id, "did": decision_id, "recs": recs},
        )
        await db.commit()

    approve_resp = await client.post(
        f"/api/v1/approvals/{approval_id}/action",
        json={"action": "approved", "reviewed_by": "tester"},
    )
    assert approve_resp.status_code == 200

    response = await client.get("/api/v1/graph/nodes")
    assert response.status_code == 200
    payload = response.json()
    first = payload["items"][0]
    assert "mode" in first
    assert "factor_snapshot" in first
    assert first["mode"] == "rebalance"


@pytest.mark.asyncio
async def test_graph_network_returns_nodes_and_edges(client, db_engine):
    sf = async_sessionmaker(db_engine, expire_on_commit=False)
    decision_one = str(uuid.uuid4())
    decision_two = str(uuid.uuid4())
    approval_one = str(uuid.uuid4())
    approval_two = str(uuid.uuid4())
    recs_one = json.dumps([{"symbol": "600519", "recommended_weight": 0.2}])
    recs_two = json.dumps([{"symbol": "600519", "recommended_weight": 0.1}, {"symbol": "300750", "recommended_weight": 0.15}])

    async with sf() as db:
        await db.execute(
            text(
                "INSERT INTO decision_runs "
                "(id,mode,status,triggered_by,started_at,symbols,candidate_symbols,agent_signals,hallucination_events,recommendations,final_direction,risk_level) "
                "VALUES (:id,'rebalance','completed','user','2026-01-01T10:00:00','[\"600519\"]','[]','[]','[]',:recs,'buy','low')"
            ),
            {"id": decision_one, "recs": recs_one},
        )
        await db.execute(
            text(
                "INSERT INTO decision_runs "
                "(id,mode,status,triggered_by,started_at,symbols,candidate_symbols,agent_signals,hallucination_events,recommendations,final_direction,risk_level) "
                "VALUES (:id,'rebalance','completed','user','2026-01-02T10:00:00','[\"600519\",\"300750\"]','[]','[]','[]',:recs,'buy','low')"
            ),
            {"id": decision_two, "recs": recs_two},
        )
        await db.execute(
            text(
                "INSERT INTO approval_records (id,decision_run_id,status,recommendations,created_at) "
                "VALUES (:id,:did,'pending',:recs,'2026-01-01T10:00:00')"
            ),
            {"id": approval_one, "did": decision_one, "recs": recs_one},
        )
        await db.execute(
            text(
                "INSERT INTO approval_records (id,decision_run_id,status,recommendations,created_at) "
                "VALUES (:id,:did,'pending',:recs,'2026-01-02T10:00:00')"
            ),
            {"id": approval_two, "did": decision_two, "recs": recs_two},
        )
        await db.commit()

    for approval_id in (approval_one, approval_two):
        approve_resp = await client.post(
            f"/api/v1/approvals/{approval_id}/action",
            json={"action": "approved", "reviewed_by": "tester"},
        )
        assert approve_resp.status_code == 200

    response = await client.get("/api/v1/graph/network")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["nodes"]) >= 2
    assert payload["total_nodes"] >= 2
    assert "edges" in payload
    assert payload["total_edges"] >= 1
    first_edge = payload["edges"][0]
    assert "source" in first_edge
    assert "target" in first_edge
    assert "strength" in first_edge
