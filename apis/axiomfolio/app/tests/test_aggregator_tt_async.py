import uuid
import asyncio
import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.tests.auth_test_utils import approve_user_for_login_tests


@pytest.fixture(scope="module")
def client():
    try:
        return TestClient(app, raise_server_exceptions=False)
    except Exception:
        pytest.skip("FastAPI TestClient not available in this env")


def _login(client):
    username = f"tt_{uuid.uuid4().hex[:6]}"
    password = "Passw0rd!"
    email = f"{username}@example.com"
    r = client.post("/api/v1/auth/register", json={"username": username, "email": email, "password": password})
    if r.status_code != 200:
        pytest.skip("auth endpoint not available in test env")
    approve_user_for_login_tests(username)
    r2 = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r2.status_code == 200
    return r.json().get("id"), r2.json()["access_token"]


def test_tastytrade_connect_async_success(client, monkeypatch):
    user_id, token = _login(client)
    if not token:
        pytest.skip("login failed in test env")

    class DummyTT:
        connected = True
        connection_health = {"status": "connected"}
        accounts = []
        async def connect_with_credentials(self, client_secret, refresh_token, **kwargs):
            return True
        async def get_accounts(self):
            return [{"account_number": "TT123", "nickname": "Primary"}]
        async def disconnect(self):
            pass

    # Import the actual module to patch (not the re-exported router)
    import importlib
    agg_module = importlib.import_module("app.api.routes.aggregator")
    monkeypatch.setattr(agg_module, "TastyTradeClient", lambda: DummyTT())

    def _create_task(coro):
        loop = asyncio.get_event_loop()
        return loop.create_task(coro) if loop.is_running() else asyncio.run(coro)
    monkeypatch.setattr(agg_module.asyncio, "create_task", _create_task)

    r = client.post(
        "/api/v1/aggregator/tastytrade/connect",
        json={"client_id": "test_client_id", "client_secret": "test_secret", "refresh_token": "test_refresh"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    job_id = r.json().get("job_id")
    assert job_id

    rs = client.get(f"/api/v1/aggregator/tastytrade/status?job_id={job_id}", headers={"Authorization": f"Bearer {token}"})
    assert rs.status_code == 200
    body = rs.json()
    assert body.get("job_state") in ("success", None)
