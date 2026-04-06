"""Experience graph endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import GraphNode
from services.graph import get_graph_network, get_graph_stats, get_similar_cases, serialize_graph_node

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])

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
    serialized = [serialize_graph_node(n) for n in nodes]
    return {"nodes": serialized, "items": serialized, "total": total}

@router.get("/network")
async def graph_network(
    limit: int = 100,
    offset: int = 0,
    approved_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    return await get_graph_network(db=db, limit=limit, approved_only=approved_only, offset=offset)

@router.get("/nodes/{node_id}")
async def get_node(node_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GraphNode).where(GraphNode.node_id == node_id))
    node = result.scalars().first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found.")
    return serialize_graph_node(node)

@router.post("/search")
async def search_nodes(payload: dict, db: AsyncSession = Depends(get_db)):
    symbols = payload.get("symbols") or []
    top_k = payload.get("top_k", 5)
    cases = await get_similar_cases(db, symbols, top_k=top_k)
    return cases
