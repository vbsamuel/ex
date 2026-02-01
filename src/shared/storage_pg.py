import asyncio
import asyncpg
from typing import Any, Iterable, Optional

from src.shared.config import POSTGRES_DSN


class PgStore:
    def __init__(self, dsn: str = POSTGRES_DSN) -> None:
        self._dsn = dsn
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(dsn=self._dsn, min_size=1, max_size=5)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def fetch(self, query: str, *args: Any) -> Iterable[asyncpg.Record]:
        assert self._pool is not None
        return await self._pool.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> Optional[asyncpg.Record]:
        assert self._pool is not None
        return await self._pool.fetchrow(query, *args)

    async def execute(self, query: str, *args: Any) -> str:
        assert self._pool is not None
        return await self._pool.execute(query, *args)

    async def executemany(self, query: str, args_list: Iterable[Iterable[Any]]) -> None:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await conn.executemany(query, args_list)


async def run_in_loop(coro):
    return await coro


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)
