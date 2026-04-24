"""OpenTelemetry tracing setup.

This module is the single place that touches the OTel SDK. Other backend
modules should call ``traced(...)`` (decorator) or ``get_tracer(...)`` and
remain agnostic of the underlying provider.

Configuration is environment-variable driven:

* ``OTEL_EXPORTER_OTLP_ENDPOINT`` — base URL of an OTLP/HTTP collector
  (Grafana Tempo, Honeycomb, Jaeger w/ OTLP receiver, etc). When unset,
  the SDK is still installed but no exporter is registered — spans are
  created and consumed by the no-op processor. This keeps dev runs fast
  and avoids a required external dependency.
* ``OTEL_EXPORTER_OTLP_HEADERS`` — comma-separated ``key=value`` pairs
  forwarded as HTTP headers (e.g. for Honeycomb auth).
* ``OTEL_SERVICE_NAME`` — overrides the ``service_name`` argument passed to
  :func:`init_tracing`.
* ``OTEL_TRACES_SAMPLER`` / ``OTEL_TRACES_SAMPLER_ARG`` — standard SDK
  sampler knobs (e.g. ``parentbased_traceidratio`` + ``0.1``).

Auto-instrumentations registered here cover FastAPI, SQLAlchemy 2.0,
Celery, httpx, and Redis. Each one is wrapped in its own try/except so a
missing optional dependency or instrumentation registration error never
breaks application startup.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Optional

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Tracer

logger = logging.getLogger(__name__)

_INIT_LOCK = threading.Lock()
_INITIALIZED = False
_TRACER_PROVIDER: Optional[TracerProvider] = None


def _build_resource(service_name: str, environment: str) -> Resource:
    """Build the OTel Resource describing this process."""
    attrs = {
        "service.name": os.getenv("OTEL_SERVICE_NAME", service_name),
        "deployment.environment": environment,
    }
    version = os.getenv("OTEL_SERVICE_VERSION") or os.getenv("RENDER_GIT_COMMIT")
    if version:
        attrs["service.version"] = version
    instance = os.getenv("HOSTNAME") or os.getenv("RENDER_INSTANCE_ID")
    if instance:
        attrs["service.instance.id"] = instance
    return Resource.create(attrs)


def _maybe_register_otlp_exporter(provider: TracerProvider) -> bool:
    """Register an OTLP/HTTP span exporter when configured.

    Returns True when a remote exporter was attached, False when no
    endpoint is configured. Failures are logged as WARN per
    ``no-silent-fallback.mdc`` — instrumentation still runs, but the user
    is told the trace pipeline is degraded.
    """
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    traces_endpoint = os.getenv(
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", ""
    ).strip()
    if not endpoint and not traces_endpoint:
        logger.info(
            "OTel tracing: no OTLP endpoint configured "
            "(OTEL_EXPORTER_OTLP_ENDPOINT unset); spans will be created but "
            "not exported. Set the env var to a Tempo/Honeycomb/Jaeger URL "
            "to enable remote export."
        )
        return False

    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        exporter = OTLPSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logger.info(
            "OTel tracing: OTLP/HTTP exporter registered (endpoint=%s)",
            traces_endpoint or endpoint,
        )
        return True
    except Exception as exc:
        logger.warning(
            "OTel tracing: failed to register OTLP exporter (%s); spans will "
            "be created but not exported. Check OTEL_EXPORTER_OTLP_ENDPOINT "
            "and OTEL_EXPORTER_OTLP_HEADERS.",
            exc,
            exc_info=True,
        )
        return False


def _instrument_fastapi(app: Optional[Any] = None) -> None:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        if app is not None:
            FastAPIInstrumentor.instrument_app(app)
        else:
            FastAPIInstrumentor().instrument()
    except Exception as exc:
        logger.warning("OTel: FastAPI auto-instrumentation failed: %s", exc)


def _instrument_sqlalchemy() -> None:
    try:
        from opentelemetry.instrumentation.sqlalchemy import (
            SQLAlchemyInstrumentor,
        )

        try:
            from app.database import engine as _engine
        except Exception:
            _engine = None

        if _engine is not None:
            SQLAlchemyInstrumentor().instrument(engine=_engine)
        else:
            SQLAlchemyInstrumentor().instrument()
    except Exception as exc:
        logger.warning("OTel: SQLAlchemy auto-instrumentation failed: %s", exc)


def _instrument_celery() -> None:
    try:
        from opentelemetry.instrumentation.celery import CeleryInstrumentor
        CeleryInstrumentor().instrument()
    except Exception as exc:
        logger.warning("OTel: Celery auto-instrumentation failed: %s", exc)


def _instrument_httpx() -> None:
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()
    except Exception as exc:
        logger.warning("OTel: httpx auto-instrumentation failed: %s", exc)


def _instrument_redis() -> None:
    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        RedisInstrumentor().instrument()
    except Exception as exc:
        logger.warning("OTel: redis auto-instrumentation failed: %s", exc)


def init_tracing(
    service_name: str,
    environment: str = "dev",
    *,
    fastapi_app: Optional[Any] = None,
    instrument_fastapi: bool = True,
    instrument_sqlalchemy: bool = True,
    instrument_celery: bool = True,
    instrument_httpx: bool = True,
    instrument_redis: bool = True,
) -> TracerProvider:
    """Idempotently install the global tracer provider and instrumentations.

    Safe to call multiple times: the second call is a no-op (returns the
    existing provider). This matters because Celery may import this module
    in both the parent process and forked children.

    Returns the active :class:`TracerProvider` so tests can register their
    own ``InMemorySpanExporter``.
    """
    global _INITIALIZED, _TRACER_PROVIDER

    with _INIT_LOCK:
        if _INITIALIZED and _TRACER_PROVIDER is not None:
            return _TRACER_PROVIDER

        resource = _build_resource(service_name, environment)
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)
        _TRACER_PROVIDER = provider

        _maybe_register_otlp_exporter(provider)

        if instrument_fastapi:
            _instrument_fastapi(fastapi_app)
        if instrument_sqlalchemy:
            _instrument_sqlalchemy()
        if instrument_celery:
            _instrument_celery()
        if instrument_httpx:
            _instrument_httpx()
        if instrument_redis:
            _instrument_redis()

        _INITIALIZED = True
        logger.info(
            "OTel tracing initialized (service=%s, environment=%s)",
            service_name,
            environment,
        )
        return provider


def get_tracer(name: str) -> Tracer:
    """Return a tracer bound to the global provider.

    Safe to call before :func:`init_tracing`; in that case the OTel API
    returns a proxy tracer that becomes live once the provider is set.
    """
    return trace.get_tracer(name)


def reset_for_tests() -> None:
    """Reset module state so tests can re-initialize cleanly.

    Also resets OpenTelemetry's process-wide tracer provider guard so
    :func:`trace.set_tracer_provider` can be used again in the same
    interpreter (the API normally allows only one successful set).

    DO NOT call from production code paths.
    """
    global _INITIALIZED, _TRACER_PROVIDER
    with _INIT_LOCK:
        try:
            current = trace.get_tracer_provider()
            # SDK provider only — avoid calling shutdown on the API proxy.
            if isinstance(current, TracerProvider):
                current.shutdown()
        except Exception as exc:
            logger.warning("reset_for_tests: tracer provider shutdown failed: %s", exc)

        _INITIALIZED = False
        _TRACER_PROVIDER = None

    # OpenTelemetry API allows set_tracer_provider only once unless we reset
    # its internal Once gate (see opentelemetry.trace._TRACER_PROVIDER_SET_ONCE).
    import opentelemetry.trace as ot_trace
    from opentelemetry.util._once import Once

    ot_trace._TRACER_PROVIDER = None
    ot_trace._TRACER_PROVIDER_SET_ONCE = Once()
