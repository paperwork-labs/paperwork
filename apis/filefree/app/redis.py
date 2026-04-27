from __future__ import annotations

import inspect
import logging

from redis.asyncio import Redis

from app.config import settings

logger = logging.getLogger(__name__)

_redis_pool: Redis | None = None


async def init_redis() -> None:
    global _redis_pool
    _redis_pool = Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=5,
    )
    try:
        # Stubs type ping() as Awaitable[bool] | bool; async client always returns a coroutine.
        ping = _redis_pool.ping()
        if inspect.isawaitable(ping):
            await ping
        else:
            assert ping
        raw = settings.REDIS_URL
        masked_url = raw.split("@")[-1] if "@" in raw else raw
        logger.info("Redis connected (%s)", masked_url)
    except Exception:
        logger.warning("Redis not available — sessions will fail")
        if _redis_pool is not None:
            await _redis_pool.aclose()
            _redis_pool = None


async def close_redis() -> None:
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None
        logger.info("Redis connection closed")


def get_redis() -> Redis:
    if _redis_pool is None:
        raise RuntimeError("Redis not initialized — call init_redis() first")
    return _redis_pool
