"""HTTP middleware for request correlation and structured access logging."""

from __future__ import annotations

import logging
import sys
import time
import uuid

from pythonjsonlogger.json import JsonFormatter
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "x-request-id"
STATE_REQUEST_ID = "request_id"
STATE_USER_ID = "user_id"
STATE_ORG_ID = "org_id"

ACCESS_LOGGER_NAME = "api_foundation.access"


def setup_access_json_logging(*, level: int = logging.INFO) -> logging.Logger:
    """Attach a stderr :class:`JsonFormatter` to the access logger (idempotent).

    Backends that already configure ``api_foundation.access`` via ``dictConfig``
    can skip this; it exists so a plain ``LoggingMiddleware`` install yields JSON
    lines without extra boilerplate.

    Uses :mod:`pythonjson-logger` for structured output — no ``print``.
    """

    lg = logging.getLogger(ACCESS_LOGGER_NAME)
    if not lg.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JsonFormatter())
        lg.addHandler(handler)
    lg.setLevel(level)
    lg.propagate = False
    return lg


def _get_request_id(request: Request) -> str | None:
    return getattr(request.state, STATE_REQUEST_ID, None)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Propagates ``X-Request-Id``: accept client value or generate UUID.

    The resolved id is stored on ``request.state.request_id`` and echoed on the
    response. Middleware that needs the id (for example :class:`LoggingMiddleware`)
    should sit **inside** this one in the stack so they see populated state.

    Recommendation: register request-id middleware early (outer layers in
    Starlette prepend order) so downstream observability stacks see a stable id,
    mirroring backends that expose request correlation before heavier middleware.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        raw = request.headers.get(REQUEST_ID_HEADER)
        request_id = (
            raw.strip() if raw is not None and raw.strip() else str(uuid.uuid4())
        )
        setattr(request.state, STATE_REQUEST_ID, request_id)

        try:
            response = await call_next(request)
        except Exception:
            _logger.exception(
                "Request pipeline escaped with exception "
                "(request_id=%s path=%s)",
                request_id,
                request.url.path,
            )
            raise
        response.headers.setdefault(REQUEST_ID_HEADER, request_id)
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Structured per-request access log via :mod:`pythonjson-logger` extras.

    Emits JSON lines (when :func:`setup_access_json_logging` is used, or when
    the host configures the same formatter) including:

    ``method``, ``path``, ``status``, ``latency_ms``, ``request_id``, optional
    ``user_id``, ``org_id`` from ``request.state`` if set by auth deps.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        setup_access_json_logging()
        started = time.perf_counter()
        access = logging.getLogger(ACCESS_LOGGER_NAME)

        status: int | None = None
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            access.error(
                "request_pipeline_error",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": None,
                    "latency_ms": round(elapsed_ms, 3),
                    "request_id": _get_request_id(request),
                    "user_id": getattr(request.state, STATE_USER_ID, None),
                    "org_id": getattr(request.state, STATE_ORG_ID, None),
                },
                exc_info=exc,
            )
            raise exc from exc

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        access.info(
            "http_request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": status,
                "latency_ms": round(elapsed_ms, 3),
                "request_id": _get_request_id(request),
                "user_id": getattr(request.state, STATE_USER_ID, None),
                "org_id": getattr(request.state, STATE_ORG_ID, None),
            },
        )
        return response
