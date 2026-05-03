"""Factory for a SlowAPI :class:`~slowapi.Limiter` with optional Redis + fail-open."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from rate_limit import storage_failopen  # noqa: F401 — register failopen-* schemes
from rate_limit.storage_failopen import _to_failopen_uri

DEFAULT_LIMITS: list[str] = ["100/minute", "1000/hour"]


def _default_key_func(request: Request) -> str:
    uid = getattr(request.state, "user_id", None)
    if uid is not None:
        return str(uid)
    return get_remote_address(request)


class PaperworkLimiter(Limiter):
    """SlowAPI limiter with a :meth:`degradation_snapshot` hook for health payloads."""

    _paperwork_degradation: dict[str, Any]

    def __init__(self, *, paperwork_degradation: dict[str, Any], **kwargs: Any) -> None:
        self._paperwork_degradation = paperwork_degradation
        super().__init__(**kwargs)

    def degradation_snapshot(self) -> dict[str, Any]:
        """Return a copy of Redis fail-open counters (``quota.py``-compatible shape)."""
        return dict(self._paperwork_degradation)


def create_limiter(
    redis_url: str | None = None,
    key_func: Callable[..., str] | None = None,
    default_limits: list[str] | None = None,
    *,
    clock: Callable[[], datetime] | None = None,
    headers_enabled: bool = True,
) -> PaperworkLimiter:
    """Build a SlowAPI limiter with memory or fail-open Redis storage.

    With ``redis_url``, storage uses ``FailOpenRedisStorage``
    (``failopen-redis://`` URIs).
    On Redis errors, requests are allowed (fail-OPEN) and
    :meth:`PaperworkLimiter.degradation_snapshot` records the outage (same idea as
    ``mcp_server.quota.DailyCallQuota``).

    Args:
        redis_url: ``redis://`` / ``rediss://``, or ``None`` for in-memory storage.
        key_func: SlowAPI key callable; default uses ``request.state.user_id`` then IP.
        default_limits: Global limit strings; default ``100/minute`` and ``1000/hour``.
        clock: Injected clock for degradation timestamps (tests).
        headers_enabled: If True, SlowAPI emits rate headers including Retry-After.
    """
    _clock = clock or (lambda: datetime.now(UTC))
    degradation: dict[str, Any] = {
        "count": 0,
        "last_error": None,
        "last_at": None,
    }

    limits = DEFAULT_LIMITS if default_limits is None else list(default_limits)
    kf = key_func or _default_key_func

    storage_uri: str
    storage_options: dict[str, Any] = {}
    if redis_url is not None:
        storage_uri = _to_failopen_uri(redis_url)
        storage_options["degradation"] = degradation
        storage_options["clock"] = _clock
    else:
        storage_uri = "memory://"

    return PaperworkLimiter(
        paperwork_degradation=degradation,
        key_func=kf,
        default_limits=limits,
        storage_uri=storage_uri,
        storage_options=storage_options,
        headers_enabled=headers_enabled,
    )


__all__ = ["DEFAULT_LIMITS", "PaperworkLimiter", "create_limiter"]
