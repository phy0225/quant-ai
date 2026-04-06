"""Candidate pool endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import DecisionRun, PortfolioHolding

router = APIRouter(prefix="/api/v1/candidate", tags=["candidate"])


def _is_stock_symbol(symbol: str) -> bool:
    normalized = str(symbol or "").strip().upper()
    return normalized.isdigit() and len(normalized) == 6


def _normalize_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper()


@router.get("/")
async def list_candidates(
    limit: int = Query(default=200, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    source_map: dict[str, set[str]] = {}
    name_map: dict[str, str] = {}

    decision_result = await db.execute(
        select(DecisionRun)
        .where(DecisionRun.mode == "rebalance")
        .order_by(DecisionRun.started_at.desc())
        .limit(limit)
    )
    for run in decision_result.scalars().all():
        merged_symbols = [*(run.symbols or []), *(getattr(run, "candidate_symbols", []) or [])]
        for raw_symbol in merged_symbols:
            symbol = _normalize_symbol(raw_symbol)
            if not _is_stock_symbol(symbol):
                continue
            source_map.setdefault(symbol, set()).add("decision")

    holding_result = await db.execute(select(PortfolioHolding))
    for holding in holding_result.scalars().all():
        symbol = _normalize_symbol(holding.symbol)
        if not _is_stock_symbol(symbol):
            continue
        source_map.setdefault(symbol, set()).add("portfolio")
        if holding.symbol_name:
            name_map[symbol] = holding.symbol_name

    items = [
        {
            "symbol": symbol,
            "symbol_name": name_map.get(symbol),
            "sources": sorted(source_map[symbol]),
        }
        for symbol in sorted(source_map.keys())
    ]
    return {"items": items[:limit], "total": len(items)}
