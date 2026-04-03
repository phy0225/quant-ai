from __future__ import annotations

import pytest


class _FakeSnapshot:
    def __init__(self, payload):
        self._payload = payload

    def to_dict(self):
        return self._payload


class _FakeProvider:
    async def get_snapshot(self, symbol: str):
        return _FakeSnapshot({
            "symbol": symbol,
            "current_price": 12.3,
            "change_pct": 1.2,
            "rsi": 55.0,
        })


@pytest.mark.asyncio
async def test_feature_client_fetches_snapshot_for_multiple_entity_types(monkeypatch):
    from services.feature_client import FeatureClient

    monkeypatch.setattr("services.feature_client.get_provider", lambda: _FakeProvider())

    client = FeatureClient()
    result = await client.fetch_snapshot(["600036"], "2026-04-02")

    assert "600036" in result
    assert result["600036"]["entity_type"] == "stock"
    assert result["600036"]["trade_date"] == "2026-04-02"
    assert result["600036"]["data_available"] is True
    assert result["600036"]["fields"]["symbol"] == "600036"


@pytest.mark.asyncio
async def test_feature_client_prefetch_all_returns_summary():
    from services.feature_client import FeatureClient

    client = FeatureClient()
    result = await client.prefetch_all("2026-04-02")

    assert result["trade_date"] == "2026-04-02"
    assert result["industry_count"] >= 1
    assert result["concept_count"] >= 1
