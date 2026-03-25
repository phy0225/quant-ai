"""Approval workflow endpoints."""
from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database import get_db
from routers.portfolio import apply_recommendations
from models import ApprovalRecord, RiskConfig
from schemas import ApprovalActionRequest, ModifyWeightsRequest, BatchActionRequest
from services.graph import add_graph_node
from websocket_manager import manager

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])

def _fmt(dt) -> str | None:
    return dt.isoformat() if dt else None

def _serialize(a: ApprovalRecord) -> dict:
    return {
        "id": a.id,
        "decision_run_id": a.decision_run_id,
        "status": a.status,
        "reviewed_by": a.reviewed_by,
        "reviewed_at": _fmt(a.reviewed_at),
        "comment": a.comment,
        "auto_rule_id": a.auto_rule_id,
        "recommendations": a.recommendations or [],
        "created_at": _fmt(a.created_at),
    }

@router.get("/")
async def list_approvals(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    q = select(ApprovalRecord).order_by(ApprovalRecord.created_at.desc())
    if status:
        q = q.where(ApprovalRecord.status == status)
    total_q = select(func.count(ApprovalRecord.id))
    if status:
        total_q = total_q.where(ApprovalRecord.status == status)
    total = (await db.execute(total_q)).scalar() or 0
    offset = (page - 1) * page_size
    result = await db.execute(q.offset(offset).limit(page_size))
    items = result.scalars().all()
    return {"items": [_serialize(a) for a in items], "total": total, "page": page, "page_size": page_size}

@router.post("/batch-action")
async def batch_action(payload: BatchActionRequest, db: AsyncSession = Depends(get_db)):
    if payload.action != "rejected":
        raise HTTPException(status_code=422, detail="批量操作仅支持 rejected")
    if not payload.approval_ids:
        raise HTTPException(status_code=422, detail="approval_ids 不能为空")
    if len(payload.approval_ids) > 50:
        raise HTTPException(status_code=422, detail="批量操作最多 50 条")

    # Check emergency stop
    cfg_result = await db.execute(select(RiskConfig))
    cfg = cfg_result.scalars().first()
    if cfg and cfg.emergency_stop_active:
        raise HTTPException(status_code=503, detail="System halted — cannot process approvals.")

    succeeded: list[str] = []
    failed: list[dict] = []

    for approval_id in payload.approval_ids:
        result = await db.execute(select(ApprovalRecord).where(ApprovalRecord.id == approval_id))
        a = result.scalars().first()
        if not a:
            failed.append({"id": approval_id, "reason": "Approval not found."})
            continue
        if a.status != "pending":
            failed.append({"id": approval_id, "reason": "Approval already processed."})
            continue

        a.status = "rejected"
        a.reviewed_by = payload.reviewed_by
        a.reviewed_at = datetime.now()
        a.comment = payload.comment
        await db.commit()

        try:
            await add_graph_node(db, a)
        except Exception as e:
            print(f"[batch_action] graph node failed for {approval_id}: {e}")

        succeeded.append(approval_id)

    return {
        "succeeded": succeeded,
        "failed": failed,
        "total": len(payload.approval_ids),
        "success_count": len(succeeded),
        "fail_count": len(failed),
    }


@router.get("/{approval_id}")
async def get_approval(approval_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ApprovalRecord).where(ApprovalRecord.id == approval_id))
    a = result.scalars().first()
    if not a:
        raise HTTPException(status_code=404, detail="Approval not found.")
    return _serialize(a)

@router.post("/{approval_id}/action")
async def process_action(approval_id: str, payload: ApprovalActionRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ApprovalRecord).where(ApprovalRecord.id == approval_id))
    a = result.scalars().first()
    if not a:
        raise HTTPException(status_code=404, detail="Approval not found.")
    if a.status != "pending":
        raise HTTPException(status_code=409, detail="Approval already processed.")

    # Check emergency stop / circuit breaker
    cfg_result = await db.execute(select(RiskConfig))
    cfg = cfg_result.scalars().first()
    if cfg and (cfg.emergency_stop_active or cfg.circuit_breaker_level >= 2):
        raise HTTPException(status_code=503, detail="System halted — cannot process approvals.")

    a.status = payload.action
    a.reviewed_by = payload.reviewed_by
    a.reviewed_at = datetime.now()
    a.comment = payload.comment
    await db.commit()

    # 审批通过时同步更新持仓
    if payload.action in ("approved", "auto_approved"):
        try:
            recs = list(a.recommendations or [])
            await apply_recommendations(db, a.decision_run_id or "", a.id, recs)
        except Exception as e:
            print(f"[approvals] portfolio sync failed: {e}")

    # Add to experience graph for all processed decisions
    await add_graph_node(db, a)

    await manager.broadcast("approval_updated", {"approval_id": approval_id, "status": payload.action})
    return _serialize(a)

@router.put("/{approval_id}/modify")
async def modify_weights(approval_id: str, payload: ModifyWeightsRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ApprovalRecord).where(ApprovalRecord.id == approval_id))
    a = result.scalars().first()
    if not a:
        raise HTTPException(status_code=404, detail="Approval not found.")
    if a.status != "pending":
        raise HTTPException(status_code=409, detail="Approval already processed.")

    # 只校验单标的上限，不校验合计（modified_weights 只含本次审批的标的，非全部持仓）
    cfg_result = await db.execute(select(RiskConfig))
    cfg = cfg_result.scalars().first()
    max_pos = cfg.max_position_weight if cfg else 0.20
    for sym, wt in payload.modified_weights.items():
        if wt < 0:
            raise HTTPException(status_code=422, detail=f"{sym} 权重不能为负数")
        if wt > max_pos:
            raise HTTPException(status_code=422, detail=f"{sym} 权重 {wt:.1%} 超过上限 {max_pos:.1%}")

    # Apply modified weights to recommendations
    updated_recs = []
    for rec in (a.recommendations or []):
        sym = rec["symbol"]
        new_wt = payload.modified_weights.get(sym, rec["recommended_weight"])
        updated_recs.append({
            **rec,
            "recommended_weight": round(new_wt, 4),
            "weight_delta": round(new_wt - rec["current_weight"], 4),
        })
    a.recommendations = updated_recs
    a.status = "modified"
    a.reviewed_by = payload.reviewed_by
    a.reviewed_at = datetime.now()
    a.comment = payload.comment
    await db.commit()

    # 修改权重后同样要更新持仓表
    try:
        await apply_recommendations(db, a.decision_run_id or "", a.id, list(a.recommendations or []))
    except Exception as e:
        print(f"[approvals] portfolio sync after modify failed: {e}")

    await add_graph_node(db, a)
    await manager.broadcast("approval_updated", {"approval_id": approval_id, "status": "modified"})
    return _serialize(a)