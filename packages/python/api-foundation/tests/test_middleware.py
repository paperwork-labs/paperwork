"""RequestIDMiddleware and LoggingMiddleware integration tests."""

from __future__ import annotations

import json
import logging
from io import StringIO

from fastapi import FastAPI, Request
from pythonjsonlogger.json import JsonFormatter
from starlette.testclient import TestClient

from api_foundation.middleware import (
    ACCESS_LOGGER_NAME,
    REQUEST_ID_HEADER,
    LoggingMiddleware,
    RequestIDMiddleware,
)


def _access_stream_with_json() -> StringIO:
    stream = StringIO()
    lg = logging.getLogger(ACCESS_LOGGER_NAME)
    lg.handlers.clear()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    lg.addHandler(handler)
    lg.propagate = False
    lg.setLevel(logging.INFO)
    return stream


def test_request_id_preserves_custom_header_roundtrip() -> None:
    _access_stream_with_json()
    raw = "cafef00d-cafe-cafe-cafe-cafe00000001"
    app = FastAPI()
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/who")
    async def who(req: Request) -> dict[str, str | None]:
        return {"rid": getattr(req.state, "request_id", None)}

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/who", headers={REQUEST_ID_HEADER: raw})
    assert r.status_code == 200
    assert r.headers[REQUEST_ID_HEADER] == raw
    assert r.json() == {"rid": raw}


def test_request_id_generates_uuid_when_header_missing() -> None:
    _access_stream_with_json()
    app = FastAPI()
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/who")
    async def who(req: Request) -> dict[str, str | None]:
        return {"rid": getattr(req.state, "request_id", None)}

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/who")
    assert r.status_code == 200
    rid = r.headers[REQUEST_ID_HEADER]
    assert r.json() == {"rid": rid}
    assert len(rid) == 36


def test_logging_middleware_emits_json_with_required_fields() -> None:
    stream = _access_stream_with_json()
    app = FastAPI()
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/x")
    async def x(request: Request) -> dict[str, str]:
        request.state.user_id = "u-1"
        request.state.org_id = "o-9"
        return {"ok": "y"}

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/x")
    assert r.status_code == 200
    rid = r.headers[REQUEST_ID_HEADER]
    line = stream.getvalue().strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["method"] == "GET"
    assert payload["path"] == "/x"
    assert payload["status"] == 200
    assert "latency_ms" in payload
    assert isinstance(payload["latency_ms"], int | float)
    assert payload["request_id"] == rid
    assert payload["user_id"] == "u-1"
    assert payload["org_id"] == "o-9"


def test_logging_middleware_logs_and_reraises_on_pipeline_error() -> None:
    stream = _access_stream_with_json()
    app = FastAPI()
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/boom")
    async def boom() -> None:
        raise ValueError("boom")

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/boom")
    assert r.status_code == 500
    logged = stream.getvalue()
    assert "request_pipeline_error" in logged
    assert "boom" in logged  # traceback text in server logs is acceptable
