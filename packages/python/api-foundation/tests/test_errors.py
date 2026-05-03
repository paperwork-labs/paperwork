"""APIError classes and global exception wiring."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi import FastAPI, HTTPException
from starlette.requests import Request
from starlette.testclient import TestClient

from api_foundation.errors import (
    APIError,
    BadRequestError,
    ConflictError,
    ExternalServiceError,
    ForbiddenError,
    InternalError,
    NotFoundError,
    RateLimitedError,
    UnauthorizedError,
    register_exception_handlers,
)


@pytest.mark.parametrize(
    ("make_exc", "status", "code"),
    [
        (lambda: BadRequestError("bad"), 400, "BAD_REQUEST"),
        (lambda: UnauthorizedError("no"), 401, "UNAUTHORIZED"),
        (lambda: ForbiddenError("nope"), 403, "FORBIDDEN"),
        (lambda: NotFoundError("gone"), 404, "NOT_FOUND"),
        (lambda: ConflictError("dup"), 409, "CONFLICT"),
        (lambda: RateLimitedError("slow"), 429, "RATE_LIMITED"),
        (lambda: InternalError("ouch"), 500, "INTERNAL"),
        (lambda: ExternalServiceError("out"), 503, "EXTERNAL_SERVICE"),
    ],
)
def test_api_error_subclasses_envelope(
    make_exc: Callable[[], APIError],
    status: int,
    code: str,
) -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/t")
    async def _t() -> None:
        raise make_exc()

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/t")
    assert r.status_code == status
    body = r.json()
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str)
    assert body["error"]["message"]
    assert body["error"]["request_id"] is None


def test_register_exception_handlers_keeps_starlette_http_exception() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/hp")
    async def _hp() -> None:
        raise HTTPException(status_code=418, detail="short and stout")

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/hp")
    assert r.status_code == 418


def test_unhandled_exception_opaque_envelope(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def _boom() -> None:
        raise RuntimeError("classified")

    client = TestClient(app, raise_server_exceptions=False)
    with caplog.at_level("ERROR", logger="api_foundation.errors"):
        resp = client.get("/boom")
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == "INTERNAL"
    assert body["error"]["message"] == "An unexpected error occurred"
    assert body["error"]["request_id"] is None
    assert "classified" not in body["error"]["message"]
    assert any("unhandled_exception" in rec.getMessage() for rec in caplog.records)


def test_api_error_includes_request_id_from_state() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/with")
    async def _with(request: Request) -> None:
        request.state.request_id = "rid-123"
        raise NotFoundError("nope")

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/with")
    assert r.status_code == 404
    assert r.json()["error"]["request_id"] == "rid-123"
