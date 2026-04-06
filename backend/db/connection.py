from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncmy

from config import settings

_pool: asyncmy.Pool | None = None


async def create_pool() -> asyncmy.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncmy.create_pool(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            db=settings.DB_NAME,
            autocommit=False,
            minsize=1,
            maxsize=10,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        await _pool.wait_closed()
        _pool = None


@asynccontextmanager
async def get_db_conn() -> AsyncIterator[asyncmy.Connection]:
    pool = await create_pool()
    async with pool.acquire() as conn:
        yield conn
