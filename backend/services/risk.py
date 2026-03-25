"""Risk management service — circuit breaker, emergency stop, risk events."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models import RiskConfig, RiskEvent

LEVEL_NAMES = {0: "NORMAL", 1: "WARNING", 2: "SUSPENDED", 3: "EMERGENCY"}

async def get_risk_config(db: AsyncSession) -> RiskConfig:
    result = await db.execute(select(RiskConfig))
    cfg = result.scalars().first()
    if not cfg:
        cfg = RiskConfig(id=1)
        db.add(cfg)
        await db.commit()
        await db.refresh(cfg)
    return cfg

async def get_risk_status(db: AsyncSession) -> dict:
    cfg = await get_risk_config(db)
    result = await db.execute(
        select(RiskEvent).order_by(RiskEvent.created_at.desc()).limit(10)
    )
    events = result.scalars().all()
    level = cfg.circuit_breaker_level
    return {
        "circuit_breaker": {
            "level": level,
            "level_name": LEVEL_NAMES.get(level, "UNKNOWN"),
            "triggered_at": cfg.circuit_breaker_triggered_at.isoformat() if cfg.circuit_breaker_triggered_at else None,
            "trigger_value": cfg.circuit_breaker_trigger_value,
            "can_execute": not cfg.emergency_stop_active and level < 2,
        },
        "emergency_stop_active": cfg.emergency_stop_active,
        "recent_risk_events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "severity": e.severity,
                "description": e.description,
                "triggered_value": e.triggered_value,
                "threshold_value": e.threshold_value,
                "created_at": e.created_at.isoformat(),
                "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
            }
            for e in events
        ],
    }

async def get_risk_params(db: AsyncSession) -> dict:
    cfg = await get_risk_config(db)
    return {
        "max_position_weight": cfg.max_position_weight,
        "daily_loss_warning_threshold": cfg.daily_loss_warning_threshold,
        "daily_loss_suspend_threshold": cfg.daily_loss_suspend_threshold,
        "max_drawdown_emergency": cfg.max_drawdown_emergency,
    }

async def update_risk_params(db: AsyncSession, params: dict) -> dict:
    cfg = await get_risk_config(db)
    for key, val in params.items():
        if val is not None and hasattr(cfg, key):
            setattr(cfg, key, val)
    await db.commit()
    await db.refresh(cfg)
    return {
        "max_position_weight": cfg.max_position_weight,
        "daily_loss_warning_threshold": cfg.daily_loss_warning_threshold,
        "daily_loss_suspend_threshold": cfg.daily_loss_suspend_threshold,
        "max_drawdown_emergency": cfg.max_drawdown_emergency,
    }

async def reset_circuit_breaker(db: AsyncSession, target_level: int, authorized_by: str) -> dict:
    cfg = await get_risk_config(db)
    if target_level >= cfg.circuit_breaker_level:
        raise ValueError("Target level must be lower than current level.")
    old_level = cfg.circuit_breaker_level
    cfg.circuit_breaker_level = target_level
    if target_level == 0:
        cfg.circuit_breaker_triggered_at = None
        cfg.circuit_breaker_trigger_value = None
        cfg.emergency_stop_active = False

    # Log event
    event = RiskEvent(
        event_type="circuit_breaker_reset",
        severity="warning",
        description=f"Circuit breaker reset from L{old_level} to L{target_level} by {authorized_by}",
        created_at=datetime.utcnow(),
    )
    db.add(event)
    await db.commit()
    await db.refresh(cfg)
    return {
        "level": cfg.circuit_breaker_level,
        "level_name": LEVEL_NAMES.get(cfg.circuit_breaker_level, "UNKNOWN"),
        "triggered_at": cfg.circuit_breaker_triggered_at.isoformat() if cfg.circuit_breaker_triggered_at else None,
        "trigger_value": cfg.circuit_breaker_trigger_value,
        "can_execute": cfg.circuit_breaker_level < 2 and not cfg.emergency_stop_active,
    }

async def activate_emergency_stop(db: AsyncSession, reason: str, activated_by: str):
    cfg = await get_risk_config(db)
    cfg.emergency_stop_active = True
    cfg.emergency_stop_activated_by = activated_by
    cfg.emergency_stop_reason = reason
    cfg.circuit_breaker_level = 3
    cfg.circuit_breaker_triggered_at = datetime.utcnow()
    event = RiskEvent(
        event_type="emergency_stop",
        severity="emergency",
        description=f"Emergency stop activated by {activated_by}: {reason}",
        created_at=datetime.utcnow(),
    )
    db.add(event)
    await db.commit()

async def deactivate_emergency_stop(db: AsyncSession, password: str, deactivated_by: str) -> dict:
    # In production, verify password against hashed secret
    if password != "admin123" and password != "":
        raise ValueError("Invalid password.")
    cfg = await get_risk_config(db)
    cfg.emergency_stop_active = False
    cfg.circuit_breaker_level = 0
    cfg.circuit_breaker_triggered_at = None
    cfg.emergency_stop_activated_by = None
    event = RiskEvent(
        event_type="emergency_stop_deactivated",
        severity="warning",
        description=f"Emergency stop deactivated by {deactivated_by}",
        created_at=datetime.utcnow(),
    )
    db.add(event)
    await db.commit()
    return {"success": True}

async def list_risk_events(db: AsyncSession, limit: int = 20, event_type: str | None = None) -> list:
    q = select(RiskEvent).order_by(RiskEvent.created_at.desc()).limit(limit)
    if event_type:
        q = q.where(RiskEvent.event_type == event_type)
    result = await db.execute(q)
    events = result.scalars().all()
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "severity": e.severity,
            "description": e.description,
            "triggered_value": e.triggered_value,
            "threshold_value": e.threshold_value,
            "created_at": e.created_at.isoformat(),
            "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
        }
        for e in events
    ]
