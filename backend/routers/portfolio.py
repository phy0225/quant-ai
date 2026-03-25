"""
持仓管理路由
GET  /api/v1/portfolio/           — 当前持仓列表
POST /api/v1/portfolio/           — 新增/更新单条持仓
PUT  /api/v1/portfolio/{id}       — 修改持仓
DELETE /api/v1/portfolio/{id}     — 删除持仓
POST /api/v1/portfolio/refresh-prices — 刷新所有持仓的实时价格和盈亏
GET  /api/v1/portfolio/summary    — 汇总（总市值、总浮盈、权重分布）
GET  /api/v1/portfolio/snapshots  — 历史快照
"""
from __future__ import annotations
import asyncio
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database import get_db
from models import PortfolioHolding, PortfolioSnapshot

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class HoldingCreate(BaseModel):
    symbol:      str
    symbol_name: Optional[str] = None
    weight:      float = 0.0
    cost_price:  Optional[float] = None
    quantity:    Optional[int] = None
    note:        Optional[str] = None

class HoldingUpdate(BaseModel):
    symbol_name: Optional[str] = None
    weight:      Optional[float] = None
    cost_price:  Optional[float] = None
    quantity:    Optional[int] = None
    note:        Optional[str] = None


def _fmt(h: PortfolioHolding) -> dict:
    return {
        "id":            h.id,
        "symbol":        h.symbol,
        "symbol_name":   h.symbol_name,
        "weight":        h.weight,
        "cost_price":    h.cost_price,
        "quantity":      h.quantity,
        "market_value":  h.market_value,
        "current_price": h.current_price,
        "pnl_pct":       h.pnl_pct,
        "note":          h.note,
        "updated_at":    h.updated_at.isoformat() if h.updated_at else None,
        "created_at":    h.created_at.isoformat() if h.created_at else None,
    }


# ─── 当前持仓列表 ────────────────────────────────────────────────────────────

@router.get("/")
async def list_holdings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PortfolioHolding).order_by(PortfolioHolding.weight.desc())
    )
    holdings = result.scalars().all()
    return {"holdings": [_fmt(h) for h in holdings]}


# ─── 汇总信息 ────────────────────────────────────────────────────────────────

@router.get("/summary")
async def get_summary(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PortfolioHolding))
    holdings = result.scalars().all()

    total_weight   = sum(h.weight for h in holdings)
    total_mv       = sum((h.market_value or 0) for h in holdings)
    # 加权平均浮盈
    weighted_pnl   = sum(
        (h.pnl_pct or 0) * h.weight for h in holdings if h.pnl_pct is not None
    )
    avg_pnl = weighted_pnl / total_weight if total_weight > 0 else 0

    return {
        "total_weight":    round(total_weight, 4),
        "total_mv":        round(total_mv, 2),
        "avg_pnl_pct":     round(avg_pnl, 4),
        "holding_count":   len(holdings),
        "weight_dist":     [
            {"symbol": h.symbol, "symbol_name": h.symbol_name, "weight": h.weight}
            for h in holdings
        ],
    }


# ─── 新增持仓 ────────────────────────────────────────────────────────────────

@router.post("/")
async def create_holding(payload: HoldingCreate, db: AsyncSession = Depends(get_db)):
    # 同一标的只允许一条记录（幂等 upsert）
    result = await db.execute(
        select(PortfolioHolding).where(PortfolioHolding.symbol == payload.symbol.upper())
    )
    existing = result.scalars().first()
    if existing:
        existing.weight      = payload.weight
        existing.symbol_name = payload.symbol_name or existing.symbol_name
        existing.cost_price  = payload.cost_price  or existing.cost_price
        existing.quantity    = payload.quantity    or existing.quantity
        existing.note        = payload.note        or existing.note
        existing.updated_at  = datetime.now()
        await db.commit()
        await db.refresh(existing)
        return _fmt(existing)

    h = PortfolioHolding(
        symbol      = payload.symbol.upper(),
        symbol_name = payload.symbol_name,
        weight      = payload.weight,
        cost_price  = payload.cost_price,
        quantity    = payload.quantity,
        note        = payload.note,
    )
    db.add(h)
    await db.commit()
    await db.refresh(h)
    return _fmt(h)


# ─── 修改持仓 ────────────────────────────────────────────────────────────────

@router.put("/{holding_id}")
async def update_holding(
    holding_id: str, payload: HoldingUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(PortfolioHolding).where(PortfolioHolding.id == holding_id)
    )
    h = result.scalars().first()
    if not h:
        raise HTTPException(404, "持仓记录不存在")

    if payload.weight      is not None: h.weight      = payload.weight
    if payload.symbol_name is not None: h.symbol_name = payload.symbol_name
    if payload.cost_price  is not None: h.cost_price  = payload.cost_price
    if payload.quantity    is not None: h.quantity    = payload.quantity
    if payload.note        is not None: h.note        = payload.note
    h.updated_at = datetime.now()

    await db.commit()
    await db.refresh(h)
    return _fmt(h)


# ─── 删除持仓 ────────────────────────────────────────────────────────────────

@router.delete("/{holding_id}")
async def delete_holding(holding_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PortfolioHolding).where(PortfolioHolding.id == holding_id)
    )
    h = result.scalars().first()
    if not h:
        raise HTTPException(404, "持仓记录不存在")
    await db.delete(h)
    await db.commit()
    return {"ok": True}


# ─── 刷新实时价格 & 盈亏 ─────────────────────────────────────────────────────

@router.post("/refresh-prices")
async def refresh_prices(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PortfolioHolding))
    holdings = result.scalars().all()

    if not holdings:
        return {"refreshed": 0}

    from services.cn_market_data import fetch_cn_snapshot

    async def refresh_one(h: PortfolioHolding):
        try:
            snap = await fetch_cn_snapshot(h.symbol)
            if not snap:
                return
            price = snap.get("current_price")
            if price:
                h.current_price = price
                if h.cost_price and h.cost_price > 0:
                    h.pnl_pct = round((price - h.cost_price) / h.cost_price, 4)
                if h.quantity:
                    h.market_value = round(price * h.quantity, 2)
                h.updated_at = datetime.now()
        except Exception as e:
            print(f"[portfolio] refresh {h.symbol} failed: {e}")

    # 并发刷新所有标的
    await asyncio.gather(*[refresh_one(h) for h in holdings])
    await db.commit()

    return {"refreshed": len(holdings), "updated_at": datetime.now().isoformat()}


# ─── 历史快照 ────────────────────────────────────────────────────────────────

@router.get("/snapshots")
async def list_snapshots(limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PortfolioSnapshot)
        .order_by(PortfolioSnapshot.created_at.desc())
        .limit(limit)
    )
    snaps = result.scalars().all()
    return {"snapshots": [
        {
            "id":          s.id,
            "decision_id": s.decision_id,
            "approval_id": s.approval_id,
            "holdings":    s.holdings,
            "total_mv":    s.total_mv,
            "created_at":  s.created_at.isoformat() if s.created_at else None,
        }
        for s in snaps
    ]}


# ─── 审批通过后自动同步持仓（供 approvals.py 调用）──────────────────────────

async def apply_recommendations(
    db: AsyncSession,
    decision_id: str,
    approval_id: str,
    recommendations: list[dict],
):
    """
    审批通过后调用：
    1. 用建议权重更新 PortfolioHolding 表
    2. 保存一份 PortfolioSnapshot 快照
    """
    if not recommendations:
        return

    for rec in recommendations:
        symbol = rec.get("symbol", "").upper()
        new_weight = rec.get("recommended_weight", 0.0)
        if not symbol:
            continue

        result = await db.execute(
            select(PortfolioHolding).where(PortfolioHolding.symbol == symbol)
        )
        h = result.scalars().first()

        if new_weight <= 0.0001:
            # 权重清零 = 清仓，删除记录
            if h:
                await db.delete(h)
            continue

        if h:
            h.weight     = new_weight
            h.updated_at = datetime.now()
        else:
            h = PortfolioHolding(symbol=symbol, weight=new_weight)
            db.add(h)

    await db.commit()

    # 保存快照
    result = await db.execute(select(PortfolioHolding))
    all_holdings = result.scalars().all()
    snap = PortfolioSnapshot(
        decision_id = decision_id,
        approval_id = approval_id,
        holdings    = {h.symbol: h.weight for h in all_holdings},
        total_mv    = sum((h.market_value or 0) for h in all_holdings),
    )
    db.add(snap)
    await db.commit()
    print(f"[portfolio] applied {len(recommendations)} recs, snapshot saved")
