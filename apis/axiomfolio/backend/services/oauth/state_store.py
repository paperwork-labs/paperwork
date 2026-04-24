"""Transient OAuth flow-state store backed by Redis.

OAuth 1.0a needs us to remember the ``request_token_secret`` between the
``initiate_url`` redirect and the ``exchange_code`` callback. We can't put it
in a JWT (the user agent never holds it) and we don't want to persist it in
Postgres (it's expired in 5 minutes anyway). Redis with a short TTL fits.

Keying: ``oauth:state:{broker}:{state}``. ``state`` is the CSRF nonce
returned by the adapter, so collisions are negligible.

There is an in-memory fallback when Redis is unavailable so dev-without-Redis
and unit tests still work; in production Redis must be reachable or callbacks
will fail loudly when the key is missing.

medallion: ops
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_DEFAULT_TTL_SECONDS = 600  # 10 minutes — covers slow human + verifier paste

_memory_lock = threading.Lock()
_memory_store: Dict[str, tuple[float, Dict[str, Any]]] = {}


def _normalize_state_token(state: str) -> str:
    """Strip whitespace; preserve case (URL-safe nonce must not be lowercased)."""

    return (state or "").strip()


def _key(broker: str, state: str) -> str:
    return f"oauth:state:{broker}:{_normalize_state_token(state)}"


def _redis_client():
    """Best-effort Redis lookup; returns ``None`` if unavailable."""

    try:
        from backend.core.redis_client import get_redis  # type: ignore
    except ImportError as exc:
        logger.debug(
            "Preferred Redis client import failed for OAuth state store; "
            "falling back to direct Redis client: %s",
            exc,
        )
    else:
        try:
            return get_redis()
        except (AttributeError, OSError, RuntimeError) as exc:
            logger.debug(
                "Preferred Redis client initialization failed for OAuth state "
                "store; falling back to direct Redis client: %s",
                exc,
            )

    try:
        import redis  # type: ignore
        from redis.exceptions import RedisError  # type: ignore

        from backend.config import settings

        url = getattr(settings, "REDIS_URL", None)
        if not url:
            return None
        return redis.Redis.from_url(url, decode_responses=True)
    except ImportError as exc:
        logger.debug("Redis unavailable for OAuth state store: %s", exc)
        return None
    except (RedisError, OSError, ValueError) as exc:
        logger.debug("Redis unavailable for OAuth state store: %s", exc)
        return None


def save_extra(
    broker: str,
    state: str,
    extra: Dict[str, Any],
    *,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> None:
    """Persist ``extra`` against ``(broker, state)`` for ``ttl_seconds``."""

    norm = _normalize_state_token(state)
    payload = json.dumps(extra)
    client = _redis_client()
    if client is not None:
        try:
            client.setex(_key(broker, norm), ttl_seconds, payload)
            return
        except Exception as exc:
            logger.warning(
                "Redis setex failed for oauth state broker=%s: %s; using memory fallback",
                broker,
                exc,
            )
    expiry = time.monotonic() + ttl_seconds
    with _memory_lock:
        _memory_store[_key(broker, norm)] = (expiry, dict(extra))


def load_extra(broker: str, state: str) -> Optional[Dict[str, Any]]:
    """Pop the stored ``extra`` for ``(broker, state)``; ``None`` if missing."""

    norm = _normalize_state_token(state)
    key = _key(broker, norm)
    client = _redis_client()
    if client is not None:
        try:
            raw = client.get(key)
            if raw is not None:
                try:
                    client.delete(key)
                except Exception as del_exc:
                    logger.debug(
                        "OAuth state Redis delete failed after get broker=%s: %s",
                        broker,
                        del_exc,
                    )
                return json.loads(raw)
        except Exception as exc:
            logger.warning(
                "Redis get failed for oauth state broker=%s: %s; trying memory fallback",
                broker,
                exc,
            )
    with _memory_lock:
        entry = _memory_store.pop(key, None)
    if entry is None:
        return None
    expiry, payload = entry
    if expiry < time.monotonic():
        return None
    return payload


def clear_memory_store() -> None:
    """Test helper — wipes the in-memory fallback."""

    with _memory_lock:
        _memory_store.clear()


__all__ = ["save_extra", "load_extra", "clear_memory_store"]
