from __future__ import annotations

from datetime import datetime
from hashlib import md5
from typing import Any
from uuid import uuid4

_VERSIONS: dict[str, dict[str, Any]] = {
    "v1": {
        "version_id": "v1",
        "parent_version_id": None,
        "name": "Baseline v1",
        "description": "Initial production baseline.",
        "created_at": datetime.utcnow().isoformat(),
    }
}
_EXPERIMENTS: dict[str, dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _metric(seed: str, offset: int) -> float:
    digest = md5(f"{seed}:{offset}".encode("utf-8")).hexdigest()
    return round(0.02 + (int(digest[:8], 16) % 700) / 10000, 4)


async def run_evolution(base_version_id: str, experiment_id: str) -> dict[str, Any]:
    exp = _EXPERIMENTS.get(experiment_id)
    if not exp:
        raise KeyError("experiment not found")
    exp["status"] = "running"
    exp["started_at"] = _now_iso()

    hypothesis = exp["hypothesis"]
    seed = f"{base_version_id}:{hypothesis}".lower()
    new_version_id = f"v{len(_VERSIONS) + 1}"
    _VERSIONS[new_version_id] = {
        "version_id": new_version_id,
        "parent_version_id": base_version_id,
        "name": f"Experiment {new_version_id}",
        "description": hypothesis,
        "created_at": _now_iso(),
    }

    exp["new_version_id"] = new_version_id
    exp["expected_improvement"] = {
        "annualized_return_lift": _metric(seed, 1),
        "drawdown_reduction": _metric(seed, 2),
        "sharpe_lift": _metric(seed, 3),
    }
    exp["status"] = "completed"
    exp["completed_at"] = _now_iso()
    return exp


async def create_experiment(base_version_id: str, hypothesis: str) -> dict[str, Any]:
    if base_version_id not in _VERSIONS:
        raise ValueError("base version not found")

    experiment_id = str(uuid4())
    _EXPERIMENTS[experiment_id] = {
        "experiment_id": experiment_id,
        "base_version_id": base_version_id,
        "hypothesis": hypothesis,
        "status": "pending",
        "new_version_id": None,
        "expected_improvement": None,
        "created_at": _now_iso(),
        "started_at": None,
        "completed_at": None,
    }
    return await run_evolution(base_version_id, experiment_id)


def list_versions() -> list[dict[str, Any]]:
    return sorted(_VERSIONS.values(), key=lambda r: r["created_at"], reverse=True)


def list_experiments(limit: int = 20) -> list[dict[str, Any]]:
    rows = sorted(_EXPERIMENTS.values(), key=lambda r: r["created_at"], reverse=True)
    return rows[:limit]


def get_experiment(experiment_id: str) -> dict[str, Any] | None:
    return _EXPERIMENTS.get(experiment_id)
