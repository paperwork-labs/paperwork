"""Shared SlowAPI rate limiting with optional fail-open Redis storage."""

from __future__ import annotations

from slowapi import Limiter, _rate_limit_exceeded_handler

from rate_limit.keys import (
    KeyFunc,
    get_org_id_key,
    get_remote_address_key,
    get_user_id_key,
)
from rate_limit.limiter import DEFAULT_LIMITS, PaperworkLimiter, create_limiter
from rate_limit.middleware import RateLimitMiddleware
from rate_limit.storage_failopen import FailOpenRedisStorage

__all__ = [
    "DEFAULT_LIMITS",
    "FailOpenRedisStorage",
    "KeyFunc",
    "Limiter",
    "PaperworkLimiter",
    "RateLimitMiddleware",
    "_rate_limit_exceeded_handler",
    "create_limiter",
    "get_org_id_key",
    "get_remote_address_key",
    "get_user_id_key",
]
