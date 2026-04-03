"""Daily scheduler helpers for factor, NAV, and settlement jobs."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable

from config import settings


JobFunc = Callable[..., Any]


@dataclass
class FallbackJob:
    id: str
    func: JobFunc
    trigger: str
    kwargs: dict[str, Any]


class FallbackScheduler:
    """Tiny scheduler surface compatible with the project test needs."""

    def __init__(self) -> None:
        self._jobs: list[FallbackJob] = []
        self.running = False

    def add_job(self, func: JobFunc, trigger: str, id: str, replace_existing: bool = True, **kwargs: Any) -> None:
        if replace_existing:
            self._jobs = [job for job in self._jobs if job.id != id]
        self._jobs.append(FallbackJob(id=id, func=func, trigger=trigger, kwargs=kwargs))

    def get_jobs(self) -> list[FallbackJob]:
        return list(self._jobs)

    def start(self) -> None:
        self.running = True

    def shutdown(self, wait: bool = False) -> None:
        self.running = False


def _build_backend_scheduler() -> Any:
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore

        return AsyncIOScheduler(timezone="Asia/Shanghai")
    except Exception:
        return FallbackScheduler()


async def run_factor_snapshot_job() -> dict:
    from services.factor_engine import run_daily

    trade_date = datetime.now().date().isoformat()
    return await run_daily(trade_date)


async def run_nav_snapshot_job(holdings: list[dict] | None = None) -> dict:
    from services.nav_calculator import build_nav_snapshot

    return build_nav_snapshot(holdings or [], datetime.now())


async def run_settlement_job() -> dict:
    return {
        "job": "t5_settlement_daily",
        "status": "pending_db_integration",
        "settled_count": 0,
    }


def build_scheduler() -> Any:
    scheduler = _build_backend_scheduler()
    scheduler.add_job(
        run_factor_snapshot_job,
        trigger="cron",
        id="factor_engine_daily",
        replace_existing=True,
        hour=18,
        minute=5,
    )
    scheduler.add_job(
        run_nav_snapshot_job,
        trigger="cron",
        id="portfolio_nav_daily",
        replace_existing=True,
        hour=18,
        minute=10,
    )
    scheduler.add_job(
        run_settlement_job,
        trigger="cron",
        id="t5_settlement_daily",
        replace_existing=True,
        hour=18,
        minute=15,
    )
    return scheduler


def start_scheduler_if_enabled(scheduler: Any) -> bool:
    if not settings.APSCHEDULER_ENABLED:
        return False
    scheduler.start()
    return True
