"""Tracing tests."""

from __future__ import annotations

from unittest import mock

import pytest
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from observability.tracing import configure_tracing, trace_function


@pytest.fixture
def in_memory_tracing() -> InMemorySpanExporter:
    """Install a TracerProvider that records spans to memory."""
    exporter = InMemorySpanExporter()
    provider = trace.get_tracer_provider()
    shutdown = getattr(provider, "shutdown", None)
    if callable(shutdown):
        shutdown()
    resource = Resource.create({"service.name": "trace-test"})
    new_provider = TracerProvider(resource=resource)
    new_provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(new_provider)
    return exporter


@pytest.mark.asyncio
async def test_trace_function_sync_and_async(
    in_memory_tracing: InMemorySpanExporter,
) -> None:
    exporter = in_memory_tracing

    @trace_function()
    def add(a: int, b: int) -> int:
        return a + b

    assert add(2, 3) == 5
    sync_spans = exporter.get_finished_spans()
    assert len(sync_spans) == 1
    assert sync_spans[0].name.endswith("add")
    exporter.clear()

    @trace_function("async_op")
    async def double(x: int) -> int:
        return x * 2

    assert await double(4) == 8
    async_spans = exporter.get_finished_spans()
    assert len(async_spans) == 1
    assert async_spans[0].name == "async_op"


def test_configure_tracing_no_endpoint_is_tracer_provider() -> None:
    provider = trace.get_tracer_provider()
    shutdown = getattr(provider, "shutdown", None)
    if callable(shutdown):
        shutdown()
    configure_tracing("noop-svc", otlp_endpoint=None)
    assert isinstance(trace.get_tracer_provider(), TracerProvider)


def test_configure_tracing_with_endpoint_adds_processor() -> None:
    provider = trace.get_tracer_provider()
    shutdown = getattr(provider, "shutdown", None)
    if callable(shutdown):
        shutdown()
    with (
        mock.patch(
            "observability.tracing.BatchSpanProcessor",
            autospec=True,
        ) as bsp,
        mock.patch(
            "observability.tracing.OTLPSpanExporter",
            autospec=True,
        ),
    ):
        configure_tracing("exp-svc", otlp_endpoint="http://localhost:4318")
    bsp.assert_called_once()
