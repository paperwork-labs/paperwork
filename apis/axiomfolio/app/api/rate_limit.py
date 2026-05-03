"""
SlowAPI limiter singleton (shared rate-limit package).

Defined here so route modules can import `limiter` without importing `main`
(circular import: main loads routers which would load main again).
"""

from slowapi.util import get_remote_address

from rate_limit import create_limiter

from app.config import settings

limiter = create_limiter(
    redis_url=settings.RATE_LIMIT_STORAGE_URL or None,
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
)
