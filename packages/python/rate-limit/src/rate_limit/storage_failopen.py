"""Redis-backed limits storage that fail-opens on backend errors.

Registers custom ``failopen-redis://`` / ``failopen-rediss://`` schemes with
``limits`` so :class:`slowapi.Limiter` can be constructed via ``storage_uri``.
"""

from __future__ import annotations

import logging
import time
import urllib.parse
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

from limits.storage import RedisStorage
from limits.storage.base import (
    MovingWindowSupport,
    SlidingWindowCounterSupport,
    Storage,
)

logger = logging.getLogger(__name__)


def _inner_redis_uri(uri: str) -> str:
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme == "failopen-redis":
        return urllib.parse.urlunparse(parsed._replace(scheme="redis"))
    if parsed.scheme == "failopen-rediss":
        return urllib.parse.urlunparse(parsed._replace(scheme="rediss"))
    raise ValueError(f"unsupported failopen storage uri scheme: {parsed.scheme}")


def _to_failopen_uri(redis_url: str) -> str:
    parsed = urllib.parse.urlparse(redis_url)
    if parsed.scheme == "redis":
        return urllib.parse.urlunparse(parsed._replace(scheme="failopen-redis"))
    if parsed.scheme == "rediss":
        return urllib.parse.urlunparse(parsed._replace(scheme="failopen-rediss"))
    raise ValueError(
        "redis_url must start with redis:// or rediss:// "
        f"(got scheme {parsed.scheme!r})"
    )


class FailOpenRedisStorage(Storage, MovingWindowSupport, SlidingWindowCounterSupport):
    """Delegate to :class:`limits.storage.RedisStorage`; allow traffic if Redis fails.

    On any storage error we log, update the shared ``degradation`` dict (same
    shape as :meth:`mcp_server.quota.DailyCallQuota.degradation_snapshot`), and
    return values that keep rate checks passing (fail-OPEN).
    """

    STORAGE_SCHEME = ["failopen-redis", "failopen-rediss"]  # noqa: RUF012

    def __init__(self, uri: str, **options: Any) -> None:
        degradation_any = options.pop("degradation", None)
        clock_any = options.pop("clock", lambda: datetime.now(UTC))
        super().__init__(uri, wrap_exceptions=False, **options)
        self._degradation = cast(dict[str, Any] | None, degradation_any)
        self._clock = cast(Callable[[], datetime], clock_any)
        inner_uri = _inner_redis_uri(uri)
        self._inner = RedisStorage(inner_uri, **cast(Any, options))

    @property
    def base_exceptions(self) -> type[Exception] | tuple[type[Exception], ...]:
        return self._inner.base_exceptions

    def _record(self, exc: BaseException) -> None:
        logger.warning("rate-limit Redis unavailable (fail-open): %s", exc)
        if self._degradation is None:
            return
        try:
            self._degradation["count"] += 1
            self._degradation["last_error"] = str(exc)
            self._degradation["last_at"] = self._clock().isoformat()
        except Exception:
            pass

    def incr(self, key: str, expiry: int, amount: int = 1) -> int:
        try:
            return self._inner.incr(key, expiry, amount=amount)
        except Exception as e:
            self._record(e)
            return 0

    def get(self, key: str) -> int:
        try:
            return self._inner.get(key)
        except Exception as e:
            self._record(e)
            return 0

    def get_expiry(self, key: str) -> float:
        try:
            return self._inner.get_expiry(key)
        except Exception as e:
            self._record(e)
            return time.time() + 1.0

    def clear(self, key: str) -> None:
        try:
            self._inner.clear(key)
        except Exception as e:
            self._record(e)

    def check(self) -> bool:
        try:
            return self._inner.check()
        except Exception as e:
            self._record(e)
            return False

    def reset(self) -> int | None:
        try:
            return self._inner.reset()
        except Exception as e:
            self._record(e)
            return None

    def get_moving_window(self, key: str, limit: int, expiry: int) -> tuple[float, int]:
        try:
            return self._inner.get_moving_window(key, limit, expiry)
        except Exception as e:
            self._record(e)
            return time.time(), 0

    def acquire_entry(self, key: str, limit: int, expiry: int, amount: int = 1) -> bool:
        try:
            return self._inner.acquire_entry(key, limit, expiry, amount=amount)
        except Exception as e:
            self._record(e)
            return True

    def get_sliding_window(
        self, key: str, expiry: int
    ) -> tuple[int, float, int, float]:
        try:
            return self._inner.get_sliding_window(key, expiry)
        except Exception as e:
            self._record(e)
            return 0, 0.0, 0, 0.0

    def acquire_sliding_window_entry(
        self, key: str, limit: int, expiry: int, amount: int = 1
    ) -> bool:
        try:
            return self._inner.acquire_sliding_window_entry(
                key, limit, expiry, amount=amount
            )
        except Exception as e:
            self._record(e)
            return True

    def clear_sliding_window(self, key: str, expiry: int) -> None:
        try:
            self._inner.clear_sliding_window(key, expiry)
        except Exception as e:
            self._record(e)


__all__ = ["FailOpenRedisStorage"]
