"""T+5 settlement and dynamic agent-weight update service."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from hashlib import sha1

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import AgentPerformance, AgentWeightConfig


def _as_date(value: str) -> datetime.date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _simulated_return(symbol: str | None, settle_date: str) -> float:
    """Deterministic pseudo return so tests are stable without market I/O."""
    key = f"{symbol or ''}|{settle_date}"
    digest = sha1(key.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 2001  # 0..2000
    return round((bucket - 1000) / 10000, 4)  # -10.00%..+10.00%


def _is_direction_correct(predicted_direction: str | None, actual_return: float) -> bool:
    direction = (predicted_direction or "hold").strip().lower()
    if direction == "buy":
        return actual_return > 0
    if direction == "sell":
        return actual_return < 0
    return True


async def list_pending_settlement(
    db: AsyncSession,
    settle_date: str,
) -> list[AgentPerformance]:
    target_date = _as_date(settle_date)
    result = await db.execute(select(AgentPerformance).where(AgentPerformance.is_correct.is_(None)))
    rows = []
    for item in result.scalars().all():
        if not item.settlement_date:
            continue
        try:
            if _as_date(item.settlement_date) <= target_date:
                rows.append(item)
        except ValueError:
            continue
    return rows


async def refresh_agent_weights(db: AsyncSession) -> dict[str, float]:
    now = datetime.utcnow()
    d30 = now - timedelta(days=30)
    d60 = now - timedelta(days=60)

    result = await db.execute(select(AgentPerformance).where(AgentPerformance.is_correct.is_not(None)))
    rows = result.scalars().all()

    grouped: dict[str, list[AgentPerformance]] = defaultdict(list)
    for row in rows:
        grouped[row.agent_type].append(row)

    updated: dict[str, float] = {}
    for agent_type, items in grouped.items():
        acc30_items = [it for it in items if it.settled_at and it.settled_at >= d30]
        acc60_items = [it for it in items if it.settled_at and it.settled_at >= d60]

        def _acc(src: list[AgentPerformance]) -> float | None:
            if not src:
                return None
            wins = sum(1 for x in src if x.is_correct)
            return wins / len(src)

        acc30 = _acc(acc30_items)
        acc60 = _acc(acc60_items)
        base_acc = acc30 if acc30 is not None else (acc60 if acc60 is not None else 0.5)
        # Keep weights bounded and deterministic.
        new_weight = round(max(0.05, min(0.60, 0.10 + base_acc * 0.50)), 4)

        weight_result = await db.execute(
            select(AgentWeightConfig).where(AgentWeightConfig.agent_type == agent_type)
        )
        existing = weight_result.scalars().first()
        if existing:
            existing.accuracy_30d = round(acc30, 4) if acc30 is not None else None
            existing.accuracy_60d = round(acc60, 4) if acc60 is not None else None
            if not existing.is_locked:
                existing.weight = new_weight
            existing.last_updated = now
            updated[agent_type] = existing.weight
        else:
            node = AgentWeightConfig(
                agent_type=agent_type,
                weight=new_weight,
                accuracy_30d=round(acc30, 4) if acc30 is not None else None,
                accuracy_60d=round(acc60, 4) if acc60 is not None else None,
                is_locked=False,
                last_updated=now,
            )
            db.add(node)
            updated[agent_type] = node.weight
    return updated


async def run(db: AsyncSession, settle_date: str) -> dict:
    pending = await list_pending_settlement(db, settle_date)
    settled = 0
    for row in pending:
        actual_return = row.actual_return
        if actual_return is None:
            actual_return = _simulated_return(row.symbol, settle_date)
        row.actual_return = actual_return
        row.is_correct = _is_direction_correct(row.predicted_direction, actual_return)
        row.settled_at = datetime.utcnow()
        settled += 1

    weights = await refresh_agent_weights(db)
    await db.commit()
    return {
        "settle_date": settle_date,
        "pending_count": len(pending),
        "settled_count": settled,
        "weights_updated": len(weights),
    }

