"""Helpers for tracking FastAPI background tasks."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from fastapi import FastAPI


def _background_tasks(app: FastAPI) -> set[asyncio.Task]:
    tasks = getattr(app.state, "background_tasks", None)
    if tasks is None:
        tasks = set()
        app.state.background_tasks = tasks
    return tasks


def track_background_task(app: FastAPI, coro: Awaitable) -> asyncio.Task:
    task = asyncio.create_task(coro)
    tasks = _background_tasks(app)
    tasks.add(task)
    task.add_done_callback(tasks.discard)
    return task


async def wait_for_background_tasks(app: FastAPI) -> None:
    tasks = list(_background_tasks(app))
    if not tasks:
        return
    await asyncio.gather(*tasks, return_exceptions=True)


async def cancel_background_tasks(app: FastAPI) -> None:
    tasks = list(_background_tasks(app))
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
