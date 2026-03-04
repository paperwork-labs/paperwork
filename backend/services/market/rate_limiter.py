"""Proactive per-provider rate limiter (token-bucket model).

Prevents hitting 429s by enforcing minimum spacing between API calls
per provider, complementing the existing concurrency semaphore and
reactive backoff in market_data_service.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class TokenBucketLimiter:
    """Async token-bucket rate limiter for a single provider.

    Args:
        calls_per_minute: max sustained call rate
        burst: optional burst capacity (defaults to calls_per_minute / 10, min 1)
    """

    def __init__(self, calls_per_minute: int, *, burst: Optional[int] = None) -> None:
        self.rate = calls_per_minute / 60.0  # tokens per second
        self.max_tokens = burst if burst is not None else max(1, calls_per_minute // 10)
        self._tokens = float(self.max_tokens)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.max_tokens, self._tokens + elapsed * self.rate)
        self._last_refill = now

    async def acquire(self) -> None:
        """Wait until a token is available, then consume one."""
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait_time = (1.0 - self._tokens) / self.rate
            await asyncio.sleep(min(wait_time, 2.0))

    def acquire_sync(self) -> None:
        """Blocking variant for sync code paths (Celery tasks)."""
        while True:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return
            wait_time = (1.0 - self._tokens) / self.rate
            time.sleep(min(wait_time, 2.0))


class ProviderRateLimiter:
    """Registry of per-provider rate limiters.

    Default limits (calls/minute) tuned for free/starter tiers:
        FMP Starter:    250 (conservative vs 300 limit)
        Finnhub Free:    50
        Twelve Data:      7
        Alpha Vantage:    4
        yfinance:        30 (unofficial, be polite)
    """

    DEFAULT_LIMITS: Dict[str, int] = {
        "fmp": 250,
        "finnhub": 50,
        "twelvedata": 7,
        "alphavantage": 4,
        "yfinance": 30,
    }

    def __init__(self, overrides: Optional[Dict[str, int]] = None) -> None:
        limits = {**self.DEFAULT_LIMITS, **(overrides or {})}
        self._limiters: Dict[str, TokenBucketLimiter] = {
            name: TokenBucketLimiter(cpm)
            for name, cpm in limits.items()
        }

    def get(self, provider: str) -> Optional[TokenBucketLimiter]:
        return self._limiters.get(provider.lower())

    async def acquire(self, provider: str) -> None:
        limiter = self.get(provider)
        if limiter:
            await limiter.acquire()

    def acquire_sync(self, provider: str) -> None:
        limiter = self.get(provider)
        if limiter:
            limiter.acquire_sync()


provider_rate_limiter = ProviderRateLimiter()
