"""Tests for :func:`rate_limit.create_limiter` and Redis fail-open storage."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient
from slowapi.util import get_remote_address

from rate_limit import RateLimitMiddleware, create_limiter
from rate_limit.keys import get_org_id_key, get_remote_address_key, get_user_id_key
from rate_limit.storage_failopen import FailOpenRedisStorage


@pytest.fixture
def clock() -> MagicMock:
    return MagicMock(return_value=datetime(2026, 5, 3, 12, 0, 0, tzinfo=UTC))


def test_default_key_prefers_user_id_from_state() -> None:
    limiter = create_limiter(default_limits=["10/minute"])
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limiter=limiter)

    @app.get("/u")
    def u(request: Request) -> PlainTextResponse:
        request.state.user_id = "uid-42"
        return PlainTextResponse("ok")

    client = TestClient(app)
    assert client.get("/u").status_code == 200


def test_under_limit_memory() -> None:
    limiter = create_limiter(default_limits=["10/minute"])
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limiter=limiter)

    @app.get("/")
    def root(request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    client = TestClient(app)
    for _ in range(5):
        r = client.get("/")
        assert r.status_code == 200


def test_at_limit_boundary_memory() -> None:
    limiter = create_limiter(default_limits=["3/minute"])
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limiter=limiter)

    @app.get("/")
    def root(request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert client.get("/").status_code == 200
    assert client.get("/").status_code == 200


def test_over_limit_memory() -> None:
    limiter = create_limiter(default_limits=["2/minute"])
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limiter=limiter)

    @app.get("/")
    def root(request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert client.get("/").status_code == 200
    assert client.get("/").status_code == 429


def test_redis_outage_fail_open_records_degradation(
    monkeypatch: pytest.MonkeyPatch, clock: MagicMock
) -> None:
    limiter = create_limiter(
        redis_url="redis://127.0.0.1:6379/0",
        default_limits=["2/minute"],
        clock=clock,
    )
    storage = limiter._storage
    assert isinstance(storage, FailOpenRedisStorage)

    def broken_incr(*_a: object, **_k: object) -> int:
        raise ConnectionError("redis simulated down")

    monkeypatch.setattr(storage._inner, "incr", broken_incr)
    monkeypatch.setattr(storage._inner, "get", lambda *_a, **_k: 0)
    monkeypatch.setattr(storage._inner, "get_expiry", lambda *_a, **_k: 1e9)

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limiter=limiter)

    @app.get("/")
    def root(request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert client.get("/").status_code == 200
    snap = limiter.degradation_snapshot()
    assert snap["count"] >= 1
    assert snap["last_error"] is not None
    assert "redis simulated down" in snap["last_error"]
    assert snap["last_at"] is not None


def test_custom_key_func_per_user_isolation() -> None:
    def key_func(request: Request) -> str:
        return str(getattr(request.state, "tenant", "x"))

    limiter = create_limiter(
        default_limits=["1/minute"],
        key_func=key_func,
    )
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limiter=limiter)

    @app.get("/{tenant}")
    def root(request: Request, tenant: str) -> PlainTextResponse:
        request.state.tenant = tenant
        return PlainTextResponse("ok")

    client = TestClient(app)
    assert client.get("/a").status_code == 200
    assert client.get("/a").status_code == 429
    assert client.get("/b").status_code == 200


def test_get_user_id_key_prefers_user() -> None:
    app = FastAPI()

    @app.get("/q")
    def q(request: Request) -> PlainTextResponse:
        request.state.user_id = 99
        assert get_user_id_key(request) == "99"
        return PlainTextResponse("ok")

    client = TestClient(app)
    client.get("/q")


def test_get_user_id_key_fallback_ip() -> None:
    app = FastAPI()

    @app.get("/")
    def root(request: Request) -> PlainTextResponse:
        k = get_user_id_key(request)
        assert k == get_remote_address(request)
        return PlainTextResponse(k)

    client = TestClient(app)
    client.get("/")


def test_get_org_id_key_prefers_org() -> None:
    app = FastAPI()

    @app.get("/o")
    def o(request: Request) -> PlainTextResponse:
        request.state.org_id = "org-9"
        assert get_org_id_key(request) == "org-9"
        return PlainTextResponse("ok")

    client = TestClient(app)
    client.get("/o")


def test_get_org_id_key_fallback_ip() -> None:
    app = FastAPI()

    @app.get("/p")
    def p(request: Request) -> PlainTextResponse:
        assert get_org_id_key(request) == get_remote_address(request)
        return PlainTextResponse("ok")

    client = TestClient(app)
    client.get("/p")


def test_get_remote_address_key() -> None:
    app = FastAPI()

    @app.get("/r")
    def r(request: Request) -> PlainTextResponse:
        assert get_remote_address_key(request) == get_remote_address(request)
        return PlainTextResponse("ok")

    client = TestClient(app)
    client.get("/r")


def test_degradation_snapshot_is_copy() -> None:
    limiter = create_limiter(redis_url="redis://127.0.0.1:6379/0")
    snap = limiter.degradation_snapshot()
    snap["count"] = 999
    assert limiter.degradation_snapshot()["count"] == 0


def test_to_failopen_uri_rediss() -> None:
    from rate_limit.storage_failopen import _to_failopen_uri

    assert _to_failopen_uri("rediss://example:6380/1").startswith("failopen-rediss://")


def test_to_failopen_uri_errors() -> None:
    from rate_limit.storage_failopen import _to_failopen_uri

    with pytest.raises(ValueError, match="redis://"):
        _to_failopen_uri("memcached://localhost")
