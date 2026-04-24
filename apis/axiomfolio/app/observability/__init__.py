"""OpenTelemetry instrumentation for AxiomFolio.

Pure observability: no behavior changes. The public surface is intentionally
small so callers don't reach into the SDK directly.

Typical usage from process bootstrap (FastAPI startup or Celery worker init):

    from app.observability import init_tracing, init_metrics

    init_tracing(service_name="axiomfolio-api", environment=settings.ENVIRONMENT)
    init_metrics(service_name="axiomfolio-api")

Hot-path instrumentation:

    from app.observability import traced

    @traced("recompute_universe", attrs={"component": "market"})
    def recompute_universe(...):
        ...

If ``OTEL_EXPORTER_OTLP_ENDPOINT`` is unset, exporters degrade to a no-op
(logged at INFO once on init) so dev runs do not require a collector. Per
``no-silent-fallback.mdc`` any exporter construction failure logs a WARNING
and instrumentation still reports a span — just without remote export.
"""

from app.observability.metrics import init_metrics, get_meter
from app.observability.span_decorators import traced
from app.observability.tracing import init_tracing, get_tracer

__all__ = [
    "init_tracing",
    "init_metrics",
    "traced",
    "get_tracer",
    "get_meter",
]
