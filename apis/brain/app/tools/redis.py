"""Redis helpers for Brain tools — scheduler locks across Gunicorn workers.

Fails open when Redis is unavailable so jobs still run (possible duplicate execution).
"""

from __future__ import annotations

import logging
import os
import time

logger = logging.getLogger(__name__)


async def try_acquire_scheduler_lock(key: str, ttl_seconds: int) -> bool:
    """Return True if this worker acquired the lock (should run the job).

    Return False if another worker holds ``key`` (caller should skip).

    On Redis errors or uninitialized Redis, log WARNING and return True (fail open).
    """
    try:
        from app.redis import get_redis

        redis_client = get_redis()
    except Exception:
        logger.warning(
            "scheduler lock: Redis unavailable (%s), proceeding without lock",
            key,
            exc_info=True,
        )
        return True
    token = f"{os.getpid()}:{time.time():.6f}"
    try:
        acquired = await redis_client.set(key, token, nx=True, ex=int(ttl_seconds))
    except Exception:
        logger.warning(
            "scheduler lock: acquire failed (%s), proceeding without lock",
            key,
            exc_info=True,
        )
        return True
    return acquired is True


async def release_scheduler_lock(key: str) -> None:
    """Best-effort ``DEL`` of ``key`` (TTL still expires if this fails)."""
    try:
        from app.redis import get_redis

        redis_client = get_redis()
        await redis_client.delete(key)
    except Exception:
        logger.debug("scheduler lock: release failed (%s)", key, exc_info=True)
