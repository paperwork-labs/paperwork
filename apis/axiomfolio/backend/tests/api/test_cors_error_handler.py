"""CORS headers on unhandled exceptions (ALB/worker failures surface as JSON in browser)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app


@pytest.fixture(scope="module")
def client():
    try:
        return TestClient(app, raise_server_exceptions=False)
    except Exception:
        pytest.skip("FastAPI TestClient not available")


def test_unhandled_exception_returns_cors_headers(client: TestClient):
    path = f"/__cors_boom_{uuid.uuid4().hex}"

    async def _boom():
        raise RuntimeError("test boom")

    app.add_api_route(path, _boom, methods=["GET"])
    try:
        r = client.get(path, headers={"Origin": "http://localhost:3000"})
        assert r.status_code == 500
        body = r.json()
        assert body.get("detail") == "internal_server_error"
        assert body.get("path") == path
        assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
        assert r.headers.get("access-control-allow-credentials") == "true"
    finally:
        app.router.routes = [
            route for route in app.router.routes if getattr(route, "path", None) != path
        ]
