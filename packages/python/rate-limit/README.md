# `rate-limit`

Shared SlowAPI-based rate limiting for Paperwork Labs Python services: global
default limits, optional Redis-backed counters, **intentional fail-OPEN** on
Redis errors with a `degradation_snapshot` compatible with
`mcp_server.quota.DailyCallQuota`, and ASGI middleware for FastAPI.

## Public API

| Symbol | Role |
|--------|------|
| `create_limiter` | Build a `PaperworkLimiter` (SlowAPI `Limiter`) with memory or fail-open Redis storage |
| `PaperworkLimiter` | Subclass adding `degradation_snapshot()` |
| `RateLimitMiddleware` | ASGI wrapper that sets `app.state.limiter` and delegates to SlowAPI |
| `_rate_limit_exceeded_handler` | Re-exported SlowAPI 429 handler (JSON body + headers) |
| `get_user_id_key` / `get_org_id_key` / `get_remote_address_key` | Pre-built key extractors |
| `FailOpenRedisStorage` | Custom `limits` storage (`failopen-redis://` schemes) |

## Why fail-OPEN (and not fail-CLOSED)

If rate limiting treated Redis as a hard dependency, a Redis outage would
**deny all traffic** (fail-closed) even though your app could otherwise serve
read-heavy or degraded-mode responses. That turns an infrastructure blip into a
full product outage.

This package **allows requests** when Redis errors occur, logs a warning, and
increments `degradation_snapshot` counters so health endpoints can surface the
outage—matching the rationale in
`packages/python/mcp-server/src/mcp_server/quota.py`. That behavior is
**explicit and observable**, not a silent fallback.

## FastAPI example

```python
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

from rate_limit import RateLimitMiddleware, create_limiter

limiter = create_limiter(redis_url="redis://localhost:6379/0")

app = FastAPI()
app.add_middleware(RateLimitMiddleware, limiter=limiter)


@app.get("/health/deps")
def deps():
    return {"rate_limit_degraded": limiter.degradation_snapshot()}


@app.get("/")
def root(request: Request):
    request.state.user_id = "user-123"
    return PlainTextResponse("ok")
```

Use `create_limiter(redis_url=None)` for tests or local dev (in-memory
storage; no degradation path).

## Development

```bash
cd packages/python/rate-limit
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"
ruff check src tests
mypy src
pytest --cov=rate_limit --cov-report=term-missing
```

Coverage gate: **>80%** (configured in `pyproject.toml`).
