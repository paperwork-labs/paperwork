"""Health endpoints."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from api_foundation.healthcheck import register_healthcheck


def test_healthz_always_returns_200() -> None:
    app = FastAPI()
    register_healthcheck(app)
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "alive"}


def test_readyz_200_when_registered_checks_pass_or_skipped() -> None:
    app = FastAPI()
    register_healthcheck(app, check_db=lambda: True, check_redis=lambda: True)
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/readyz")
    assert r.status_code == 200
    payload = r.json()
    assert payload["status"] == "ready"
    assert payload["probes"]["database"] is True
    assert payload["probes"]["redis"] is True


def test_readyz_skipped_probes_only() -> None:
    app = FastAPI()
    register_healthcheck(app)
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/readyz")
    assert r.status_code == 200


def test_readyz_503_when_check_returns_false(caplog: pytest.LogCaptureFixture) -> None:
    app = FastAPI()
    register_healthcheck(app, check_db=lambda: False, check_redis=lambda: True)
    client = TestClient(app, raise_server_exceptions=False)
    with caplog.at_level("ERROR", logger="api_foundation.healthcheck"):
        r = client.get("/readyz")
    assert r.status_code == 503
    assert r.json()["status"] == "not_ready"
    assert r.json()["probes"]["database"] is False


def test_readyz_503_when_check_raises(caplog: pytest.LogCaptureFixture) -> None:
    app = FastAPI()

    def boom() -> bool:
        raise RuntimeError("redis down")

    register_healthcheck(app, check_db=lambda: True, check_redis=boom)
    client = TestClient(app, raise_server_exceptions=False)
    with caplog.at_level("ERROR", logger="api_foundation.healthcheck"):
        r = client.get("/readyz")
    assert r.status_code == 503
    assert r.json()["probes"]["redis"] is False
    assert any("readiness_probe_failed" in rec.getMessage() for rec in caplog.records)
