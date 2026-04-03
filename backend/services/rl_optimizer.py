"""
RL Agent 权重优化服务
- load_agent_weights: pipeline 调用，读取当前生效权重
- update_agent_weights: 更新权重（统计或 RL）
- get_rl_status: RL 训练状态查询（供前端展示）
"""
import logging
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {
    "technical": 0.25,
    "fundamental": 0.25,
    "news": 0.25,
    "sentiment": 0.25,
}

WEIGHT_MIN = 0.05
WEIGHT_MAX = 0.45
MIN_SETTLED_FOR_RL = 60


async def load_agent_weights(db: AsyncSession) -> Dict[str, float]:
    """从 DB 读取当前生效权重，不存在则返回默认值"""
    from models import AgentWeightConfig

    try:
        result = await db.execute(select(AgentWeightConfig))
        configs = result.scalars().all()
        if not configs:
            return DEFAULT_WEIGHTS.copy()
        weights = {c.agent_type: c.weight for c in configs}
        # 确保四个 agent 都有值
        for k, v in DEFAULT_WEIGHTS.items():
            weights.setdefault(k, v)
        return weights
    except Exception as e:
        logger.warning(f"读取 AgentWeightConfig 失败，使用默认权重: {e}")
        return DEFAULT_WEIGHTS.copy()


async def update_agent_weights(
    db: AsyncSession,
    new_weights: Dict[str, float],
    source: str = "accuracy_based",
    model_version: Optional[str] = None,
) -> bool:
    """更新权重，跳过锁定的 agent"""
    from models import AgentWeightConfig

    # 先归一化，确保总和为 1.0
    total = sum(new_weights.values())
    if total <= 0:
        return False
    normalized = {k: v / total for k, v in new_weights.items()}

    # 钳制范围
    for k in normalized:
        normalized[k] = max(WEIGHT_MIN, min(WEIGHT_MAX, normalized[k]))

    try:
        result = await db.execute(select(AgentWeightConfig))
        configs = {c.agent_type: c for c in result.scalars().all()}

        for agent_type, weight in normalized.items():
            if agent_type in configs:
                cfg = configs[agent_type]
                if cfg.locked:
                    logger.info(f"Agent {agent_type} 已锁定，跳过权重更新")
                    continue
                cfg.weight = weight
                cfg.weight_source = source
                cfg.last_updated_at = datetime.now()
                if model_version:
                    cfg.rl_model_version = model_version
            else:
                # 初始化记录
                new_cfg = AgentWeightConfig(
                    agent_type=agent_type,
                    weight=weight,
                    weight_source=source,
                    rl_model_version=model_version,
                )
                db.add(new_cfg)

        await db.commit()
        logger.info(f"权重已更新 (source={source}): {normalized}")
        return True
    except Exception as e:
        logger.error(f"更新权重失败: {e}")
        await db.rollback()
        return False


async def get_rl_status(db: AsyncSession) -> dict:
    """获取 RL 训练状态（供前端展示）"""
    from models import GraphNode, AgentWeightConfig
    from sqlalchemy import func as sa_func

    # 已结算节点数
    settled_result = await db.execute(
        select(sa_func.count(GraphNode.node_id)).where(GraphNode.outcome_settled == True)  # noqa: E712
    )
    settled_count = settled_result.scalar() or 0

    # 当前权重配置
    weight_result = await db.execute(select(AgentWeightConfig))
    configs = weight_result.scalars().all()

    last_trained = None
    model_version = None
    for cfg in configs:
        if cfg.rl_model_version:
            model_version = cfg.rl_model_version
        if cfg.last_updated_at and cfg.weight_source == "rl_optimized":
            if last_trained is None or cfg.last_updated_at > last_trained:
                last_trained = cfg.last_updated_at

    return {
        "settled_count": settled_count,
        "min_settled_for_rl": MIN_SETTLED_FOR_RL,
        "progress_pct": min(100, int(settled_count / MIN_SETTLED_FOR_RL * 100)),
        "last_trained_at": last_trained.isoformat() if last_trained else None,
        "model_version": model_version,
        "rl_ready": settled_count >= MIN_SETTLED_FOR_RL,
        "weights": [
            {
                "agent_type": c.agent_type,
                "weight": c.weight,
                "weight_source": c.weight_source,
                "locked": c.locked,
            }
            for c in configs
        ],
    }
