from __future__ import annotations

import asyncio
import math
from typing import Protocol

from redis.asyncio import Redis


class JobQueue(Protocol):
    async def put(self, job_id: str) -> None: ...
    async def get(self, timeout_seconds: float) -> str | None: ...
    async def close(self) -> None: ...


class InMemoryQueue:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()

    async def put(self, job_id: str) -> None:
        await self._queue.put(job_id)

    async def get(self, timeout_seconds: float) -> str | None:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout_seconds)
        except TimeoutError:
            return None

    async def close(self) -> None:
        return None


class RedisQueue:
    def __init__(self, redis_url: str, queue_name: str) -> None:
        self._queue_name = queue_name
        self._redis = Redis.from_url(redis_url, decode_responses=True)

    async def put(self, job_id: str) -> None:
        await self._redis.lpush(self._queue_name, job_id)

    async def get(self, timeout_seconds: float) -> str | None:
        timeout = max(1, math.ceil(timeout_seconds))
        result = await self._redis.brpop(self._queue_name, timeout=timeout)
        if result is None:
            return None
        _, job_id = result
        return job_id

    async def close(self) -> None:
        await self._redis.aclose()
