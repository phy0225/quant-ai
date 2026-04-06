from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from services import factor_discovery
from services.factor_engine import run_daily

router = APIRouter(prefix="/api/v1/factors", tags=["factors"])


class FactorDiscoveryCreate(BaseModel):
    research_direction: str = Field(..., min_length=4, max_length=500)


@router.get("/daily")
async def get_daily_factor_snapshot(date: str = Query(...)):
    return await run_daily(date)


@router.post("/discover")
async def create_factor_discovery_task(payload: FactorDiscoveryCreate):
    return await factor_discovery.create_task(payload.research_direction.strip())


@router.get("/discover")
async def list_factor_discovery_tasks(limit: int = Query(20, ge=1, le=200)):
    items = factor_discovery.list_tasks(limit=limit)
    return {"items": items, "total": len(items)}


@router.get("/discover/{task_id}")
async def get_factor_discovery_task(task_id: str):
    item = factor_discovery.get_task(task_id)
    if not item:
        raise HTTPException(status_code=404, detail="Factor discovery task not found.")
    return item
