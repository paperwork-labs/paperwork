"""medallion: silver"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import finnhub
import redis
import redis.asyncio as aioredis

from backend.config import settings

logger = logging.getLogger(__name__)


class MarketInfra:
    """Shared infrastructure for all market data sub-services.

    Owns Redis connections (sync + async), API client instances,
    provider call tracking, and admin toggles.  No business logic.
    """

    def __init__(self) -> None:
        self._redis_sync: Optional[redis.Redis] = None
        self._redis_async: Optional[aioredis.Redis] = None
        # Async Redis must not be reused across closed asyncio loops (Celery tasks
        # create a fresh loop per run_until_complete and then close it).
        self._redis_async_loop: Optional[asyncio.AbstractEventLoop] = None
        self.cache_ttl_seconds: int = int(getattr(settings, "MARKET_DATA_CACHE_TTL", 300))

        self.finnhub_client = (
            finnhub.Client(api_key=settings.FINNHUB_API_KEY)
            if settings.FINNHUB_API_KEY
            else None
        )

        self.twelve_data_client = None
        try:
            from twelvedata import TDClient

            if settings.TWELVE_DATA_API_KEY:
                self.twelve_data_client = TDClient(apikey=settings.TWELVE_DATA_API_KEY)
        except Exception as e:
            logger.warning("Twelve Data client init failed, Twelve Data disabled: %s", e)
            self.twelve_data_client = None

    # ---------------------- Redis ----------------------

    @property
    def redis_client(self) -> redis.Redis:
        return self._sync_redis

    @property
    def _sync_redis(self) -> redis.Redis:
        if self._redis_sync is None:
            url = getattr(settings, "REDIS_URL", None)
            if not url:
                raise RuntimeError("REDIS_URL is not configured")
            self._redis_sync = redis.from_url(url)
        return self._redis_sync

    async def _get_redis(self) -> aioredis.Redis:
        current_loop = asyncio.get_running_loop()
        stale = self._redis_async is None
        if not stale and self._redis_async_loop is not current_loop:
            stale = True
        if not stale and self._redis_async_loop is not None and self._redis_async_loop.is_closed():
            stale = True

        if stale and self._redis_async is not None:
            try:
                await self._redis_async.aclose()
            except Exception as e:
                logger.warning("Failed to close stale async Redis client: %s", e)
            self._redis_async = None
            self._redis_async_loop = None

        if self._redis_async is None:
            url = getattr(settings, "REDIS_URL", None)
            if not url:
                raise RuntimeError("REDIS_URL is not configured")
            self._redis_async = aioredis.from_url(url)
            self._redis_async_loop = current_loop
        return self._redis_async

    # ---------------------- Provider call tracking ----------------------

    async def _record_provider_call(self, provider: str, n: int = 1) -> None:
        try:
            r = await self._get_redis()
            date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            hash_key = f"provider:calls:{date_key}"
            await r.hincrby(hash_key, provider, n)
            await r.expire(hash_key, 86400 * 30)
        except Exception:
            logger.debug("Failed to record provider call for %s", provider)

    def _record_provider_call_sync(self, provider: str, n: int = 1) -> None:
        try:
            r = self._sync_redis
            date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            hash_key = f"provider:calls:{date_key}"
            r.hincrby(hash_key, provider, n)
            r.expire(hash_key, 86400 * 30)
        except Exception:
            logger.debug("Failed to record provider call (sync) for %s", provider)

    # ---------------------- Admin toggles ----------------------

    def is_backfill_5m_enabled(self) -> bool:
        try:
            raw = self._sync_redis.get("coverage:backfill_5m_enabled")
            if raw is None:
                return False
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode()
            return str(raw).strip().lower() not in ("0", "false", "off", "disabled")
        except Exception as e:
            logger.warning(
                "is_backfill_5m_enabled Redis read failed, defaulting OFF: %s", e
            )
            return False

    async def is_backfill_5m_enabled_async(self) -> bool:
        try:
            r = await self._get_redis()
            raw = await r.get("coverage:backfill_5m_enabled")
            if raw is None:
                return False
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode()
            return str(raw).strip().lower() not in ("0", "false", "off", "disabled")
        except Exception as e:
            logger.warning(
                "is_backfill_5m_enabled_async Redis read failed, defaulting OFF: %s", e
            )
            return False
