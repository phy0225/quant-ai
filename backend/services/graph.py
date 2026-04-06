"""Experience graph service — stores and retrieves historical decision nodes."""
from __future__ import annotations
import math, random
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from models import DecisionRun, GraphNode, ApprovalRecord

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

def serialize_graph_node(n: GraphNode) -> dict:
    metadata = n.metadata_ or {}
    symbols = n.symbols or []
    return {
        "node_id": n.node_id,
        "timestamp": n.timestamp.isoformat(),
        "approved": n.approved,
        "outcome_return": n.outcome_return,
        "outcome_sharpe": n.outcome_sharpe,
        "symbols": symbols,
        "mode": metadata.get("mode"),
        "factor_snapshot": metadata.get("factor_snapshot"),
        "market_regime": metadata.get("market_regime"),
        "node_type": "experience",
        "display_label": ", ".join(symbols[:2]) if symbols else "空案例",
        "entity_key": n.node_id,
    }

def build_graph_edges(nodes: list[GraphNode]) -> list[dict]:
    edges: list[dict] = []
    for i, left in enumerate(nodes):
        left_meta = left.metadata_ or {}
        left_symbols = left.symbols or []
        for right in nodes[i + 1:]:
            right_meta = right.metadata_ or {}
            right_symbols = right.symbols or []
            shared_symbols = sorted(set(left_symbols).intersection(right_symbols))
            same_mode = bool(left_meta.get("mode") and left_meta.get("mode") == right_meta.get("mode"))
            same_regime = bool(
                left_meta.get("market_regime")
                and left_meta.get("market_regime") == right_meta.get("market_regime")
            )

            strength = 0.0
            relation_parts: list[str] = []

            if shared_symbols:
                strength += min(0.75, len(shared_symbols) * 0.35)
                relation_parts.append("shared_symbols")
            if same_mode:
                strength += 0.18
                relation_parts.append("same_mode")
            if same_regime:
                strength += 0.22
                relation_parts.append("same_market_regime")

            if strength < 0.3:
                continue

            edges.append(
                {
                    "edge_id": f"{left.node_id}:{right.node_id}",
                    "source": left.node_id,
                    "target": right.node_id,
                    "relation_type": "+".join(relation_parts),
                    "strength": round(strength, 3),
                    "shared_symbols": shared_symbols,
                    "shared_market_regime": left_meta.get("market_regime") if same_regime else None,
                }
            )

    edges.sort(key=lambda item: item["strength"], reverse=True)
    return edges

async def add_graph_node(db: AsyncSession, approval: ApprovalRecord) -> GraphNode:
    symbols = [r["symbol"] for r in (approval.recommendations or []) if isinstance(r, dict) and r.get("symbol")]
    decision_result = await db.execute(select(DecisionRun).where(DecisionRun.id == approval.decision_run_id))
    decision = decision_result.scalars().first()
    mode = getattr(decision, "mode", "targeted")
    market_regime = None
    factor_snapshot = {
        "source": "decision_recommendations",
        "symbol_count": len(symbols),
        "generated_at": (approval.reviewed_at or datetime.utcnow()).isoformat(),
    }
    embedding = _make_embedding(symbols, None)
    node = GraphNode(
        approval_id=approval.id,
        timestamp=approval.reviewed_at or datetime.utcnow(),
        approved=(approval.status in ("approved", "auto_approved", "modified")),
        outcome_return=round(random.uniform(-0.08, 0.15), 4),
        outcome_sharpe=round(random.uniform(-0.5, 3.0), 2),
        symbols=symbols,
        embedding=embedding,
        metadata_={
            "mode": mode,
            "factor_snapshot": factor_snapshot,
            "market_regime": market_regime,
        },
    )
    db.add(node)
    await db.commit()
    await db.refresh(node)
    return node

async def get_graph_stats(db: AsyncSession) -> dict:
    nodes_result = await db.execute(select(GraphNode))
    nodes = nodes_result.scalars().all()
    n = len(nodes)
    edges = build_graph_edges(nodes)
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
        "edge_count": len(edges),
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

async def get_graph_network(
    db: AsyncSession,
    limit: int = 100,
    approved_only: bool = False,
    offset: int = 0,
) -> dict:
    q = select(GraphNode).order_by(GraphNode.timestamp.desc()).offset(offset).limit(limit)
    if approved_only:
        q = q.where(GraphNode.approved == True)
    result = await db.execute(q)
    nodes = result.scalars().all()
    serialized_nodes = [serialize_graph_node(node) for node in nodes]
    edges = build_graph_edges(nodes)

    symbol_nodes: dict[str, dict] = {}
    regime_nodes: dict[str, dict] = {}
    factor_nodes: dict[str, dict] = {}

    for node in nodes:
        node_payload = serialize_graph_node(node)
        for symbol in node.symbols or []:
            symbol_id = f"symbol:{symbol}"
            if symbol_id not in symbol_nodes:
                symbol_nodes[symbol_id] = {
                    "node_id": symbol_id,
                    "timestamp": node.timestamp.isoformat(),
                    "approved": True,
                    "outcome_return": 0.0,
                    "outcome_sharpe": 0.0,
                    "symbols": [symbol],
                    "mode": None,
                    "factor_snapshot": None,
                    "market_regime": None,
                    "node_type": "symbol",
                    "display_label": symbol,
                    "entity_key": symbol,
                }
            edges.append(
                {
                    "edge_id": f"{node.node_id}:{symbol_id}",
                    "source": node.node_id,
                    "target": symbol_id,
                    "relation_type": "has_symbol",
                    "strength": 0.95,
                    "shared_symbols": [symbol],
                    "shared_market_regime": None,
                }
            )

        regime = node_payload.get("market_regime")
        if regime:
            regime_id = f"regime:{regime}"
            if regime_id not in regime_nodes:
                regime_nodes[regime_id] = {
                    "node_id": regime_id,
                    "timestamp": node.timestamp.isoformat(),
                    "approved": True,
                    "outcome_return": 0.0,
                    "outcome_sharpe": 0.0,
                    "symbols": [],
                    "mode": None,
                    "factor_snapshot": None,
                    "market_regime": regime,
                    "node_type": "market_regime",
                    "display_label": regime,
                    "entity_key": regime,
                }
            edges.append(
                {
                    "edge_id": f"{node.node_id}:{regime_id}",
                    "source": node.node_id,
                    "target": regime_id,
                    "relation_type": "in_market_regime",
                    "strength": 0.88,
                    "shared_symbols": [],
                    "shared_market_regime": regime,
                }
            )

        factor_snapshot = node_payload.get("factor_snapshot")
        if isinstance(factor_snapshot, dict):
            factor_keys = sorted(
                key
                for key in factor_snapshot.keys()
                if key not in {"source", "symbol_count", "generated_at"}
            )
            for factor_key in factor_keys[:8]:
                factor_id = f"factor:{factor_key}"
                if factor_id not in factor_nodes:
                    factor_nodes[factor_id] = {
                        "node_id": factor_id,
                        "timestamp": node.timestamp.isoformat(),
                        "approved": True,
                        "outcome_return": 0.0,
                        "outcome_sharpe": 0.0,
                        "symbols": [],
                        "mode": None,
                        "factor_snapshot": None,
                        "market_regime": None,
                        "node_type": "factor",
                        "display_label": factor_key,
                        "entity_key": factor_key,
                    }
                edges.append(
                    {
                        "edge_id": f"{node.node_id}:{factor_id}",
                        "source": node.node_id,
                        "target": factor_id,
                        "relation_type": "has_factor",
                        "strength": 0.82,
                        "shared_symbols": [],
                        "shared_market_regime": None,
                    }
                )

    all_nodes = serialized_nodes + list(symbol_nodes.values()) + list(regime_nodes.values()) + list(factor_nodes.values())
    return {
        "nodes": all_nodes,
        "edges": edges,
        "total_nodes": len(all_nodes),
        "total_edges": len(edges),
    }
