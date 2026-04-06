"""Risk management endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from schemas import (
    RiskParamsUpdate, CircuitBreakerResetRequest,
    EmergencyStopRequest, EmergencyDeactivateRequest,
)
import services.risk as risk_svc
from models import AgentWeightConfig
from websocket_manager import manager

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])

@router.get("/status")
async def get_status(db: AsyncSession = Depends(get_db)):
    return await risk_svc.get_risk_status(db)

@router.get("/events")
async def list_events(limit: int = 20, event_type: str | None = None, db: AsyncSession = Depends(get_db)):
    return await risk_svc.list_risk_events(db, limit=limit, event_type=event_type)

@router.get("/params")
async def get_params(db: AsyncSession = Depends(get_db)):
    return await risk_svc.get_risk_params(db)

@router.put("/params")
async def update_params(payload: RiskParamsUpdate, db: AsyncSession = Depends(get_db)):
    return await risk_svc.update_risk_params(db, payload.model_dump(exclude_none=True))

@router.post("/circuit-breaker/reset")
async def reset_circuit_breaker(payload: CircuitBreakerResetRequest, db: AsyncSession = Depends(get_db)):
    try:
        result = await risk_svc.reset_circuit_breaker(db, payload.target_level, payload.authorized_by)
        await manager.broadcast("circuit_breaker_changed", {"level": payload.target_level})
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@router.post("/emergency-stop/activate")
async def activate_emergency(payload: EmergencyStopRequest, db: AsyncSession = Depends(get_db)):
    await risk_svc.activate_emergency_stop(db, payload.reason, payload.activated_by)
    await manager.broadcast("emergency_stop_activated", {"reason": payload.reason})

@router.post("/emergency-stop/deactivate")
async def deactivate_emergency(payload: EmergencyDeactivateRequest, db: AsyncSession = Depends(get_db)):
    try:
        result = await risk_svc.deactivate_emergency_stop(db, payload.password, payload.deactivated_by)
        await manager.broadcast("emergency_stop_deactivated", {})
        return result
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/agent-weights")
async def get_agent_weights(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AgentWeightConfig).order_by(AgentWeightConfig.weight.desc()))
    return {
        "items": [
            {
                "agent_type": row.agent_type,
                "weight": row.weight,
                "accuracy_30d": row.accuracy_30d,
                "accuracy_60d": row.accuracy_60d,
                "is_locked": row.is_locked,
            }
            for row in result.scalars().all()
        ]
    }
