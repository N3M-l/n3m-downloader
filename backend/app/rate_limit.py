"""Sliding-window rate limiting keyed by client IP."""

from __future__ import annotations

import asyncio
import math
import time
from collections import deque

from starlette.requests import Request


def client_ip(request: Request, *, trust_proxy: bool) -> str:
    """Return the caller address, honouring the proxy's last X-Forwarded-For hop."""
    if trust_proxy:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            parts = [part.strip() for part in forwarded.split(",") if part.strip()]
            if parts:
                return parts[-1]
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


class SlidingWindowLimiter:
    """Per-key sliding window; every key stores timestamps in a deque."""

    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        async with self._lock:
            bucket = self._hits.setdefault(key, deque())
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                retry = max(1, math.ceil(self.window_seconds - (now - bucket[0])))
                return False, retry
            bucket.append(now)
            if len(self._hits) > 5000:
                self._prune(cutoff)
            return True, 0

    def _prune(self, cutoff: float) -> None:
        stale = [key for key, bucket in self._hits.items() if not bucket or bucket[-1] <= cutoff]
        for key in stale:
            self._hits.pop(key, None)

    async def reset(self) -> None:
        async with self._lock:
            self._hits.clear()
