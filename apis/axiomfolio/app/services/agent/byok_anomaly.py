"""BYOK anomaly counter.

Increments a small Redis counter every time the AgentBrain falls back
from a user's stored BYOK key to the platform key. A fallback is any of:

* stored payload is undecryptable (vault rotation, corrupt row)
* provider field is missing or not in the allowlist
* API key field is empty after decrypt
* provider host is not in :data:`BYOK_ALLOWED_HOSTS`
* Anthropic BYOK is stored but transport is not yet wired

Silent fallbacks are specifically forbidden by
``.cursor/rules/no-silent-fallback.mdc`` — a degraded BYOK path must be
visible to a downstream observer. Surfacing these counters on the
admin health payload is that visibility.

The counter is deliberately Redis-only (no DB row) because:

1. The value is entirely operational / short-lived (a 7-day rolling
   window is plenty for ops triage).
2. Writing a DB row per LLM call would be a hot-path foot-gun.
3. Losing the counter on a Redis flush is acceptable — nothing about
   billing or auth depends on it.

Module owner: :mod:`app.services.silver.market.admin_health_service`
reads the snapshot via :func:`snapshot`.

medallion: ops
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# 7-day key TTL is enough for an operator to notice and act on a spike
# without letting a single flaky key drift into permanent noise.
_KEY = "byok:anomaly:counts"
_LAST_AT_KEY = "byok:anomaly:last_at"
_KEY_TTL_S = 60 * 60 * 24 * 7  # 7 days


def _get_redis_client():
    """Resolve the shared Redis client, or ``None`` if unreachable.

    ``infra.redis_client`` is the same handle the rest of the admin
    health service uses; reusing it means one less connection pool and
    one less place to authenticate.
    """
    try:
        from app.services.silver.market.market_data_service import infra

        return infra.redis_client
    except Exception as e:  # pragma: no cover - defensive import guard
        logger.warning("byok_anomaly: redis client unavailable: %s", e)
        return None


def record_fallback(
    user_id: Optional[int], reason: str, *, provider: Optional[str] = None
) -> None:
    """Increment the anomaly counter for ``reason``.

    Never raises — observability is best-effort. If Redis is down the
    caller's decision to fall back to the platform key still stands; we
    just can't count it.

    Args:
        user_id: the user whose BYOK fell back, if known. Only used for
            logging context (we don't bucket per-user to keep the
            keyspace bounded).
        reason: short, stable reason string. Keep cardinality low (< 10
            distinct values). Examples: ``"decrypt_failed"``,
            ``"provider_not_allowed"``, ``"empty_api_key"``,
            ``"host_not_allowlisted"``,
            ``"anthropic_transport_pending"``.
        provider: the provider string from the stored payload, if
            parseable. Helpful when sifting through Sentry.
    """
    client = _get_redis_client()
    if client is None:
        return
    try:
        client.hincrby(_KEY, reason, 1)
        client.expire(_KEY, _KEY_TTL_S)
        client.set(
            _LAST_AT_KEY,
            datetime.now(timezone.utc).isoformat(),
            ex=_KEY_TTL_S,
        )
    except Exception as e:  # pragma: no cover - best-effort write
        logger.warning(
            "byok_anomaly: failed to increment reason=%s user_id=%s: %s",
            reason,
            user_id,
            e,
        )
        return
    logger.info(
        "byok_anomaly: fallback user_id=%s provider=%s reason=%s",
        user_id,
        provider,
        reason,
    )


def snapshot() -> Dict[str, Any]:
    """Return a JSON-ready snapshot of recent BYOK fallback counts.

    Shape::

        {
          "total": int,
          "by_reason": {reason: int, ...},
          "last_at": iso8601 str | None,
          "available": bool,   # False if Redis is unreachable
        }

    The ``available=False`` branch is the no-silent-fallback signal: a
    downstream observer can still tell whether the health surface
    reflects real counts or just a Redis outage.
    """
    client = _get_redis_client()
    if client is None:
        return {
            "total": 0,
            "by_reason": {},
            "last_at": None,
            "available": False,
        }
    try:
        raw = client.hgetall(_KEY) or {}
        last_at_raw = client.get(_LAST_AT_KEY)
    except Exception as e:
        logger.warning("byok_anomaly: snapshot read failed: %s", e)
        return {
            "total": 0,
            "by_reason": {},
            "last_at": None,
            "available": False,
        }
    by_reason: Dict[str, int] = {}
    for k, v in raw.items():
        key = k.decode() if isinstance(k, (bytes, bytearray)) else str(k)
        val = v.decode() if isinstance(v, (bytes, bytearray)) else str(v)
        try:
            by_reason[key] = int(val)
        except (TypeError, ValueError):
            continue
    last_at = None
    if last_at_raw is not None:
        last_at = (
            last_at_raw.decode()
            if isinstance(last_at_raw, (bytes, bytearray))
            else str(last_at_raw)
        )
    return {
        "total": sum(by_reason.values()),
        "by_reason": by_reason,
        "last_at": last_at,
        "available": True,
    }


def reset() -> None:
    """Wipe counters. Intended for test setup; no route exposes this."""
    client = _get_redis_client()
    if client is None:
        return
    try:
        client.delete(_KEY, _LAST_AT_KEY)
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("byok_anomaly: reset failed: %s", e)
