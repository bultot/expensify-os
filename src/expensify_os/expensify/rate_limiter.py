"""Rate limiter for the Expensify API.

Expensify enforces:
  - 5 requests per 10 seconds
  - 20 requests per 60 seconds

This implements a sliding-window rate limiter that respects both limits.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque


class RateLimiter:
    """Sliding-window rate limiter with multiple window support."""

    def __init__(
        self,
        *,
        short_limit: int = 5,
        short_window: float = 10.0,
        long_limit: int = 20,
        long_window: float = 60.0,
    ) -> None:
        self.short_limit = short_limit
        self.short_window = short_window
        self.long_limit = long_limit
        self.long_window = long_window
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    def _prune(self, now: float) -> None:
        """Remove timestamps older than the longest window."""
        cutoff = now - self.long_window
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

    def _wait_time(self, now: float) -> float:
        """Calculate how long to wait before the next request is allowed."""
        self._prune(now)

        wait = 0.0

        # Check short window (5 req / 10s)
        short_cutoff = now - self.short_window
        short_count = sum(1 for t in self._timestamps if t >= short_cutoff)
        if short_count >= self.short_limit:
            oldest_in_window = next(t for t in self._timestamps if t >= short_cutoff)
            wait = max(wait, oldest_in_window + self.short_window - now)

        # Check long window (20 req / 60s)
        if len(self._timestamps) >= self.long_limit:
            wait = max(wait, self._timestamps[0] + self.long_window - now)

        return wait

    async def acquire(self) -> None:
        """Wait until a request is allowed, then record the timestamp."""
        async with self._lock:
            while True:
                now = time.monotonic()
                wait = self._wait_time(now)
                if wait <= 0:
                    self._timestamps.append(now)
                    return
                await asyncio.sleep(wait)
