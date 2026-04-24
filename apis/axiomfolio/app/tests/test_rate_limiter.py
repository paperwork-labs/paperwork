"""Tests for the token-bucket rate limiter.

Covers CPM=0 pass-through, normal rate limiting for CPM > 0,
and edge cases around infinite rate / refill.
"""

import asyncio
import math
import time

import pytest

from app.services.silver.math.rate_limiter import TokenBucketLimiter, ProviderRateLimiter


pytestmark = pytest.mark.no_db


# ── CPM=0 pass-through ──────────────────────────────────────────────


class TestCPMZero:
    """CPM=0 means no rate cap; all calls are instant no-ops."""

    def test_init_does_not_crash(self):
        limiter = TokenBucketLimiter(0)
        assert math.isinf(limiter.rate)
        assert math.isinf(limiter.max_tokens)

    def test_acquire_returns_immediately(self):
        limiter = TokenBucketLimiter(0)
        loop = asyncio.new_event_loop()
        try:
            start = time.monotonic()
            loop.run_until_complete(limiter.acquire())
            elapsed = time.monotonic() - start
            assert elapsed < 0.1, "acquire() should be instant for CPM=0"
        finally:
            loop.close()

    def test_acquire_sync_returns_immediately(self):
        limiter = TokenBucketLimiter(0)
        start = time.monotonic()
        limiter.acquire_sync()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1, "acquire_sync() should be instant for CPM=0"

    def test_many_rapid_calls_do_not_block(self):
        limiter = TokenBucketLimiter(0)
        start = time.monotonic()
        for _ in range(100):
            limiter.acquire_sync()
        elapsed = time.monotonic() - start
        assert elapsed < 0.5, "100 acquire_sync() calls should be near-instant for CPM=0"


# ── Normal rate limiting (CPM > 0) ──────────────────────────────────


class TestNormalRateLimiting:
    """CPM > 0 enforces actual rate limiting."""

    def test_burst_available_immediately(self):
        limiter = TokenBucketLimiter(600, burst=5)
        assert limiter.max_tokens == 5
        for _ in range(5):
            limiter.acquire_sync()

    def test_rate_calculated_correctly(self):
        limiter = TokenBucketLimiter(120)
        assert limiter.rate == pytest.approx(2.0)

    def test_exceeding_burst_causes_wait(self):
        limiter = TokenBucketLimiter(600, burst=2)
        limiter.acquire_sync()
        limiter.acquire_sync()
        start = time.monotonic()
        limiter.acquire_sync()
        elapsed = time.monotonic() - start
        assert elapsed > 0.01, "Third call should wait for token refill"

    def test_default_burst_is_cpm_div_10(self):
        limiter = TokenBucketLimiter(100)
        assert limiter.max_tokens == 10

    def test_default_burst_minimum_is_1(self):
        limiter = TokenBucketLimiter(5)
        assert limiter.max_tokens >= 1


# ── Refill edge cases ───────────────────────────────────────────────


class TestRefillEdgeCases:
    """Test _refill handles inf rate gracefully."""

    def test_refill_skips_when_rate_is_inf(self):
        limiter = TokenBucketLimiter(0)
        old_tokens = limiter._tokens
        limiter._refill()
        assert limiter._tokens == old_tokens, "_refill must be a no-op for inf rate"

    def test_refill_adds_tokens_for_normal_rate(self):
        limiter = TokenBucketLimiter(6000, burst=10)
        limiter._tokens = 0.0
        limiter._last_refill = time.monotonic() - 1.0
        limiter._refill()
        assert limiter._tokens > 0, "Refill should add tokens after elapsed time"

    def test_refill_caps_at_max_tokens(self):
        limiter = TokenBucketLimiter(600, burst=5)
        limiter._tokens = 4.0
        limiter._last_refill = time.monotonic() - 100.0
        limiter._refill()
        assert limiter._tokens == limiter.max_tokens


# ── ProviderRateLimiter registry ────────────────────────────────────


class TestProviderRateLimiter:
    """Test the provider registry wrapper."""

    def test_unknown_provider_returns_none(self):
        registry = ProviderRateLimiter(overrides={"fmp": 60})
        assert registry.get("nonexistent_provider") is None

    def test_override_applies(self):
        registry = ProviderRateLimiter(overrides={"fmp": 120})
        limiter = registry.get("fmp")
        assert limiter is not None
        assert limiter.rate == pytest.approx(2.0)

    def test_acquire_sync_works_through_registry(self):
        registry = ProviderRateLimiter(overrides={"fmp": 6000})
        registry.acquire_sync("fmp")

    def test_acquire_async_works_through_registry(self):
        registry = ProviderRateLimiter(overrides={"fmp": 6000})
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(registry.acquire("fmp"))
        finally:
            loop.close()

    def test_acquire_unknown_provider_is_noop(self):
        registry = ProviderRateLimiter(overrides={"fmp": 60})
        registry.acquire_sync("unknown")
