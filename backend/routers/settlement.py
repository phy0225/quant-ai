"""Settlement endpoints."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from services import settlement as settlement_svc

router = APIRouter(prefix="/api/v1/settlement", tags=["settlement"])


class SettlementRunRequest(BaseModel):
    settle_date: str | None = None


@router.post("/run")
async def run_settlement(payload: SettlementRunRequest, db: AsyncSession = Depends(get_db)):
    settle_date = payload.settle_date or datetime.utcnow().strftime("%Y-%m-%d")
    return await settlement_svc.run(db, settle_date)


@router.get("/pending")
async def list_pending(settle_date: str, db: AsyncSession = Depends(get_db)):
    items = await settlement_svc.list_pending_settlement(db, settle_date)
    return {"total": len(items)}

