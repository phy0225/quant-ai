"""Decision trigger and query endpoints."""
from __future__ import annotations
import asyncio, traceback, json
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from database import get_db, AsyncSessionLocal
from models import ApprovalRecord, DecisionRun, RiskConfig
from agents.pipeline import run_decision_pipeline
from services.graph import get_similar_cases
from websocket_manager import manager

router = APIRouter(prefix="/api/v1/decisions", tags=["decisions"])


class DecisionTriggerPayload(BaseModel):
    mode: str = "targeted"
    symbols: list[str] = Field(default_factory=list)
    candidate_symbols: list[str] = Field(default_factory=list)
    current_portfolio: dict[str, float] | None = None

    @model_validator(mode="after")
    def validate_mode_payload(self):
        self.mode = (self.mode or "targeted").strip().lower()
        self.symbols = [str(symbol).strip().upper() for symbol in self.symbols if str(symbol).strip()]
        self.candidate_symbols = [
            str(symbol).strip().upper() for symbol in self.candidate_symbols if str(symbol).strip()
        ]
        if self.mode not in {"targeted", "rebalance"}:
            raise ValueError("mode must be targeted or rebalance")
        if self.mode == "targeted" and not self.symbols:
            raise ValueError("targeted mode requires at least one symbol")
        if self.mode == "rebalance" and not (self.symbols or self.candidate_symbols or self.current_portfolio):
            raise ValueError("rebalance mode requires symbols, candidate_symbols, or current_portfolio")
        return self

    def resolved_symbols(self) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        portfolio_symbols = list((self.current_portfolio or {}).keys())
        for symbol in [*self.symbols, *self.candidate_symbols, *portfolio_symbols]:
            normalized = str(symbol).strip().upper()
            if normalized and normalized not in seen:
                seen.add(normalized)
                merged.append(normalized)
        return merged


def _fmt(dt) -> str | None:
    return dt.isoformat() if dt else None


def _serialize_run(run: DecisionRun) -> dict:
    return {
        "id": run.id,
        "mode": getattr(run, "mode", "targeted"),
        "status": run.status,
        "triggered_by": run.triggered_by,
        "started_at": _fmt(run.started_at),
        "completed_at": _fmt(run.completed_at),
        "symbols": run.symbols or [],
        "candidate_symbols": getattr(run, "candidate_symbols", []) or [],
        "recommendations": run.recommendations or [],
        "agent_signals": run.agent_signals or [],
        "hallucination_events": run.hallucination_events or [],
        "final_direction": run.final_direction,
        "risk_level": run.risk_level,
        "error_message": run.error_message,
    }


async def _db_updater(decision_id: str, **kwargs):
    """
    Use raw SQL UPDATE so SQLAlchemy JSON-tracking issues are completely bypassed.
    """
    async with AsyncSessionLocal() as db:
        try:
            # Build SET clause dynamically
            set_parts = []
            bind_params = {"did": decision_id}

            for k, v in kwargs.items():
                set_parts.append(f"{k} = :{k}")
                if isinstance(v, (list, dict)):
                    bind_params[k] = json.dumps(v)
                elif isinstance(v, datetime):
                    bind_params[k] = v.isoformat()
                else:
                    bind_params[k] = v

            if not set_parts:
                return

            sql = f"UPDATE decision_runs SET {', '.join(set_parts)} WHERE id = :did"
            await db.execute(text(sql), bind_params)
            await db.commit()

            signals_count = len(kwargs.get("agent_signals") or [])
            print(f"[db_updater] OK  fields={list(kwargs.keys())}  signals={signals_count}")

            # Auto-create approval on completion
            if kwargs.get("status") == "completed":
                recs_json = json.dumps(kwargs.get("recommendations", []))
                import uuid
                approval_id = str(uuid.uuid4())
                now_iso = datetime.now().isoformat()
                await db.execute(text(
                    "INSERT INTO approval_records "
                    "(id, decision_run_id, status, recommendations, created_at) "
                    "VALUES (:id, :did, 'pending', :recs, :now)"
                ), {"id": approval_id, "did": decision_id, "recs": recs_json, "now": now_iso})
                await db.commit()
                print(f"[db_updater] approval created: {approval_id}")

        except Exception as e:
            print(f"[db_updater] ERROR: {e}")
            traceback.print_exc()


async def _background_pipeline(
    decision_id: str,
    symbols: list,
    current_portfolio: dict | None,
    risk_cfg: dict,
):
    try:
        await run_decision_pipeline(
            decision_id=decision_id,
            symbols=symbols,
            current_portfolio=current_portfolio,
            db_updater=_db_updater,
            risk_cfg=risk_cfg,
            ws_broadcaster=manager.broadcast,
        )
    except Exception as e:
        print(f"[background_pipeline] FATAL: {e}")
        traceback.print_exc()
        async with AsyncSessionLocal() as db:
            try:
                now_iso = datetime.now().isoformat()
                await db.execute(text(
                    "UPDATE decision_runs SET status='failed', error_message=:msg, completed_at=:now WHERE id=:did"
                ), {"msg": str(e), "now": now_iso, "did": decision_id})
                await db.commit()
            except Exception:
                pass


@router.post("/trigger")
async def trigger_decision(
    payload: DecisionTriggerPayload,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(RiskConfig))
    cfg = result.scalars().first()
    if cfg and cfg.emergency_stop_active:
        raise HTTPException(status_code=503, detail="System is in emergency stop mode.")

    symbols = payload.resolved_symbols()
    run = DecisionRun(
        mode=payload.mode,
        symbols=symbols,
        candidate_symbols=payload.candidate_symbols,
        current_portfolio=payload.current_portfolio,
        triggered_by="user",
        status="running",
        agent_signals=[],
        hallucination_events=[],
        recommendations=[],
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    risk_cfg = {}
    if cfg:
        risk_cfg = {
            "max_position_weight": cfg.max_position_weight,
            "daily_loss_warning_threshold": cfg.daily_loss_warning_threshold,
        }

    # 浠庢寔浠撹〃璇诲彇瀹屾暣鎸佷粨鏁版嵁锛堝惈鎴愭湰浠枫€佹诞鐩堢瓑锛夛紝娉ㄥ叆 pipeline context
    from models import PortfolioHolding
    portfolio_result = await db.execute(select(PortfolioHolding))
    all_holdings = portfolio_result.scalars().all()
    full_portfolio = {}
    if all_holdings:
        for h in all_holdings:
            full_portfolio[h.symbol] = {
                "weight":        h.weight,
                "cost_price":    h.cost_price,
                "current_price": h.current_price,
                "pnl_pct":       h.pnl_pct,
                "quantity":      h.quantity,
                "market_value":  h.market_value,
                "symbol_name":   h.symbol_name,
            }
    # 濡傛灉鍓嶇浼犱簡鎸佷粨锛屽悎骞惰繘鏉ワ紙鍓嶇鏁版嵁浼樺厛 weight 瀛楁锛?
    if payload.current_portfolio:
        for sym, wt in payload.current_portfolio.items():
            if sym in full_portfolio:
                full_portfolio[sym]["weight"] = wt
            else:
                full_portfolio[sym] = {"weight": wt}

    print(f"[trigger] decision={run.id}  symbols={payload.symbols}  portfolio={len(full_portfolio)}鍙?)
    asyncio.create_task(
        _background_pipeline(run.id, payload.symbols, full_portfolio, risk_cfg)
    )
    return _serialize_run(run)


@router.get("/")
async def list_decisions(page: int = 1, page_size: int = 20, db: AsyncSession = Depends(get_db)):
    offset = (page - 1) * page_size
    total = (await db.execute(select(func.count(DecisionRun.id)))).scalar() or 0
    result = await db.execute(
        select(DecisionRun).order_by(DecisionRun.started_at.desc()).offset(offset).limit(page_size)
    )
    return {
        "items": [_serialize_run(r) for r in result.scalars().all()],
        "total": total, "page": page, "page_size": page_size,
    }


@router.get("/stats")
async def get_decision_stats(
    symbol: Optional[str] = Query(default=None),
    days: int = Query(default=30),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.now() - timedelta(days=days)
    result = await db.execute(
        select(DecisionRun)
        .where(DecisionRun.status == "completed")
        .where(DecisionRun.started_at >= cutoff)
    )
    runs = result.scalars().all()

    # Python-side symbol filter (symbols is a JSON list)
    if symbol:
        runs = [r for r in runs if symbol in (r.symbols or [])]

    # Aggregate per symbol
    sym_data: dict = defaultdict(lambda: {
        "count": 0,
        "directions": [],
        "confidences": [],
        "last_direction": None,
        "last_analyzed_at": None,
    })

    for run in runs:
        syms = run.symbols or []
        for sym in syms:
            d = sym_data[sym]
            d["count"] += 1
            if run.final_direction:
                d["directions"].append(run.final_direction)
            for sig in (run.agent_signals or []):
                if isinstance(sig, dict) and sig.get("agent_type") not in ("risk", "executor"):
                    conf = sig.get("confidence")
                    if conf is not None:
                        try:
                            d["confidences"].append(float(conf))
                        except (TypeError, ValueError):
                            pass
            run_ts = run.started_at.isoformat() if run.started_at else None
            if run_ts and (d["last_analyzed_at"] is None or run_ts > d["last_analyzed_at"]):
                d["last_direction"] = run.final_direction
                d["last_analyzed_at"] = run_ts

    symbol_stats = []
    for sym, data in sym_data.items():
        direction_dist: dict[str, int] = {}
        for dir_ in data["directions"]:
            direction_dist[dir_] = direction_dist.get(dir_, 0) + 1
        avg_conf = None
        if data["confidences"]:
            avg_conf = round(sum(data["confidences"]) / len(data["confidences"]), 4)
        symbol_stats.append({
            "symbol": sym,
            "decision_count": data["count"],
            "direction_dist": direction_dist,
            "avg_confidence": avg_conf,
            "last_direction": data["last_direction"],
            "last_analyzed_at": data["last_analyzed_at"],
        })

    return {
        "total_decisions": len(runs),
        "symbol_stats": symbol_stats,
        "generated_at": datetime.now().isoformat(),
    }




def _is_stock_symbol(symbol: str) -> bool:
    normalized = str(symbol or "").strip().upper()
    return normalized.isdigit() and len(normalized) == 6


def _to_order_row(row: dict) -> dict:
    symbol = str(row.get("symbol", "")).strip().upper()
    current_weight = float(row.get("current_weight") or 0.0)
    target_weight = row.get("recommended_weight")
    if target_weight is None:
        target_weight = row.get("target_weight")
    target_weight = float(target_weight or 0.0)

    raw_delta = row.get("weight_delta")
    try:
        weight_delta = float(raw_delta) if raw_delta is not None else round(target_weight - current_weight, 4)
    except (TypeError, ValueError):
        weight_delta = round(target_weight - current_weight, 4)

    action = row.get("action")
    if not action:
        if weight_delta > 0:
            action = "buy"
        elif weight_delta < 0:
            action = "sell"
        else:
            action = "hold"

    return {
        "symbol": symbol,
        "symbol_name": row.get("symbol_name"),
        "action": action,
        "current_weight": current_weight,
        "target_weight": target_weight,
        "weight_delta": weight_delta,
        "confidence_score": row.get("confidence_score"),
        "reasoning": row.get("reasoning") or row.get("reasoning_summary"),
    }


@router.get("/{decision_id}/orders")
async def get_decision_orders(decision_id: str, db: AsyncSession = Depends(get_db)):
    run_result = await db.execute(select(DecisionRun).where(DecisionRun.id == decision_id))
    run = run_result.scalars().first()
    if not run:
        raise HTTPException(status_code=404, detail="Decision not found.")

    approval_result = await db.execute(
        select(ApprovalRecord)
        .where(ApprovalRecord.decision_run_id == decision_id)
        .order_by(ApprovalRecord.created_at.desc())
    )
    latest_approval = approval_result.scalars().first()

    source_rows = []
    if latest_approval and latest_approval.recommendations:
        source_rows = list(latest_approval.recommendations or [])
    elif run.recommendations:
        source_rows = list(run.recommendations or [])

    orders: list[dict] = []
    for row in source_rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol", "")).strip().upper()
        if not _is_stock_symbol(symbol):
            continue
        orders.append(_to_order_row(row))
    return orders
@router.get("/{decision_id}")
async def get_decision(decision_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DecisionRun).where(DecisionRun.id == decision_id))
    run = result.scalars().first()
    if not run:
        raise HTTPException(status_code=404, detail="Decision not found.")
    if run.status == "completed" and run.recommendations:
        cases = await get_similar_cases(db, run.symbols or [], top_k=3)
        run.recommendations = [{**rec, "similar_cases": cases} for rec in (run.recommendations or [])]
    return _serialize_run(run)
