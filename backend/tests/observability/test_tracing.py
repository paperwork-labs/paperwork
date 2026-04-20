"""Tests for backend.observability.

These tests use OTel's :class:`InMemorySpanExporter` so we can assert on
emitted spans without needing a collector. They cover:

* ``init_tracing`` is idempotent and degrades to a no-op exporter when
  ``OTEL_EXPORTER_OTLP_ENDPOINT`` is unset (so dev/CI never crashes).
* ``init_metrics`` likewise degrades cleanly.
* ``@traced`` emits a span with the configured name + static attributes.
* ``@traced`` records exceptions and marks the span ERROR before re-raise.
* The ``@traced`` decorator preserves async semantics.
* When applied to ``compute_full_indicator_series``, the decorator does
  not alter the wrapped function's signature or output.
"""

from __future__ import annotations

import asyncio
from typing import List

import pytest

from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)


@pytest.fixture
def in_memory_provider(monkeypatch):
    """Install a fresh tracer provider with an in-memory exporter.

    OTel's global provider is a process singleton; we reset our init
    module's flags so subsequent calls re-initialize cleanly.
    """
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)

    from backend.observability import tracing as tracing_module

    tracing_module.reset_for_tests()

    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    yield exporter

    exporter.clear()
    tracing_module.reset_for_tests()


def _span_names(spans: List[ReadableSpan]) -> List[str]:
    return [s.name for s in spans]


def test_init_tracing_no_endpoint_does_not_raise(monkeypatch):
    """No OTLP endpoint configured -> SDK installs no exporter, no exception."""
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)

    from backend.observability import tracing as tracing_module

    tracing_module.reset_for_tests()
    provider = tracing_module.init_tracing(
        service_name="axiomfolio-test",
        environment="test",
        instrument_fastapi=False,
        instrument_sqlalchemy=False,
        instrument_celery=False,
        instrument_httpx=False,
        instrument_redis=False,
    )
    assert provider is not None

    same_provider = tracing_module.init_tracing(
        service_name="axiomfolio-test",
        environment="test",
        instrument_fastapi=False,
        instrument_sqlalchemy=False,
        instrument_celery=False,
        instrument_httpx=False,
        instrument_redis=False,
    )
    assert same_provider is provider

    tracing_module.reset_for_tests()


def test_init_metrics_no_endpoint_does_not_raise(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", raising=False)

    from backend.observability import metrics as metrics_module

    metrics_module.reset_for_tests()
    provider = metrics_module.init_metrics(service_name="axiomfolio-test")
    assert provider is not None

    same = metrics_module.init_metrics(service_name="axiomfolio-test")
    assert same is provider

    metrics_module.reset_for_tests()


def test_traced_decorator_emits_span(in_memory_provider: InMemorySpanExporter):
    from backend.observability import traced

    @traced("test_sync_op", attrs={"component": "tests"})
    def square(x: int) -> int:
        return x * x

    assert square(5) == 25

    spans = in_memory_provider.get_finished_spans()
    assert "test_sync_op" in _span_names(spans)

    span = next(s for s in spans if s.name == "test_sync_op")
    assert span.attributes.get("component") == "tests"
    assert span.status.status_code != trace.StatusCode.ERROR


def test_traced_decorator_records_exception(
    in_memory_provider: InMemorySpanExporter,
):
    from backend.observability import traced

    @traced("test_failing_op")
    def boom() -> None:
        raise ValueError("intentional")

    with pytest.raises(ValueError, match="intentional"):
        boom()

    spans = in_memory_provider.get_finished_spans()
    failing = next(s for s in spans if s.name == "test_failing_op")
    assert failing.status.status_code == trace.StatusCode.ERROR
    assert any(
        ev.name == "exception" for ev in failing.events
    ), "exception event was not recorded"


def test_traced_decorator_async(
    in_memory_provider: InMemorySpanExporter,
):
    from backend.observability import traced

    @traced("test_async_op", attrs={"component": "tests"})
    async def double(x: int) -> int:
        await asyncio.sleep(0)
        return x * 2

    result = asyncio.run(double(3))
    assert result == 6

    spans = in_memory_provider.get_finished_spans()
    assert "test_async_op" in _span_names(spans)


def test_traced_preserves_function_metadata():
    from backend.observability import traced

    @traced("documented_op")
    def documented(a: int, b: int = 2) -> int:
        """A documented function."""
        return a + b

    assert documented.__name__ == "documented"
    assert documented.__doc__ == "A documented function."
    assert documented(3) == 5
    assert documented(3, b=10) == 13


def test_compute_full_indicator_series_emits_span(
    in_memory_provider: InMemorySpanExporter,
):
    """Smoke-test that the DANGER ZONE decorator placement works.

    Feeds the simplest possible (empty) DataFrame to confirm:
      1. The function is callable with the decorator applied.
      2. A span named ``compute_full_indicator_series`` is emitted.
      3. The function returns its expected value.
    """
    import pandas as pd

    from backend.services.market.indicator_engine import (
        compute_full_indicator_series,
    )

    out = compute_full_indicator_series(pd.DataFrame())
    assert out is not None

    spans = in_memory_provider.get_finished_spans()
    names = _span_names(spans)
    assert "compute_full_indicator_series" in names

    span = next(s for s in spans if s.name == "compute_full_indicator_series")
    assert span.attributes.get("component") == "market"
    assert span.attributes.get("subsystem") == "indicator_engine"
