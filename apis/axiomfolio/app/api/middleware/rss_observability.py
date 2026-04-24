"""Per-request process max RSS delta observability (fail-open, Redis-backed)."""

from __future__ import annotations

import asyncio
import logging
import resource
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import settings
from app.services.observability.rss_store import maxrss_to_bytes, record_request_rss_peak

logger = logging.getLogger(__name__)

_redis_fail_open_logged: bool = False


def _path_template_for_metrics(request: Request) -> str:
    route = request.scope.get("route")
    if route is not None and hasattr(route, "path"):
        return str(getattr(route, "path", "") or request.url.path)
    return request.url.path


def _get_sync_redis():
    if not settings.ENABLE_RSS_OBSERVABILITY:
        return None
    try:
        from app.services.market.market_data_service import infra

        return infra.redis_client
    except Exception as e:
        global _redis_fail_open_logged
        if not _redis_fail_open_logged:
            logger.warning("rss observability: could not get redis client: %s", e, exc_info=True)
            _redis_fail_open_logged = True
        return None


class RssObservabilityMiddleware(BaseHTTPMiddleware):
    """Record peak RSS delta (``ru_maxrss``) per request into Redis (UTC hour keys)."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if not settings.ENABLE_RSS_OBSERVABILITY:
            return await call_next(request)

        try:
            start_raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            start_b = maxrss_to_bytes(int(start_raw))
        except Exception as e:
            logger.warning("rss observability: getrusage at start failed: %s", e, exc_info=True)
            return await call_next(request)

        response = await call_next(request)

        try:
            end_raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            end_b = maxrss_to_bytes(int(end_raw))
        except Exception as e:
            logger.warning("rss observability: getrusage at end failed: %s", e, exc_info=True)
            return response

        path = _path_template_for_metrics(request)
        method = (request.method or "GET").upper()
        r = _get_sync_redis()
        if r is None:
            return response

        def _write() -> None:
            record_request_rss_peak(r, method, path, start_b, end_b)

        try:
            await asyncio.to_thread(_write)
        except Exception as e:
            logger.warning("rss observability: async record failed: %s", e, exc_info=True)
        return response
