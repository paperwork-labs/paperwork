"""
SlowAPI limiter singleton.

Defined here so route modules can import `limiter` without importing `main`
(circular import: main loads routers which would load main again).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    storage_uri=settings.RATE_LIMIT_STORAGE_URL or None,
)
