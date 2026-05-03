"""Per-user daily MCP call quota backed by Redis.

Design notes:

* **Fail-OPEN on Redis outage.** Treating the rate limiter as a hard
  dependency would turn a Redis hiccup into a global MCP outage for
  every tier. We allow the call but increment a degradation counter so
  ops can see what happened on ``/admin/health``.
* **Single counter per (user, UTC day).** ``mcp:calls:<user_id>:<YYYY-MM-DD>``
  with a 25-hour TTL so the key self-cleans even if the next day's
  request never lands. Key prefix is configurable so multiple products
  sharing one Redis can keep counters in different namespaces.
* **Sync-only.** AxiomFolio's MCP transport is sync-FastAPI today; the
  helper mirrors that. Async variant is intentionally deferred until a
  consumer needs it.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import redis

logger = logging.getLogger(__name__)


# A small helper type alias: callers pass in a zero-arg factory rather
# than a connected client, so we never hold a reference across loops or
# fork boundaries the consumer hasn't authorized.
RedisClientFactory = Callable[[], "redis.Redis"]


class DailyCallQuota:
    """Increment-and-check daily call counter with degradation reporting.

    Usage::

        quota = DailyCallQuota(lambda: my_redis_client)
        ok = quota.consume(user_id=42, limit=1000)
        if not ok:
            # over the daily cap

    The factory is called every ``consume()`` so ``MarketInfra``-style
    lazy clients (``self._redis_sync`` constructed on first access)
    behave correctly without us caching anything that might go stale.
    """

    DEFAULT_KEY_PREFIX = "mcp:calls"
    # 24h + 1h slack so the key auto-cleans even if a slow client hits
    # right at the day boundary.
    DEFAULT_TTL_SECONDS = 60 * 60 * 25

    def __init__(
        self,
        redis_client_factory: RedisClientFactory,
        *,
        key_prefix: str = DEFAULT_KEY_PREFIX,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._factory = redis_client_factory
        self._key_prefix = key_prefix
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._degradation: dict[str, Any] = {
            "count": 0,
            "last_error": None,
            "last_at": None,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def consume(self, *, user_id: int, limit: int) -> bool:
        """Increment today's counter and return True if still under ``limit``.

        Returns False only when the counter increments **past** ``limit``.
        Returns True (fail-open) on any Redis error, after recording the
        outage in :py:meth:`degradation_snapshot`.
        """
        day = self._clock().date().isoformat()
        key = f"{self._key_prefix}:{user_id}:{day}"
        try:
            client = self._factory()
            used = int(client.incr(key))
            if used == 1:
                client.expire(key, self._ttl_seconds)
            return used <= limit
        except Exception as e:
            logger.warning(
                "MCP quota Redis unavailable (fail-open) user_id=%s: %s",
                user_id,
                e,
            )
            self._record_degradation(e)
            return True

    def degradation_snapshot(self) -> dict[str, Any]:
        """Return a copy of the degradation counters for ``/admin/health``."""
        return dict(self._degradation)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _record_degradation(self, exc: BaseException) -> None:
        # Best effort -- if the counter itself blows up we still want
        # consume() to return True. Diagnostic only.
        try:
            self._degradation["count"] += 1
            self._degradation["last_error"] = str(exc)
            self._degradation["last_at"] = self._clock().isoformat()
        except Exception:
            pass


def make_module_level_quota(
    redis_client_factory: RedisClientFactory,
    *,
    key_prefix: str = DailyCallQuota.DEFAULT_KEY_PREFIX,
) -> tuple[DailyCallQuota, Callable[[], dict[str, Any]]]:
    """Convenience factory matching AxiomFolio's original surface.

    Returns ``(quota, snapshot_callable)`` so callers can wire
    ``snapshot_callable`` directly into their ``/admin/health`` payload
    without keeping a reference to ``DailyCallQuota`` itself.
    """
    quota = DailyCallQuota(redis_client_factory, key_prefix=key_prefix)
    return quota, quota.degradation_snapshot


__all__ = ["DailyCallQuota", "RedisClientFactory", "make_module_level_quota"]


# Optional: ``redis`` is needed only for the sync type alias. We import
# at the top because the module is small and fail-fast import is
# preferable to surprising AttributeError later.
def _redis_module_check() -> str | None:  # pragma: no cover - sanity helper
    return getattr(redis, "__version__", None)
