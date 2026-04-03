from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from services import strategy_evolution

router = APIRouter(prefix="/api/v1/strategy", tags=["strategy"])


class StrategyExperimentCreate(BaseModel):
    base_version_id: str = Field(..., min_length=1, max_length=100)
    hypothesis: str = Field(..., min_length=4, max_length=1000)


@router.get("/versions")
async def list_strategy_versions():
    rows = strategy_evolution.list_versions()
    return {"items": rows, "total": len(rows)}


@router.get("/experiments")
async def list_strategy_experiments(limit: int = Query(20, ge=1, le=200)):
    rows = strategy_evolution.list_experiments(limit=limit)
    return {"items": rows, "total": len(rows)}


@router.post("/experiment")
async def create_strategy_experiment(payload: StrategyExperimentCreate):
    try:
        return await strategy_evolution.create_experiment(
            base_version_id=payload.base_version_id.strip(),
            hypothesis=payload.hypothesis.strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/experiment/{experiment_id}")
async def get_strategy_experiment(experiment_id: str):
    row = strategy_evolution.get_experiment(experiment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Strategy experiment not found.")
    return row
