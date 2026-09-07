from __future__ import annotations

import asyncio
import hashlib
import time
from collections.abc import Callable
from typing import Any, Protocol


class RateLimiter(Protocol):
    async def allow(self, key: str, *, limit: int, window_seconds: int) -> bool: ...


class InMemoryRateLimiter:
    """Deterministic development/test limiter; production must use Redis."""

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.monotonic
        self._entries: dict[str, tuple[float, int]] = {}
        self._lock = asyncio.Lock()

    async def allow(self, key: str, *, limit: int, window_seconds: int) -> bool:
        now = self._clock()
        async with self._lock:
            started, count = self._entries.get(key, (now, 0))
            if now - started >= window_seconds:
                started, count = now, 0
            count += 1
            self._entries[key] = (started, count)
            return count <= limit


class RedisRateLimiter:
    def __init__(self, client: Any) -> None:
        self.client = client

    async def allow(self, key: str, *, limit: int, window_seconds: int) -> bool:
        count = int(await self.client.incr(key))
        if count == 1:
            await self.client.expire(key, window_seconds)
        return count <= limit


def rate_limit_key(namespace: str, subject: str) -> str:
    digest = hashlib.sha256(subject.strip().casefold().encode()).hexdigest()[:32]
    return f"{namespace}:{digest}"
