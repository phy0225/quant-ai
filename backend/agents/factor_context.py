"""Helpers for building deterministic factor context for pipeline decisions."""
from __future__ import annotations

from typing import Any

from services.factor_engine import run_daily


def _normalize_stock_score(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for key in ("score", "final_score", "value", "stock_score"):
            candidate = value.get(key)
            if isinstance(candidate, (int, float)):
                return float(candidate)
    return 0.5


async def build_factor_context(
    symbols: list[str],
    candidate_symbols: list[str] | None = None,
    trade_date: str | None = None,
    factor_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot = factor_snapshot or await run_daily(trade_date or "latest")
    scored_stocks = snapshot.get("stock_scores", {}) or {}
    effective = snapshot.get("effective_factors", []) or []

    merged_symbols: list[str] = []
    seen: set[str] = set()
    for symbol in [*(symbols or []), *(candidate_symbols or [])]:
        normalized = str(symbol).strip().upper()
        if normalized and normalized not in seen:
            seen.add(normalized)
            merged_symbols.append(normalized)

    return {
        "factor_date": snapshot.get("trade_date", trade_date),
        "market_regime": snapshot.get("market_regime", "unknown"),
        "effective_factors": effective,
        "factor_count": len(effective),
        "scored_stocks": {symbol: _normalize_stock_score(scored_stocks.get(symbol, 0.5)) for symbol in merged_symbols},
        "raw_snapshot": snapshot,
    }
