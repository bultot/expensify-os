"""Tests for the rate limiter."""

from __future__ import annotations

import asyncio
import time

import pytest

from expensify_os.expensify.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_allows_requests_within_limit():
    limiter = RateLimiter(short_limit=3, short_window=10.0, long_limit=10, long_window=60.0)

    # 3 requests should all go through immediately
    start = time.monotonic()
    for _ in range(3):
        await limiter.acquire()
    elapsed = time.monotonic() - start

    assert elapsed < 0.1  # Should be near-instant


@pytest.mark.asyncio
async def test_blocks_when_short_limit_exceeded():
    limiter = RateLimiter(short_limit=2, short_window=0.3, long_limit=100, long_window=60.0)

    # Fill the short window
    await limiter.acquire()
    await limiter.acquire()

    # Third request should wait ~0.3s
    start = time.monotonic()
    await limiter.acquire()
    elapsed = time.monotonic() - start

    assert elapsed >= 0.2  # Should have waited for the window to slide


@pytest.mark.asyncio
async def test_prunes_old_timestamps():
    limiter = RateLimiter(short_limit=5, short_window=10.0, long_limit=20, long_window=0.1)

    # Fill with some timestamps
    for _ in range(5):
        await limiter.acquire()

    # Wait for long window to expire
    await asyncio.sleep(0.15)

    # After pruning, should be able to continue
    await limiter.acquire()
    assert len(limiter._timestamps) <= 6
