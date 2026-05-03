"""Integration tests for :class:`rate_limit.RateLimitMiddleware`."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

from rate_limit import RateLimitMiddleware, create_limiter


def test_middleware_429_includes_retry_after_header() -> None:
    limiter = create_limiter(
        default_limits=["2/minute"],
        headers_enabled=True,
    )
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limiter=limiter)

    @app.get("/hit")
    def hit(request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    client = TestClient(app)
    assert client.get("/hit").status_code == 200
    assert client.get("/hit").status_code == 200
    r = client.get("/hit")
    assert r.status_code == 429
    assert "retry-after" in {h.lower() for h in r.headers}


def test_middleware_disabled_limiter_bypasses() -> None:
    limiter = create_limiter(default_limits=["1/minute"])
    limiter.enabled = False
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limiter=limiter)

    @app.get("/free")
    def free(request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    client = TestClient(app)
    for _ in range(5):
        assert client.get("/free").status_code == 200
