"""Auto-approval rules endpoints."""
from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import AutoApprovalRule
from schemas import AutoApprovalRuleCreate

router = APIRouter(prefix="/api/v1/rules", tags=["rules"])

def _fmt(dt) -> str | None:
    return dt.isoformat() if dt else None

def _serialize(r: AutoApprovalRule) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "description": r.description,
        "is_active": r.is_active,
        "priority": r.priority,
        "logic_operator": r.logic_operator,
        "conditions": r.conditions or [],
        "action": r.action,
        "trigger_count": r.trigger_count,
        "last_triggered_at": _fmt(r.last_triggered_at),
        "created_at": _fmt(r.created_at),
        "updated_at": _fmt(r.updated_at),
    }

@router.get("/")
async def list_rules(active_only: bool = False, db: AsyncSession = Depends(get_db)):
    q = select(AutoApprovalRule).order_by(AutoApprovalRule.priority.desc())
    if active_only:
        q = q.where(AutoApprovalRule.is_active == True)
    result = await db.execute(q)
    return [_serialize(r) for r in result.scalars().all()]

@router.post("/")
async def create_rule(payload: AutoApprovalRuleCreate, db: AsyncSession = Depends(get_db)):
    rule = AutoApprovalRule(
        name=payload.name,
        description=payload.description,
        is_active=payload.is_active,
        priority=payload.priority,
        logic_operator=payload.logic_operator,
        conditions=[c.model_dump() for c in payload.conditions],
        action=payload.action,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return _serialize(rule)

@router.put("/{rule_id}")
async def update_rule(rule_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AutoApprovalRule).where(AutoApprovalRule.id == rule_id))
    rule = result.scalars().first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found.")
    for k, v in payload.items():
        if hasattr(rule, k) and k not in ("id", "created_at", "trigger_count"):
            setattr(rule, k, v)
    rule.updated_at = datetime.utcnow()
    await db.commit()
    return _serialize(rule)

@router.delete("/{rule_id}", status_code=204)
async def delete_rule(rule_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AutoApprovalRule).where(AutoApprovalRule.id == rule_id))
    rule = result.scalars().first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found.")
    await db.delete(rule)
    await db.commit()

@router.post("/{rule_id}/toggle")
async def toggle_rule(rule_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AutoApprovalRule).where(AutoApprovalRule.id == rule_id))
    rule = result.scalars().first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found.")
    rule.is_active = not rule.is_active
    rule.updated_at = datetime.utcnow()
    await db.commit()
    return _serialize(rule)
