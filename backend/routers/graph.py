"""Experience graph endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import GraphNode
from services.graph import get_graph_stats, get_similar_cases

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])

def _serialize_node(n: GraphNode) -> dict:
    return {
        "node_id": n.node_id,
        "timestamp": n.timestamp.isoformat(),
        "approved": n.approved,
        "outcome_return": n.outcome_return,
        "outcome_sharpe": n.outcome_sharpe,
        "symbols": n.symbols or [],
    }

@router.get("/stats")
async def graph_stats(db: AsyncSession = Depends(get_db)):
    return await get_graph_stats(db)

@router.get("/nodes")
async def list_nodes(
    limit: int = 300,
    offset: int = 0,
    approved_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    q = select(GraphNode).order_by(GraphNode.timestamp.desc()).offset(offset).limit(limit)
    if approved_only:
        q = q.where(GraphNode.approved == True)
    result = await db.execute(q)
    nodes = result.scalars().all()
    from sqlalchemy import func
    total_result = await db.execute(select(func.count(GraphNode.node_id)))
    total = total_result.scalar() or 0
    return {"nodes": [_serialize_node(n) for n in nodes], "total": total}

@router.get("/nodes/{node_id}")
async def get_node(node_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GraphNode).where(GraphNode.node_id == node_id))
    node = result.scalars().first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found.")
    return _serialize_node(node)

@router.post("/search")
async def search_nodes(payload: dict, db: AsyncSession = Depends(get_db)):
    symbols = payload.get("symbols") or []
    top_k = payload.get("top_k", 5)
    cases = await get_similar_cases(db, symbols, top_k=top_k)
    return cases
