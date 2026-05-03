"""Shared observability primitives: logging, tracing, metrics, FastAPI wiring."""

from __future__ import annotations

from observability.fastapi_integration import instrument_fastapi
from observability.logging import (
    StructuredJsonFormatter,
    configure_structured_logging,
    request_context,
    scrub_pii,
)
from observability.metrics import (
    Counter,
    Gauge,
    Histogram,
    configure_metrics,
    db_query_duration_ms,
    get_db_query_duration_ms,
    get_http_request_duration_ms,
    get_http_requests_total,
    http_request_duration_ms,
    http_requests_total,
)
from observability.tracing import configure_tracing, trace_function

__all__ = [
    "Counter",
    "Gauge",
    "Histogram",
    "StructuredJsonFormatter",
    "configure_metrics",
    "configure_structured_logging",
    "configure_tracing",
    "db_query_duration_ms",
    "get_db_query_duration_ms",
    "get_http_request_duration_ms",
    "get_http_requests_total",
    "http_request_duration_ms",
    "http_requests_total",
    "instrument_fastapi",
    "request_context",
    "scrub_pii",
    "trace_function",
]
