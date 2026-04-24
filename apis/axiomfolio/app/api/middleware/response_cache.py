"""Redis-backed HTTP response cache for authenticated GET hot paths."""

from __future__ import annotations

import functools
import hashlib
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.models.user import User
from app.services.market.market_data_service import infra

logger = logging.getLogger(__name__)

REDIS_BYPASS_COUNTER_KEY = "apiv1:resp_cache:redis_bypass_total"
_CACHE_KEY_PREFIX = "apiv1:resp_cache"

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def _inc_redis_bypass(reason: str) -> None:
    try:
        infra.redis_client.incr(REDIS_BYPASS_COUNTER_KEY)
    except Exception as e:
        logger.warning("response_cache: redis bypass counter failed (%s): %s", reason, e)


def _cache_key(user_id: int, request: Request) -> str:
    q = request.url.query.encode("utf-8")
    query_hash = hashlib.sha256(q).hexdigest()[:16]
    path = request.url.path
    return f"{_CACHE_KEY_PREFIX}:{user_id}:{path}:{query_hash}"


def _find_user(kwargs: dict[str, Any]) -> User | None:
    for v in kwargs.values():
        if isinstance(v, User):
            return v
    return None


def _json_default(o: Any) -> str:
    return str(o)


def redis_response_cache(*, ttl_seconds: int = 30) -> Callable[[F], F]:
    """Cache successful JSON dict responses for identical user + path + query.

    Skips caching when ``request`` is missing, user cannot be resolved, Redis
    errors (degrades open; increments ``apiv1:resp_cache:redis_bypass_total``),
    or the handler returns a non-dict/non-list body.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            request: Request | None = kwargs.get("request")
            user = _find_user(kwargs)
            if request is None or user is None:
                return await func(*args, **kwargs)

            key = _cache_key(user.id, request)
            try:
                raw = infra.redis_client.get(key)
                if raw:
                    if isinstance(raw, (bytes, bytearray)):
                        raw = raw.decode("utf-8")
                    payload = json.loads(raw)
                    return JSONResponse(content=payload)
            except Exception as e:
                logger.warning("response_cache: read failed key=%s: %s", key, e)
                _inc_redis_bypass("read_error")

            result = await func(*args, **kwargs)
            if isinstance(result, Response):
                return result
            if isinstance(result, (dict, list)):
                try:
                    infra.redis_client.setex(
                        key,
                        ttl_seconds,
                        json.dumps(result, default=_json_default),
                    )
                except Exception as e:
                    logger.warning("response_cache: write failed key=%s: %s", key, e)
                    _inc_redis_bypass("write_error")
            return result

        return wrapper  # type: ignore[return-value]

    return decorator
