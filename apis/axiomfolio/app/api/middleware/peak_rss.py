"""Per-request peak-RSS observability (Wave E / S2).

Wraps each HTTP request in ``tracemalloc`` + ``resource.getrusage`` so
we get two numbers per request:

* ``peak_rss_kb`` — delta of the OS high-water mark (``ru_maxrss``) over the
  request, normalized to KiB (Linux: raw in KiB, macOS: bytes/1024); see
  ``ru_maxrss_raw_to_kib``.
* ``tracemalloc_peak_bytes`` — Python-heap peak for the request (after
  ``tracemalloc.clear_traces`` at the start, ``get_traced_memory()[1]`` at the end).

We sample about 10% of requests (``SHA-256`` request id mod 10) to limit overhead.
Results go to Redis; ``get_hottest_endpoints_aggregated`` powers /admin/health.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import resource
import tracemalloc
from typing import Optional, Set

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import settings
from app.services.observability import peak_rss_store
from app.utils.request_context import get_request_id

logger = logging.getLogger(__name__)

_EXcluded_PATH_PREFIXES: tuple[str, ...] = ("/docs", "/redoc", "/openapi.json")
_EXcluded_EXACT: Set[str] = {"/health", "/favicon.ico"}


def _path_template_for_metrics(request: Request) -> str:
    route = request.scope.get("route")
    if route is not None and hasattr(route, "path"):
        return str(getattr(route, "path", "") or request.url.path)
    return request.url.path


def is_observability_bypass_path(path: str) -> bool:
    """True if we never sample (health probes, docs, admin health)."""
    if path in _EXcluded_EXACT:
        return True
    for p in _EXcluded_PATH_PREFIXES:
        if path.startswith(p) or path == p:
            return True
    if path == "/health" or path.startswith("/health/"):
        return True
    if "admin/health" in path:
        return True
    return False


def should_sample_for_request_id(request_id: str) -> bool:
    """About 10% of request ids, stable for a given id (not ``hash()`` / PYTHONHASHSEED)."""
    h = int.from_bytes(hashlib.sha256(request_id.encode("utf-8")).digest()[:4], "big")
    return (h % 10) == 0


def _get_user_id_for_log(request: Request) -> Optional[int]:
    st = getattr(request, "state", None)
    if st is None:
        return None
    u = getattr(st, "user_id", None)
    if isinstance(u, int):
        return u
    return None


class PeakRssMiddleware(BaseHTTPMiddleware):
    """10% sampled per-request ``ru_maxrss`` delta + ``tracemalloc`` peak; Redis write."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if not getattr(settings, "ENABLE_PEAK_RSS_MIDDLEWARE", True):
            return await call_next(request)

        path = request.url.path
        if is_observability_bypass_path(path):
            return await call_next(request)

        rid = get_request_id() or "-"
        if not should_sample_for_request_id(rid):
            return await call_next(request)

        tracemalloc.clear_traces()
        try:
            start_raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        except Exception as e:  # noqa: BLE001
            logger.warning("peak_rss: getrusage at start failed: %s", e, exc_info=True)
            return await call_next(request)

        response = await call_next(request)

        try:
            end_raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        except Exception as e:  # noqa: BLE001
            logger.warning("peak_rss: getrusage at end failed: %s", e, exc_info=True)
            return response

        _cur, tpeak = tracemalloc.get_traced_memory()
        del _cur

        start_kib = peak_rss_store.ru_maxrss_raw_to_kib(int(start_raw))
        end_kib = peak_rss_store.ru_maxrss_raw_to_kib(int(end_raw))
        delta_kib = max(0, end_kib - start_kib)

        path_t = _path_template_for_metrics(request)
        method = (request.method or "GET").upper()
        r = _get_sync_redis()
        if r is not None:
            def _write() -> None:
                peak_rss_store.record_peak_rss_sample(r, method, path_t, delta_kib)
            try:
                await asyncio.to_thread(_write)
            except Exception as e:  # noqa: BLE001
                logger.warning("peak_rss: async record failed: %s", e, exc_info=True)

        if delta_kib > peak_rss_store.PEAK_RSS_WARN_DELTA_KIB:
            uid = _get_user_id_for_log(request)
            logger.warning(
                "peak_rss: request delta peak RSS >500MiB: delta_kib=%d method=%s path=%s "
                "user_id=%s request_id=%s tracemalloc_peak_bytes=%d",
                delta_kib,
                method,
                path_t,
                uid,
                rid,
                int(tpeak),
            )

        return response


_redis_fail_open_logged: bool = False


def _get_sync_redis():
    if not getattr(settings, "ENABLE_PEAK_RSS_MIDDLEWARE", True):
        return None
    try:
        from app.services.silver.market.market_data_service import infra
        return infra.redis_client
    except Exception as e:  # noqa: BLE001
        global _redis_fail_open_logged
        if not _redis_fail_open_logged:
            logger.warning("peak_rss: could not get redis client: %s", e, exc_info=True)
            _redis_fail_open_logged = True
        return None
