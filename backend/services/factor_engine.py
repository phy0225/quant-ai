from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from services.feature_client import FeatureClient

IC_THRESHOLD = 0.03
IC_IR_THRESHOLD = 0.40
ROLLING_WINDOW = 60


def _detect_regime(market_features: dict[str, Any]) -> str:
    market_return = float(market_features.get("market_return_5d", 0.0) or 0.0)
    market_vol = float(market_features.get("market_volatility_20d", 0.0) or 0.0)
    if market_return > 0.02 and market_vol > 0.015:
        return "bull_high_vol"
    if market_return > 0.02:
        return "bull_low_vol"
    if market_return < -0.02 and market_vol > 0.015:
        return "bear_high_vol"
    if market_return < -0.02:
        return "bear_low_vol"
    return "sideways"


async def run_daily(trade_date: str, feature_client: FeatureClient | None = None) -> dict[str, Any]:
    client = feature_client or FeatureClient()
    market = await client.fetch_market(trade_date)
    industry = await client.fetch_industry(trade_date)
    concept = await client.fetch_concept(trade_date)

    effective_factors = [
        {"factor_key": "momentum_20d", "ic": 0.05, "ic_ir": 0.62, "direction": 1, "weight": 0.5},
        {"factor_key": "quality_roe", "ic": 0.04, "ic_ir": 0.51, "direction": 1, "weight": 0.3},
        {"factor_key": "valuation_pb", "ic": -0.03, "ic_ir": 0.44, "direction": -1, "weight": 0.2},
    ]

    stock_scores = defaultdict(dict)
    stock_snapshots = await client.fetch_snapshot(["600036", "600519", "000001"], trade_date)
    for symbol, payload in stock_snapshots.items():
        fields = payload.get("fields", {})
        stock_scores[symbol] = {
            "composite_score": round(min(max((float(fields.get("rsi", 50.0)) - 20.0) / 60.0, 0.0), 1.0), 4),
            "price": fields.get("current_price"),
            "change_pct": fields.get("change_pct"),
        }

    return {
        "id": f"factor-snapshot-{trade_date}",
        "trade_date": trade_date,
        "market_regime": _detect_regime(market),
        "effective_factors": effective_factors,
        "stock_scores": dict(stock_scores),
        "industry_scores": industry,
        "concept_scores": concept,
        "market_factors": market,
        "created_at": datetime.now().isoformat(),
    }
