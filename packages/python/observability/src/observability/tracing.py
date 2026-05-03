"""OpenTelemetry tracing helpers."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import ParamSpec, TypeVar, cast

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

P = ParamSpec("P")
R = TypeVar("R")


def _normalize_traces_endpoint(url: str) -> str:
    trimmed = url.rstrip("/")
    if trimmed.endswith("/v1/traces"):
        return trimmed
    return f"{trimmed}/v1/traces"


def configure_tracing(
    service_name: str,
    otlp_endpoint: str | None = None,
) -> None:
    """Install a :class:`TracerProvider`.

    When ``otlp_endpoint`` is set, spans are exported via OTLP/HTTP.
    Otherwise spans are recorded locally only (no exporter attached).
    """
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    if otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=_normalize_traces_endpoint(otlp_endpoint))
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


def trace_function(
    name: str | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator that wraps the callable in an OpenTelemetry span (sync or async)."""

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        span_name = name or fn.__qualname__
        tracer = trace.get_tracer(fn.__module__)

        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                with tracer.start_as_current_span(span_name):
                    result = await fn(*args, **kwargs)
                return cast(R, result)

            return cast(Callable[P, R], async_wrapper)

        @functools.wraps(fn)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with tracer.start_as_current_span(span_name):
                return fn(*args, **kwargs)

        return cast(Callable[P, R], sync_wrapper)

    return decorator


__all__ = ["configure_tracing", "trace_function"]
