"""OpenTelemetry metrics wrappers and service defaults."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from typing import Any, cast

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    InMemoryMetricReader,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource

_CONFIGURED = False

ObservableCallback = Callable[
    [metrics.CallbackOptions],
    Iterable[metrics.Observation],
]

http_requests_total: Counter | None = None
http_request_duration_ms: Histogram | None = None
db_query_duration_ms: Histogram | None = None


def _normalize_metrics_endpoint(url: str) -> str:
    trimmed = url.rstrip("/")
    if trimmed.endswith("/v1/metrics"):
        return trimmed
    return f"{trimmed}/v1/metrics"


class Counter:
    """Thin wrapper over ``meter.create_counter``."""

    def __init__(
        self,
        meter: metrics.Meter,
        name: str,
        description: str = "",
        unit: str = "1",
    ) -> None:
        self._counter = meter.create_counter(name, description=description, unit=unit)

    def add(self, amount: int, attributes: dict[str, Any] | None = None) -> None:
        self._counter.add(amount, attributes or {})


class Histogram:
    """Thin wrapper over ``meter.create_histogram``."""

    def __init__(
        self,
        meter: metrics.Meter,
        name: str,
        description: str = "",
        unit: str = "ms",
    ) -> None:
        self._histogram = meter.create_histogram(
            name,
            description=description,
            unit=unit,
        )

    def record(
        self,
        value: float | int,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        self._histogram.record(float(value), attributes or {})


class Gauge:
    """Thin wrapper over an asynchronous gauge observation (callback instrument)."""

    def __init__(
        self,
        meter: metrics.Meter,
        name: str,
        callbacks: Sequence[ObservableCallback],
        description: str = "",
        unit: str = "1",
    ) -> None:
        self._gauge = meter.create_observable_gauge(
            name,
            callbacks=cast(Any, list(callbacks)),
            description=description,
            unit=unit,
        )


def configure_metrics(
    service_name: str,
    otlp_endpoint: str | None = None,
) -> None:
    """Install a :class:`MeterProvider` and register default HTTP/DB instruments.

    Without ``otlp_endpoint``, metrics accumulate in-process via
    :class:`InMemoryMetricReader` (suitable for local dev / tests).
    """
    global _CONFIGURED
    global http_requests_total, http_request_duration_ms, db_query_duration_ms
    resource = Resource.create({"service.name": service_name})
    if otlp_endpoint:
        exporter = OTLPMetricExporter(
            endpoint=_normalize_metrics_endpoint(otlp_endpoint),
        )
        reader: InMemoryMetricReader | PeriodicExportingMetricReader = (
            PeriodicExportingMetricReader(exporter)
        )
    else:
        reader = InMemoryMetricReader()
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(provider)
    meter = metrics.get_meter(__name__, version="0.1.0", schema_url=None)
    http_requests_total = Counter(
        meter,
        "http_requests_total",
        "Total HTTP requests handled",
        "1",
    )
    http_request_duration_ms = Histogram(
        meter,
        "http_request_duration_ms",
        "HTTP request duration",
        "ms",
    )
    db_query_duration_ms = Histogram(
        meter,
        "db_query_duration_ms",
        "Database query duration",
        "ms",
    )
    _CONFIGURED = True


def _ensure_configured() -> None:
    if not _CONFIGURED:
        msg = "configure_metrics() must be called before using default instruments"
        raise RuntimeError(msg)


def get_http_requests_total() -> Counter:
    _ensure_configured()
    assert http_requests_total is not None
    return http_requests_total


def get_http_request_duration_ms() -> Histogram:
    _ensure_configured()
    assert http_request_duration_ms is not None
    return http_request_duration_ms


def get_db_query_duration_ms() -> Histogram:
    _ensure_configured()
    assert db_query_duration_ms is not None
    return db_query_duration_ms


__all__ = [
    "Counter",
    "Gauge",
    "Histogram",
    "ObservableCallback",
    "configure_metrics",
    "db_query_duration_ms",
    "get_db_query_duration_ms",
    "get_http_request_duration_ms",
    "get_http_requests_total",
    "http_request_duration_ms",
    "http_requests_total",
]
