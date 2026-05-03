"""FastAPI: OpenTelemetry instrumentation + request-scoped structured logging."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Response
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse

from observability.logging import configure_structured_logging, request_context
from observability.metrics import get_http_request_duration_ms, get_http_requests_total

_LOG = logging.getLogger("observability.fastapi")


def _normalize_path(request: StarletteRequest) -> str:
    route = request.scope.get("route")
    if route and getattr(route, "path", None):
        return str(route.path)
    return request.url.path


class _ObservabilityLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: StarletteRequest,
        call_next: RequestResponseEndpoint,
    ) -> StarletteResponse:
        incoming = request.headers.get("x-request-id") or request.headers.get(
            "X-Request-ID",
        )
        request_id = incoming or str(uuid.uuid4())
        request.state.observability_request_id = request_id

        rid_token = request_context.set_request_id(request_id)
        user_raw = getattr(request.state, "user_id", None)
        user_str = str(user_raw) if user_raw is not None else None
        uid_token = request_context.set_user_id(user_str)

        path_start = _normalize_path(request)
        start = time.perf_counter()
        _LOG.info(
            "http_request_started",
            extra={"http_method": request.method, "http_path": path_start},
        )
        counter = get_http_requests_total()
        histogram = get_http_request_duration_ms()
        status_code = 500
        response: StarletteResponse | None = None
        try:
            response = await call_next(request)
            status_code = response.status_code
        except BaseException:
            status_code = 500
            raise
        finally:
            path_done = _normalize_path(request)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            attrs = {
                "http_method": request.method,
                "http_route": path_done,
                "http_status_code": str(status_code),
            }
            counter.add(1, attrs)
            histogram.record(elapsed_ms, attrs)
            late_user = getattr(request.state, "user_id", None)
            late_uid_str = str(late_user) if late_user is not None else None
            user_finish_token = request_context.set_user_id(late_uid_str)
            try:
                _LOG.info(
                    "http_request_finished",
                    extra={
                        "http_method": request.method,
                        "http_path": path_done,
                        "http_status_code": status_code,
                        "duration_ms": round(elapsed_ms, 3),
                    },
                )
            finally:
                request_context.reset_user_id(user_finish_token)
            request_context.reset_request_id(rid_token)
            request_context.reset_user_id(uid_token)

        assert response is not None
        if isinstance(response, Response):
            response.headers.setdefault("X-Request-ID", request_id)
        return response


def instrument_fastapi(
    app: FastAPI,
    *,
    service_name: str,
    configure_logging: bool = True,
) -> None:
    """Configure JSON logging, OTEL FastAPI spans, and request logging middleware.

    **Requires** :func:`observability.metrics.configure_metrics` to have been called
    so HTTP counters/histograms can be updated from the middleware.

    Set ``configure_logging=False`` when tests (or callers) install their own root
    handlers — the middleware still emits structured records.
    """
    if configure_logging:
        configure_structured_logging(service_name)
    FastAPIInstrumentor.instrument_app(app)
    app.add_middleware(_ObservabilityLoggingMiddleware)


__all__ = ["instrument_fastapi"]
