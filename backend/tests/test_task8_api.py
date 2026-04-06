import pytest


class TestTask8DecisionOrders:
    @pytest.mark.asyncio
    async def test_get_decision_orders_returns_stock_only_rows(self, client, completed_rebalance_run):
        response = await client.get(f"/api/v1/decisions/{completed_rebalance_run}/orders")
        assert response.status_code == 200
        rows = response.json()
        assert len(rows) == 1
        assert all("symbol" in row for row in rows)
        assert all(row["symbol"].isdigit() and len(row["symbol"]) == 6 for row in rows)


class TestTask8ApprovalModify:
    @pytest.mark.asyncio
    async def test_approval_modify_updates_decision_orders(self, client, pending_approval):
        aid = pending_approval["approval_id"]
        did = pending_approval["decision_id"]

        r = await client.put(f"/api/v1/approvals/{aid}/modify", json={
            "modified_weights": {"600519": 0.11},
            "reviewed_by": "tester",
        })
        assert r.status_code == 200

        orders_resp = await client.get(f"/api/v1/decisions/{did}/orders")
        assert orders_resp.status_code == 200
        orders = orders_resp.json()
        row = next(x for x in orders if x["symbol"] == "600519")
        assert abs(row["target_weight"] - 0.11) < 0.001


class TestTask8Candidate:
    @pytest.mark.asyncio
    async def test_list_candidates_returns_stock_only_unique_symbols(self, client, db_engine):
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import async_sessionmaker

        sf = async_sessionmaker(db_engine, expire_on_commit=False)
        async with sf() as db:
            await db.execute(text(
                "INSERT INTO decision_runs "
                "(id,mode,status,triggered_by,started_at,symbols,candidate_symbols,agent_signals,"
                "hallucination_events,recommendations,final_direction,risk_level) "
                "VALUES ('d-cand-1','rebalance','completed','user','2026-01-01T10:00:00',"
                "'[\"000001\",\"CSI300\"]','[\"600519\",\"300750\",\"CSI300\"]','[]','[]','[]','hold','low')"
            ))
            await db.commit()

        await client.post("/api/v1/portfolio/", json={"symbol": "002594", "weight": 0.08})

        r = await client.get("/api/v1/candidate/")
        assert r.status_code == 200
        payload = r.json()
        symbols = [row["symbol"] for row in payload["items"]]

        assert "600519" in symbols
        assert "300750" in symbols
        assert "000001" in symbols
        assert "002594" in symbols
        assert "CSI300" not in symbols
        assert len(symbols) == len(set(symbols))
