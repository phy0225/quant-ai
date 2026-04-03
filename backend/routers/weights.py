"""
Agent 权重管理路由 (v2.0)
GET  /api/v1/weights         — 返回当前权重配置 + RL 状态
PUT  /api/v1/weights/{agent_type}/lock  — 锁定/解锁某 Agent 权重
PUT  /api/v1/weights/{agent_type}       — 手动设置某 Agent 权重
POST /api/v1/weights/settle             — 手动触发结算（调试用）
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import AgentWeightConfig
from services.rl_optimizer import load_agent_weights, update_agent_weights, get_rl_status, DEFAULT_WEIGHTS, WEIGHT_MIN, WEIGHT_MAX

router = APIRouter(prefix="/api/v1/weights", tags=["weights"])

VALID_AGENT_TYPES = {"technical", "fundamental", "news", "sentiment"}


class LockRequest(BaseModel):
    locked: bool


class WeightUpdateRequest(BaseModel):
    weight: float
    comment: Optional[str] = None


def _fmt(cfg: AgentWeightConfig) -> dict:
    return {
        "agent_type": cfg.agent_type,
        "weight": cfg.weight,
        "weight_source": cfg.weight_source,
        "locked": cfg.locked,
        "rl_model_version": cfg.rl_model_version,
        "last_updated_at": cfg.last_updated_at.isoformat() if cfg.last_updated_at else None,
    }


@router.get("/")
async def get_weights(db: AsyncSession = Depends(get_db)):
    """返回当前权重配置 + RL 训练状态"""
    rl_status = await get_rl_status(db)
    current_weights = await load_agent_weights(db)

    # 如果 DB 中没有配置记录，返回默认值
    result = await db.execute(select(AgentWeightConfig))
    configs = result.scalars().all()
    if not configs:
        weights_detail = [
            {
                "agent_type": k,
                "weight": v,
                "weight_source": "default",
                "locked": False,
                "rl_model_version": None,
                "last_updated_at": None,
            }
            for k, v in DEFAULT_WEIGHTS.items()
        ]
    else:
        weights_detail = [_fmt(c) for c in configs]

    return {
        "weights": weights_detail,
        "current_weights": current_weights,
        "rl_status": rl_status,
        "generated_at": datetime.now().isoformat(),
    }


@router.put("/{agent_type}/lock")
async def lock_agent_weight(
    agent_type: str, payload: LockRequest, db: AsyncSession = Depends(get_db)
):
    """锁定或解锁某 Agent 的权重（锁定后不受 RL 自动更新影响）"""
    agent_type = agent_type.lower()
    if agent_type not in VALID_AGENT_TYPES:
        raise HTTPException(status_code=422, detail=f"无效的 agent_type，允许值: {VALID_AGENT_TYPES}")

    result = await db.execute(
        select(AgentWeightConfig).where(AgentWeightConfig.agent_type == agent_type)
    )
    cfg = result.scalars().first()
    if not cfg:
        # 初始化记录
        cfg = AgentWeightConfig(
            agent_type=agent_type,
            weight=DEFAULT_WEIGHTS.get(agent_type, 0.25),
            weight_source="default",
            locked=payload.locked,
        )
        db.add(cfg)
    else:
        cfg.locked = payload.locked
        cfg.last_updated_at = datetime.now()

    await db.commit()
    await db.refresh(cfg)
    return _fmt(cfg)


@router.put("/{agent_type}")
async def set_agent_weight(
    agent_type: str, payload: WeightUpdateRequest, db: AsyncSession = Depends(get_db)
):
    """手动设置某 Agent 的权重"""
    agent_type = agent_type.lower()
    if agent_type not in VALID_AGENT_TYPES:
        raise HTTPException(status_code=422, detail=f"无效的 agent_type，允许值: {VALID_AGENT_TYPES}")

    weight = float(payload.weight)
    if weight < WEIGHT_MIN or weight > WEIGHT_MAX:
        raise HTTPException(
            status_code=422,
            detail=f"权重 {weight:.3f} 超出允许范围 [{WEIGHT_MIN}, {WEIGHT_MAX}]"
        )

    result = await db.execute(
        select(AgentWeightConfig).where(AgentWeightConfig.agent_type == agent_type)
    )
    cfg = result.scalars().first()
    if not cfg:
        cfg = AgentWeightConfig(
            agent_type=agent_type,
            weight=weight,
            weight_source="manual",
            locked=False,
        )
        db.add(cfg)
    else:
        if cfg.locked:
            raise HTTPException(status_code=409, detail=f"Agent {agent_type} 已锁定，请先解锁后再修改")
        cfg.weight = weight
        cfg.weight_source = "manual"
        cfg.last_updated_at = datetime.now()

    await db.commit()
    await db.refresh(cfg)
    return _fmt(cfg)


@router.post("/settle")
async def trigger_settlement(db: AsyncSession = Depends(get_db)):
    """手动触发 T+5 结算（调试/测试用）"""
    from services.settlement import settle_pending_nodes
    try:
        count = await settle_pending_nodes(db)
        return {"settled_count": count, "triggered_at": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"结算失败: {str(e)}")
