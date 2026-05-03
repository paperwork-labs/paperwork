"""Metrics wrapper tests."""

from __future__ import annotations

from opentelemetry import metrics

from observability.metrics import (
    Counter,
    Gauge,
    Histogram,
    configure_metrics,
    get_db_query_duration_ms,
    get_http_request_duration_ms,
    get_http_requests_total,
)


def test_configure_metrics_exposes_defaults() -> None:
    configure_metrics("metrics-svc", otlp_endpoint=None)
    assert get_http_requests_total() is not None
    assert get_http_request_duration_ms() is not None
    assert get_db_query_duration_ms() is not None


def test_counter_add() -> None:
    configure_metrics("c-svc", otlp_endpoint=None)
    ctr = get_http_requests_total()
    ctr.add(1, {"http_method": "GET", "http_route": "/", "http_status_code": "200"})
    ctr.add(
        2,
        {
            "http_method": "POST",
            "http_route": "/hook",
            "http_status_code": "201",
        },
    )


def test_histogram_record() -> None:
    configure_metrics("h-svc", otlp_endpoint=None)
    hist = get_http_request_duration_ms()
    hist.record(4.2, {"db": "primary"})
    hist.record(90, None)


def test_thin_counter_histogram_gauge() -> None:
    configure_metrics("thin", otlp_endpoint=None)
    meter = metrics.get_meter("manual")

    thin_ctr = Counter(meter, "custom_total", "desc", "1")
    thin_ctr.add(1, {"x": "y"})

    thin_hist = Histogram(meter, "custom_ms", "latency", "ms")
    thin_hist.record(1.0)

    def observe(
        options: metrics.CallbackOptions,
    ) -> metrics.Observation | None:
        _ = options
        yield metrics.Observation(7, {"pool": "main"})

    g = Gauge(meter, "custom_g", [observe], "queue depth", "1")
    assert g._gauge is not None
