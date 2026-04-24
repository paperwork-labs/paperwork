"""Process-wide sync Redis client for distributed locks and short-lived cache.

This module was referenced by multiple callers
(`backend/services/execution/order_manager.py`,
`backend/services/risk/pre_trade_validator.py`,
`backend/tasks/portfolio/sync.py`,
`backend/api/routes/webhooks/tradingview.py`) but did not exist, causing every
lock acquisition to raise `ModuleNotFoundError`, hit the broad `except` in
those callers, log a warning, and proceed **without** a lock. See KNOWLEDGE.md
entry R40.

Callers should continue to wrap `redis_client` usage in try/except and decide
fail-open vs fail-closed per their risk posture (the lock is best-effort, not
a correctness guarantee). But now, on a healthy Redis, the lock will actually
hold.

Usage:
    from backend.services.cache import redis_client

    if redis_client.set(key, "1", nx=True, ex=60):
        ...  # acquired

Module attribute access is lazy (via module `__getattr__`) so unit tests that
don't exercise Redis aren't forced to have `REDIS_URL` configured at import
time. Instantiation failure surfaces at first *use*, not at import.

medallion: ops
"""

from __future__ import annotations

import logging
from typing import Optional

import redis

from backend.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """Return the process-wide sync Redis client, instantiating on first call.

    Raises:
        RuntimeError: if ``REDIS_URL`` is not configured. The existing
            try/except in call sites will catch this and fall back to
            no-lock behavior with a warning log, preserving current
            availability semantics while surfacing the misconfiguration.
    """
    global _redis_client
    if _redis_client is None:
        url = getattr(settings, "REDIS_URL", None)
        if not url:
            raise RuntimeError(
                "REDIS_URL is not configured; cannot create sync Redis client "
                "for distributed locks."
            )
        _redis_client = redis.from_url(url)
        logger.info("backend.services.cache.redis_client initialized")
    return _redis_client


def __getattr__(name: str) -> redis.Redis:
    if name == "redis_client":
        return get_redis_client()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
