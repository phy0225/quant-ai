"""Experience graph service — stores and retrieves historical decision nodes."""
from __future__ import annotations
import math, random
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from models import GraphNode, ApprovalRecord

def _cosine_similarity(a: list, b: list) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x ** 2 for x in a))
    nb = math.sqrt(sum(y ** 2 for y in b))
    return dot / (na * nb) if na * nb > 0 else 0.0

def _make_embedding(symbols: list, direction: str | None) -> list:
    """Generate a simple deterministic embedding for demo purposes."""
    random.seed(hash(tuple(sorted(symbols))) + hash(direction or "hold"))
    return [round(random.gauss(0, 1), 4) for _ in range(32)]

async def add_graph_node(db: AsyncSession, approval: ApprovalRecord) -> GraphNode:
    symbols = [r["symbol"] for r in (approval.recommendations or [])]
    embedding = _make_embedding(symbols, None)
    node = GraphNode(
        approval_id=approval.id,
        timestamp=approval.reviewed_at or datetime.utcnow(),
        approved=(approval.status in ("approved", "auto_approved", "modified")),
        outcome_return=round(random.uniform(-0.08, 0.15), 4),
        outcome_sharpe=round(random.uniform(-0.5, 3.0), 2),
        symbols=symbols,
        embedding=embedding,
    )
    db.add(node)
    await db.commit()
    await db.refresh(node)
    return node

async def get_graph_stats(db: AsyncSession) -> dict:
    nodes_result = await db.execute(select(GraphNode))
    nodes = nodes_result.scalars().all()
    n = len(nodes)
    if n == 0:
        return {
            "node_count": 0, "edge_count": 0, "avg_accuracy": 0.0,
            "approval_rate": 0.0, "similarity_trend": [],
            "outcome_distribution": {"positive": 0, "negative": 0},
            "top_symbols": [], "generated_at": datetime.utcnow().isoformat(),
        }
    approved = [nd for nd in nodes if nd.approved]
    positive = [nd for nd in approved if nd.outcome_return > 0]
    negative = [nd for nd in approved if nd.outcome_return <= 0]
    avg_acc = len(positive) / len(approved) if approved else 0.0

    # Simulate similarity trend (monthly averages)
    trend = []
    months: dict = {}
    for nd in nodes:
        key = nd.timestamp.strftime("%Y-%m")
        months.setdefault(key, []).append(random.uniform(0.6, 0.95))
    for month, vals in sorted(months.items())[-6:]:
        trend.append({"timestamp": f"{month}-01", "avg_similarity": round(sum(vals)/len(vals), 3)})

    # Top symbols
    sym_count: dict = {}
    for nd in nodes:
        for s in nd.symbols:
            sym_count[s] = sym_count.get(s, 0) + 1
    top_syms = sorted(sym_count.items(), key=lambda x: -x[1])[:5]

    return {
        "node_count": n,
        "edge_count": max(0, n - 1),
        "avg_accuracy": round(avg_acc, 3),
        "approval_rate": round(len(approved) / n, 3) if n else 0.0,
        "similarity_trend": trend,
        "outcome_distribution": {"positive": len(positive), "negative": len(negative)},
        "top_symbols": [{"symbol": s, "count": c} for s, c in top_syms],
        "generated_at": datetime.utcnow().isoformat(),
    }

async def get_similar_cases(db: AsyncSession, symbols: list, top_k: int = 3) -> list:
    result = await db.execute(select(GraphNode))
    nodes = result.scalars().all()
    if not nodes:
        return []
    query_emb = _make_embedding(symbols, None)
    scored = []
    for nd in nodes:
        emb = nd.embedding or []
        sim = _cosine_similarity(query_emb, emb) if emb else random.uniform(0.5, 0.9)
        scored.append((sim, nd))
    scored.sort(key=lambda x: -x[0])
    return [
        {
            "node_id": nd.node_id,
            "similarity_score": round(sim, 3),
            "outcome_return": nd.outcome_return,
            "outcome_sharpe": nd.outcome_sharpe,
            "approved": nd.approved,
            "timestamp": nd.timestamp.isoformat(),
        }
        for sim, nd in scored[:top_k]
    ]
