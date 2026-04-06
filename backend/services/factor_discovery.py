from __future__ import annotations

from datetime import datetime
from hashlib import md5
from typing import Any
from uuid import uuid4

_TASKS: dict[str, dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _score(seed: str, idx: int) -> float:
    digest = md5(f"{seed}:{idx}".encode("utf-8")).hexdigest()
    return round((int(digest[:8], 16) % 1000) / 1000, 3)


def _build_candidates(research_direction: str) -> list[dict[str, Any]]:
    seed = research_direction.strip().lower()
    candidates = [
        "momentum_20d_accel",
        "quality_cashflow_stability",
        "fundflow_northbound_pressure",
    ]
    rows: list[dict[str, Any]] = []
    for idx, key in enumerate(candidates):
        rows.append(
            {
                "factor_key": key,
                "score": _score(seed, idx),
                "reason": f"derived from research direction segment {idx + 1}",
            }
        )
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows


async def run_discovery(research_direction: str, task_id: str) -> dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task:
        raise KeyError("task not found")
    task["status"] = "running"
    task["started_at"] = _now_iso()

    task["recommended_factors"] = _build_candidates(research_direction)
    task["status"] = "completed"
    task["completed_at"] = _now_iso()
    return task


async def create_task(research_direction: str) -> dict[str, Any]:
    task_id = str(uuid4())
    _TASKS[task_id] = {
        "task_id": task_id,
        "research_direction": research_direction,
        "status": "pending",
        "created_at": _now_iso(),
        "started_at": None,
        "completed_at": None,
        "recommended_factors": [],
    }
    return await run_discovery(research_direction, task_id)


def list_tasks(limit: int = 20) -> list[dict[str, Any]]:
    rows = sorted(_TASKS.values(), key=lambda r: r["created_at"], reverse=True)
    return rows[:limit]


def get_task(task_id: str) -> dict[str, Any] | None:
    return _TASKS.get(task_id)
