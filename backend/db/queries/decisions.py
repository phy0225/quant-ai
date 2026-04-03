from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any


def _encode(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    return value


async def insert_decision_run(conn, payload: dict[str, Any]) -> str:
    record = {
        "id": payload["id"],
        "mode": payload["mode"],
        "status": payload.get("status", "running"),
        "triggered_by": payload.get("triggered_by", "user"),
        "symbols": _encode(payload.get("symbols", [])),
        "candidate_symbols": _encode(payload.get("candidate_symbols", [])),
        "current_portfolio": _encode(payload.get("current_portfolio", {})),
        "factor_snapshot_id": payload.get("factor_snapshot_id"),
        "factor_date": _encode(payload.get("factor_date")),
        "strategy_version_id": payload.get("strategy_version_id"),
        "market_regime": payload.get("market_regime"),
        "final_direction": payload.get("final_direction"),
        "risk_level": payload.get("risk_level"),
        "error_message": payload.get("error_message"),
        "started_at": _encode(payload.get("started_at")),
        "completed_at": _encode(payload.get("completed_at")),
    }
    sql = """
    INSERT INTO decision_runs (
        id, mode, status, triggered_by, symbols, candidate_symbols, current_portfolio,
        factor_snapshot_id, factor_date, strategy_version_id, market_regime,
        final_direction, risk_level, error_message, started_at, completed_at
    ) VALUES (
        %(id)s, %(mode)s, %(status)s, %(triggered_by)s, %(symbols)s, %(candidate_symbols)s, %(current_portfolio)s,
        %(factor_snapshot_id)s, %(factor_date)s, %(strategy_version_id)s, %(market_regime)s,
        %(final_direction)s, %(risk_level)s, %(error_message)s, %(started_at)s, %(completed_at)s
    )
    """
    async with conn.cursor() as cursor:
        await cursor.execute(sql, record)
    return str(record["id"])


async def get_decision_run(conn, decision_id: str) -> dict[str, Any] | None:
    sql = """
    SELECT id, mode, status, triggered_by, symbols, candidate_symbols, current_portfolio,
           factor_snapshot_id, factor_date, strategy_version_id, market_regime,
           final_direction, risk_level, error_message, started_at, completed_at
      FROM decision_runs
     WHERE id = %s
    """
    async with conn.cursor() as cursor:
        await cursor.execute(sql, (decision_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row))


async def list_decision_runs(conn, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
    sql = """
    SELECT id, mode, status, triggered_by, started_at, completed_at, final_direction, risk_level
      FROM decision_runs
     ORDER BY started_at DESC
     LIMIT %s OFFSET %s
    """
    async with conn.cursor() as cursor:
        await cursor.execute(sql, (limit, offset))
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in rows]
