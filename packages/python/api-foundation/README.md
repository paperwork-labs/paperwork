# api-foundation

Shared FastAPI primitives for Paperwork Labs HTTP backends: correlation IDs, structured JSON access logs (`python-json-logger`), typed `APIError` wiring, response envelopes, and `/healthz` + `/readyz` probes.

Requires Python **3.11+**.

## Install

```bash
pip install api-foundation
```

Editable from this directory:

```bash
pip install -e ".[dev]"
```

## Public API

| Surface | Purpose |
|---------|---------|
| `RequestIDMiddleware` | Accept or generate `x-request-id`; store on `request.state.request_id`; echo on response |
| `LoggingMiddleware` | Structured access logs: `method`, `path`, `status`, `latency_ms`, `request_id`, optional `user_id` / `org_id` on state |
| `setup_access_json_logging()` | Attach stderr `JsonFormatter` to logger `api_foundation.access` (idempotent helper) |
| `STATE_REQUEST_ID`, `STATE_USER_ID`, `STATE_ORG_ID`, `REQUEST_ID_HEADER` | Convention constants |
| `APIError`, concrete errors | Controlled HTTP failures with stable `error_code` |
| `register_exception_handlers(app)` | JSON error envelopes plus opaque 500s; failures logged before response |
| `success_response`, `error_response` | Uniform JSON envelopes (`success` + `data` / `error`) |
| `register_healthcheck(app, check_db=…, check_redis=…)` | `GET /healthz` process liveness; `GET /readyz` probes |

Unhandled exceptions return `"message": "An unexpected error occurred"` on the wire; details go to structured logs only.

## Adoption checklist

1. Align pins with `fastapi`, `pydantic`, `python-json-logger` in this package's `pyproject.toml`.
2. Middleware: add `LoggingMiddleware` first, then `RequestIDMiddleware` (last-added runs first inbound, so request ids exist before access logs — same layering idea as middleware comments in `apis/axiomfolio/app/api/main.py`).
3. Call `setup_access_json_logging()` at startup **or** configure `api_foundation.access` in logging `dictConfig` with `pythonjsonlogger.json.JsonFormatter`.
4. Populate `request.state.user_id` and `request.state.org_id` from auth dependencies so access logs enrich automatically.
5. Call `register_exception_handlers(app)` once after app creation.
6. Use `register_healthcheck` with synchronous `callable() -> bool` checks; unchecked probes may be omitted (`None` skips).

## Known backend duplication this package will eventually replace

- **AxiomFolio**: inline `@app.middleware("http")` request id middleware in `apis/axiomfolio/app/api/main.py`.
- **`/health` routers** across Brain, FileFree, LaunchFree, AxiomFolio — vary by path/shape versus standardized `/healthz` + `/readyz` adopted from this foundation.
- Ad hoc JSON error payloads and leaky 500 messages — converge on `register_exception_handlers` when backends migrate.

## Development

```bash
ruff check src tests && ruff format src tests && mypy src/api_foundation tests
pytest tests/ --cov=api_foundation --cov-fail-under=85
```

## Plan reference

Brain / platform architecture notes: [`docs/BRAIN_ARCHITECTURE.md`](../../docs/BRAIN_ARCHITECTURE.md). Wave **K4** introduces this extract-only package.
