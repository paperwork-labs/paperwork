"""FastAPI integration tests."""

from __future__ import annotations

import io
import json
import logging

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from observability.fastapi_integration import instrument_fastapi
from observability.logging import StructuredJsonFormatter
from observability.metrics import configure_metrics


def test_request_id_header_and_logs() -> None:
    configure_metrics("api-int")
    stream = io.StringIO()
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(StructuredJsonFormatter("api-int", json_ensure_ascii=False))
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    app = FastAPI()

    @app.get("/hello")
    def hello(request: Request) -> dict[str, str]:
        request.state.user_id = "user-99"
        return {"ok": "yes"}

    instrument_fastapi(app, service_name="api-int", configure_logging=False)

    client = TestClient(app)
    resp = client.get("/hello", headers={"X-Request-ID": "fixed-rid-1"})
    assert resp.status_code == 200
    assert resp.headers.get("x-request-id") == "fixed-rid-1"

    rows = [json.loads(line) for line in stream.getvalue().strip().splitlines()]
    finished = [r for r in rows if r.get("message") == "http_request_finished"]
    assert finished
    assert finished[0]["request_id"] == "fixed-rid-1"
    assert finished[0]["user_id"] == "user-99"
