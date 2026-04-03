from __future__ import annotations

import pytest


class _FakeFeatureClient:
    async def fetch_market(self, trade_date: str):
        return {
            "trade_date": trade_date,
            "market_return_5d": 0.03,
            "market_volatility_20d": 0.01,
        }

    async def fetch_industry(self, trade_date: str):
        return {"banking": {"entity_type": "industry", "trade_date": trade_date, "score": 0.55}}

    async def fetch_concept(self, trade_date: str):
        return {"high_dividend": {"entity_type": "concept", "trade_date": trade_date, "score": 0.58}}

    async def fetch_snapshot(self, symbols, trade_date, fields=None):
        return {
            symbol: {
                "entity_type": "stock",
                "trade_date": trade_date,
                "data_available": True,
                "fields": {"symbol": symbol, "current_price": 10.0, "change_pct": 1.0, "rsi": 56.0},
            }
            for symbol in symbols
        }


@pytest.mark.asyncio
async def test_run_daily_creates_factor_snapshot():
    from services.factor_engine import run_daily

    snapshot = await run_daily("2026-04-02", feature_client=_FakeFeatureClient())

    assert snapshot["trade_date"] == "2026-04-02"
    assert snapshot["market_regime"] == "bull_low_vol"
    assert "effective_factors" in snapshot
    assert len(snapshot["effective_factors"]) >= 1
    assert "stock_scores" in snapshot


def test_detect_regime_distinguishes_market_states():
    from services.factor_engine import _detect_regime

    assert _detect_regime({"market_return_5d": 0.03, "market_volatility_20d": 0.02}) == "bull_high_vol"
    assert _detect_regime({"market_return_5d": -0.03, "market_volatility_20d": 0.01}) == "bear_low_vol"
    assert _detect_regime({"market_return_5d": 0.0, "market_volatility_20d": 0.01}) == "sideways"
