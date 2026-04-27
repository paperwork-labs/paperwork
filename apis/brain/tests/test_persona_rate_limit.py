"""Tests for Track I per-persona rate limiting.

These protect the contract that `/brain/process` honours per-persona
``requests_per_minute`` from the PersonaSpec and fails open on Redis
outages rather than taking the whole Brain down with it.

medallion: ops
"""

from __future__ import annotations

import time

import pytest

from app.services.persona_rate_limit import (
    PersonaRateLimitExceeded,
    check_and_increment,
)


class _FakeRedis:
    """Minimal INCR/EXPIRE surface for per-persona rate limits."""

    def __init__(self) -> None:
        self.store: dict[str, int] = {}
        self.ttl: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.store[key] = self.store.get(key, 0) + 1
        return self.store[key]

    async def expire(self, key: str, ttl: int, nx: bool = False) -> None:
        if nx and key in self.ttl:
            return
        self.ttl[key] = ttl


@pytest.mark.asyncio
async def test_rate_limit_none_is_noop():
    r = _FakeRedis()
    count = await check_and_increment(
        r,
        organization_id="org-1",
        persona="cpa",
        limit_per_minute=None,
    )
    assert count == 0
    assert r.store == {}


@pytest.mark.asyncio
async def test_rate_limit_allows_under_cap():
    r = _FakeRedis()
    for _ in range(5):
        await check_and_increment(
            r,
            organization_id="org-1",
            persona="cpa",
            limit_per_minute=10,
        )
    assert any(v == 5 for v in r.store.values())


@pytest.mark.asyncio
async def test_rate_limit_raises_when_over_cap():
    r = _FakeRedis()
    for _ in range(3):
        await check_and_increment(
            r,
            organization_id="org-1",
            persona="cpa",
            limit_per_minute=3,
        )
    with pytest.raises(PersonaRateLimitExceeded) as exc:
        await check_and_increment(
            r,
            organization_id="org-1",
            persona="cpa",
            limit_per_minute=3,
        )
    assert exc.value.persona == "cpa"
    assert exc.value.limit == 3
    assert exc.value.current == 4
    assert exc.value.retry_after >= 1


@pytest.mark.asyncio
async def test_rate_limit_fails_open_without_redis():
    """Prefer degraded ops to taking Brain down."""
    count = await check_and_increment(
        None,
        organization_id="org-1",
        persona="cpa",
        limit_per_minute=10,
    )
    assert count == 0


@pytest.mark.asyncio
async def test_rate_limit_fails_open_on_redis_error():
    class _BrokenRedis:
        async def incr(self, _key: str) -> int:
            raise RuntimeError("connection refused")

        async def expire(self, _key: str, _ttl: int, _nx: bool = False) -> None:
            raise RuntimeError("connection refused")

    count = await check_and_increment(
        _BrokenRedis(),
        organization_id="org-1",
        persona="cpa",
        limit_per_minute=10,
    )
    assert count == 0


@pytest.mark.asyncio
async def test_rate_limit_window_rolls_over():
    """A key from a previous minute must not poison the new window."""
    r = _FakeRedis()
    old_bucket = (int(time.time()) // 60) - 1
    r.store[f"ratelimit:persona:org-1:cpa:{old_bucket}"] = 999
    count = await check_and_increment(
        r,
        organization_id="org-1",
        persona="cpa",
        limit_per_minute=5,
    )
    assert count == 1
