"""Portfolio NAV helpers for the v3 daily snapshot workflow."""
from __future__ import annotations

from datetime import date, datetime
from typing import Iterable


def _normalize_trade_date(trade_date: str | date | datetime | None = None) -> str:
    if trade_date is None:
        return datetime.now().date().isoformat()
    if isinstance(trade_date, datetime):
        return trade_date.date().isoformat()
    if isinstance(trade_date, date):
        return trade_date.isoformat()
    return str(trade_date)


def calculate_nav(holdings: Iterable[dict]) -> dict:
    """Calculate a simple NAV snapshot from stock holdings.

    The current project stores holdings in multiple shapes, so this helper keeps
    the math tolerant and deterministic for both unit tests and future jobs.
    """
    normalized = list(holdings)
    total_weight = sum(float(item.get("weight", 0.0) or 0.0) for item in normalized)
    total_market_value = sum(float(item.get("market_value", 0.0) or 0.0) for item in normalized)
    weighted_pnl = sum(
        float(item.get("weight", 0.0) or 0.0) * float(item.get("pnl_pct", 0.0) or 0.0)
        for item in normalized
    )

    avg_pnl = weighted_pnl / total_weight if total_weight > 0 else 0.0
    # Treat uninvested cash as zero-return exposure so NAV reflects the full book.
    nav = 1.0 + weighted_pnl
    cash_weight = max(0.0, 1.0 - total_weight)

    return {
        "nav": round(nav, 6),
        "gross_exposure": round(total_weight, 4),
        "cash_weight": round(cash_weight, 4),
        "total_market_value": round(total_market_value, 2),
        "holding_count": len(normalized),
        "avg_pnl_pct": round(avg_pnl, 4),
    }


def build_nav_snapshot(holdings: Iterable[dict], trade_date: str | date | datetime | None = None) -> dict:
    metrics = calculate_nav(holdings)
    metrics["trade_date"] = _normalize_trade_date(trade_date)
    return metrics
