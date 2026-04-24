import importlib
import os

from fastapi.testclient import TestClient


def _build_client(rate_limit: str = "2/minute") -> TestClient:
    os.environ["ENVIRONMENT"] = "test"
    os.environ["RATE_LIMIT_DEFAULT"] = rate_limit
    os.environ["RATE_LIMIT_STORAGE_URL"] = ""
    os.environ["AUTO_MIGRATE_ON_STARTUP"] = "false"

    import app.api.main as main
    import app.api.rate_limit as rate_limit
    import app.config as config

    importlib.reload(config)
    # Limiter reads settings at import time; recreate it before main rebinds app.state.
    importlib.reload(rate_limit)
    importlib.reload(main)

    return TestClient(main.app, raise_server_exceptions=False)


def test_request_id_added_and_preserved(db_session):
    client = _build_client()

    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("x-request-id")

    response = client.get("/health", headers={"x-request-id": "test-req-id"})
    assert response.status_code == 200
    assert response.headers.get("x-request-id") == "test-req-id"

    response = client.get("/does-not-exist", headers={"x-request-id": "missing-route"})
    assert response.status_code == 404
    assert response.headers.get("x-request-id") == "missing-route"


def test_rate_limit_triggers_429(db_session):
    client = _build_client(rate_limit="2/minute")

    assert client.get("/health").status_code == 200
    assert client.get("/health").status_code == 200
    assert client.get("/health").status_code == 429
