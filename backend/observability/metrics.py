"""OpenTelemetry metrics setup.

Mirrors :mod:`backend.observability.tracing`: one entry point
(:func:`init_metrics`) that installs the global meter provider and a thin
:func:`get_meter` accessor.  Configuration is the same OTLP env-var family
used for traces (``OTEL_EXPORTER_OTLP_ENDPOINT``,
``OTEL_EXPORTER_OTLP_METRICS_ENDPOINT``, ``OTEL_EXPORTER_OTLP_HEADERS``).

When no endpoint is configured the SDK is still installed but the
periodic exporter is omitted, so meters and instruments are usable
in-process without a collector. Per ``no-silent-fallback.mdc``, exporter
construction failures log a WARN and metrics still record locally.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Optional

from opentelemetry import metrics
from opentelemetry.metrics import Meter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

logger = logging.getLogger(__name__)

_INIT_LOCK = threading.Lock()
_INITIALIZED = False
_METER_PROVIDER: Optional[MeterProvider] = None


def _build_resource(service_name: str) -> Resource:
    attrs = {
        "service.name": os.getenv("OTEL_SERVICE_NAME", service_name),
    }
    version = os.getenv("OTEL_SERVICE_VERSION") or os.getenv("RENDER_GIT_COMMIT")
    if version:
        attrs["service.version"] = version
    return Resource.create(attrs)


def _build_metric_reader() -> Optional[PeriodicExportingMetricReader]:
    """Construct the periodic OTLP exporter, or None when unconfigured."""
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    metrics_endpoint = os.getenv(
        "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", ""
    ).strip()
    if not endpoint and not metrics_endpoint:
        logger.info(
            "OTel metrics: no OTLP endpoint configured; instruments are "
            "usable in-process but not exported."
        )
        return None

    try:
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
            OTLPMetricExporter,
        )

        exporter = OTLPMetricExporter()
        interval_ms = int(os.getenv("OTEL_METRIC_EXPORT_INTERVAL_MS", "60000"))
        return PeriodicExportingMetricReader(
            exporter,
            export_interval_millis=interval_ms,
        )
    except Exception as exc:
        logger.warning(
            "OTel metrics: failed to register OTLP exporter (%s); meters "
            "will record but not export.",
            exc,
            exc_info=True,
        )
        return None


def init_metrics(service_name: str) -> MeterProvider:
    """Idempotently install the global meter provider.

    Returns the active :class:`MeterProvider`. Tests may swap in their own
    in-memory readers via :func:`reset_for_tests`.
    """
    global _INITIALIZED, _METER_PROVIDER

    with _INIT_LOCK:
        if _INITIALIZED and _METER_PROVIDER is not None:
            return _METER_PROVIDER

        resource = _build_resource(service_name)
        reader = _build_metric_reader()
        readers = [reader] if reader is not None else []
        provider = MeterProvider(resource=resource, metric_readers=readers)
        metrics.set_meter_provider(provider)
        _METER_PROVIDER = provider
        _INITIALIZED = True
        logger.info(
            "OTel metrics initialized (service=%s, exporter=%s)",
            service_name,
            "otlp" if reader is not None else "none",
        )
        return provider


def get_meter(name: str) -> Meter:
    """Return a meter bound to the global provider."""
    return metrics.get_meter(name)


def reset_for_tests() -> None:
    """Reset module state so tests can re-initialize cleanly.

    DO NOT call from production code paths.
    """
    global _INITIALIZED, _METER_PROVIDER
    with _INIT_LOCK:
        _INITIALIZED = False
        _METER_PROVIDER = None
