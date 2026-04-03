"""Backtest endpoints."""
from __future__ import annotations
import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database import get_db
from models import BacktestReport
from schemas import BacktestRunRequest

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])

def _fmt(dt) -> str | None:
    return dt.isoformat() if dt else None

def _serialize(r: BacktestReport) -> dict:
    return {
        "id": r.id,
        "status": r.status,
        "symbols": r.symbols or [],
        "start_date": r.start_date,
        "end_date": r.end_date,
        "initial_capital": r.initial_capital,
        "benchmark": r.benchmark,
        "backtest_mode": getattr(r, "backtest_mode", "signal_based"),
        "commission_rate": r.commission_rate,
        "slippage": r.slippage,
        "nav_curve": r.nav_curve,
        "monthly_returns": r.monthly_returns,
        "total_return": r.total_return,
        "annualized_return": r.annualized_return,
        "sharpe_ratio": r.sharpe_ratio,
        "max_drawdown": r.max_drawdown,
        "win_rate": r.win_rate,
        "avg_holding_days": r.avg_holding_days,
        "total_commission": r.total_commission,
        "total_slippage_cost": r.total_slippage_cost,
        "created_at": _fmt(r.created_at),
        "completed_at": _fmt(r.completed_at),
        "error_message": r.error_message,
    }

async def _run_backtest_task(report_id: str, payload: BacktestRunRequest, db: AsyncSession):
    from services.backtest import run_backtest
    result = await db.execute(select(BacktestReport).where(BacktestReport.id == report_id))
    report = result.scalars().first()
    if not report:
        return
    report.status = "running"
    await db.commit()
    try:
        metrics = run_backtest(
            symbols=payload.symbols,
            start_date=payload.start_date,
            end_date=payload.end_date,
            initial_capital=payload.initial_capital,
            benchmark=payload.benchmark,
            commission_rate=payload.commission_rate,
            slippage=payload.slippage,
            rebalance_frequency=payload.rebalance_frequency,
            backtest_mode=payload.backtest_mode,
        )
        report.status = "completed"
        report.completed_at = datetime.utcnow()
        for k, v in metrics.items():
            if hasattr(report, k):
                setattr(report, k, v)
    except Exception as e:
        report.status = "failed"
        report.error_message = str(e)
        report.completed_at = datetime.utcnow()
    await db.commit()

@router.post("/")
async def run_backtest(payload: BacktestRunRequest, db: AsyncSession = Depends(get_db)):
    if len(payload.symbols) < 2:
        raise HTTPException(status_code=422, detail="At least 2 symbols required.")
    report = BacktestReport(
        symbols=payload.symbols,
        start_date=payload.start_date,
        end_date=payload.end_date,
        initial_capital=payload.initial_capital,
        benchmark=payload.benchmark,
        backtest_mode=payload.backtest_mode,
        commission_rate=payload.commission_rate,
        slippage=payload.slippage,
        rebalance_frequency=payload.rebalance_frequency,
        status="pending",
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    asyncio.create_task(_run_backtest_task(report.id, payload, db))
    return _serialize(report)

@router.get("/")
async def list_backtests(limit: int = 20, db: AsyncSession = Depends(get_db)):
    count_result = await db.execute(select(func.count()).select_from(BacktestReport))
    total = count_result.scalar()
    result = await db.execute(
        select(BacktestReport).order_by(BacktestReport.created_at.desc()).limit(limit)
    )
    items = [_serialize(r) for r in result.scalars().all()]
    return {"total": total, "items": items}

@router.get("/{report_id}")
async def get_backtest(report_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(BacktestReport).where(BacktestReport.id == report_id))
    r = result.scalars().first()
    if not r:
        raise HTTPException(status_code=404, detail="Backtest report not found.")
    return _serialize(r)
