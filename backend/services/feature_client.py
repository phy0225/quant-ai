from __future__ import annotations

from datetime import date, datetime
from typing import Any

from config import settings
from services.market_data_adapter import get_provider


def _normalize_trade_date(value: str | date | datetime | None) -> str:
    if value is None:
        return datetime.now().strftime("%Y-%m-%d")
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.isoformat()
    return value


class FeatureClient:
    """
    Unified feature access layer for stock, market, industry, and concept reads.

    The first implementation is intentionally thin: it wraps the existing provider
    layer and exposes a stable v3 interface while the real feature platform adapter
    is being rolled out.
    """

    def __init__(self, mode: str | None = None):
        self.mode = mode or settings.FEATURE_PLATFORM_MODE

    async def fetch_snapshot(
        self,
        symbols: list[str],
        date: str | date | datetime | None = None,
        fields: list[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        trade_date = _normalize_trade_date(date)
        provider = get_provider()
        result: dict[str, dict[str, Any]] = {}
        for symbol in symbols:
            snapshot = await provider.get_snapshot(symbol)
            if snapshot is None:
                result[symbol] = {
                    "entity_type": "stock",
                    "trade_date": trade_date,
                    "data_available": False,
                    "fields": {},
                }
                continue

            payload = snapshot.to_dict()
            filtered = payload if not fields else {key: payload.get(key) for key in fields}
            result[symbol] = {
                "entity_type": "stock",
                "trade_date": trade_date,
                "data_available": True,
                "fields": filtered,
            }
        return result

    async def fetch_history(
        self,
        symbols: list[str],
        start: str,
        end: str,
        fields: list[str] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        snapshots = await self.fetch_snapshot(symbols, end, fields=fields)
        return {
            symbol: [payload | {"start_date": start, "end_date": end}]
            for symbol, payload in snapshots.items()
        }

    async def fetch_market(self, date: str | date | datetime | None = None) -> dict[str, Any]:
        trade_date = _normalize_trade_date(date)
        return {
            "trade_date": trade_date,
            "market_return_5d": 0.0,
            "market_volatility_20d": 0.0,
            "market_breadth": 0.5,
        }

    async def fetch_industry(self, date: str | date | datetime | None = None) -> dict[str, dict[str, Any]]:
        trade_date = _normalize_trade_date(date)
        return {
            "banking": {"entity_type": "industry", "trade_date": trade_date, "score": 0.5},
            "liquor": {"entity_type": "industry", "trade_date": trade_date, "score": 0.5},
        }

    async def fetch_concept(self, date: str | date | datetime | None = None) -> dict[str, dict[str, Any]]:
        trade_date = _normalize_trade_date(date)
        return {
            "state_owned_enterprise": {"entity_type": "concept", "trade_date": trade_date, "score": 0.5},
            "high_dividend": {"entity_type": "concept", "trade_date": trade_date, "score": 0.5},
        }

    async def prefetch_all(self, date: str | date | datetime | None = None) -> dict[str, Any]:
        trade_date = _normalize_trade_date(date)
        market = await self.fetch_market(trade_date)
        industry = await self.fetch_industry(trade_date)
        concept = await self.fetch_concept(trade_date)
        return {
            "trade_date": trade_date,
            "market": market,
            "industry_count": len(industry),
            "concept_count": len(concept),
        }
