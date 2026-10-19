"""Async PostgreSQL access (psycopg 3). All queries are parameterized."""
from __future__ import annotations

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .config import settings

pool = AsyncConnectionPool(settings.database_url, min_size=2, max_size=20, open=False,
                           kwargs={"row_factory": dict_row, "autocommit": True}, timeout=10)


async def open_pool() -> None:
    await pool.open(wait=True, timeout=30)


async def close_pool() -> None:
    await pool.close()


async def fetch_all(sql: str, params=None) -> list[dict]:
    async with pool.connection() as c:
        cur = await c.execute(sql, params)
        return await cur.fetchall()


async def fetch_one(sql: str, params=None) -> dict | None:
    async with pool.connection() as c:
        cur = await c.execute(sql, params)
        return await cur.fetchone()


async def execute(sql: str, params=None) -> int:
    async with pool.connection() as c:
        cur = await c.execute(sql, params)
        return cur.rowcount
