# observability

Shared **structured logging**, **OpenTelemetry tracing/metrics**, and **FastAPI** instrumentation for Paperwork Python services.

## Public API

### Logging (`observability.logging`)

- **`configure_structured_logging(service_name, log_level="INFO", *, extra_fields=None)`** — Installs a single root `StreamHandler` with `python-json-logger` (no `basicConfig`). Every log line is JSON with:
  - `timestamp` (RFC3339 UTC, millisecond precision)
  - `level`, `message`, `service_name`
  - `request_id`, `user_id` (from contextvars; `null` when unset)
  - Optional static `extra_fields` merged on every record
  - Per-message **PII scrubbing** on `message` (emails, SSN-like patterns, US phone-like patterns)
- **`request_context`**: `set_request_id`, `set_user_id`, `reset_request_id`, `reset_user_id` — async-safe **contextvars** (not thread-locals).
- **`StructuredJsonFormatter`**, **`scrub_pii`**

### Tracing (`observability.tracing`)

- **`configure_tracing(service_name, otlp_endpoint=None)`** — `TracerProvider` with `service.name` resource. If `otlp_endpoint` is set (base URL or full `/v1/traces` path), attaches OTLP/HTTP export via `BatchSpanProcessor`. Otherwise no remote exporter (local/dev).
- **`trace_function(name=None)`** — decorator for sync/async functions; wraps body in a span.

### Metrics (`observability.metrics`)

- **`configure_metrics(service_name, otlp_endpoint=None)`** — `MeterProvider` with OTLP/HTTP **or** in-memory reader (no export) when `otlp_endpoint` is omitted.
- Thin types: **`Counter`**, **`Histogram`**, **`Gauge`**
- After `configure_metrics`, module-level defaults (**`http_requests_total`**, **`http_request_duration_ms`**, **`db_query_duration_ms`**) and **`get_*`** accessors are available.

### FastAPI (`observability.fastapi_integration`)

- **`instrument_fastapi(app, *, service_name, configure_logging=True)`**
  - Registers OpenTelemetry FastAPI instrumentation.
  - Adds middleware: reads **`X-Request-ID`** (or generates UUID), binds `request_context`, copies **`request.state.user_id`** into logs (stringified), emits structured start/finish logs, increments **`http_requests_total`**, observes **`http_request_duration_ms`**, echoes **`X-Request-ID`** on responses.
  - **Requires** `configure_metrics(...)` first so counters/histograms exist.
  - Set `configure_logging=False` when installing your own root handlers (e.g. tests).

## Defaults: what we log / trace / measure

| Area | Default behavior |
|------|------------------|
| **Logs** | JSON lines; scrubbed `message`; `request_id` / `user_id` when middleware or your code sets them |
| **Traces** | FastAPI routes instrumented; manual spans via `trace_function` |
| **Metrics** | `http_requests_total` (labels: `http_method`, `http_route`, `http_status_code`), `http_request_duration_ms` (ms), `db_query_duration_ms` (for you to record from DB code) |

## Adoption checklist

1. Add the workspace dependency (path or published wheel) to your backend.
2. At startup: `configure_structured_logging("your-service")` **or** rely on `instrument_fastapi(..., service_name=...)` (default `configure_logging=True`).
3. Call `configure_tracing("your-service", os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"))` when you want traces (endpoint optional).
4. Call `configure_metrics("your-service", os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"))` before `instrument_fastapi` (FastAPI path).
5. In auth middleware / dependencies, set `request.state.user_id` so logs include it.
6. From DB helpers, call `get_db_query_duration_ms().record(latency_ms, {"query": "users_by_id"})` (keep labels low-cardinality).

## Development

```bash
cd packages/python/observability
uv sync --all-extras
uv run ruff check src tests
uv run mypy src/observability
uv run pytest
```
