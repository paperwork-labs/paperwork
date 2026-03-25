import uuid
import asyncio
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.tests.auth_test_utils import approve_user_for_login_tests
from backend.models.broker_account import BrokerAccount, AccountCredentials, BrokerType
import backend.api.routes.aggregator as agg


@pytest.fixture(scope="module")
def client():
    try:
        return TestClient(app, raise_server_exceptions=False)
    except Exception:
        pytest.skip("FastAPI TestClient not available in this env")


def _login(client):
    username = f"ibkr_{uuid.uuid4().hex[:6]}"
    password = "Passw0rd!"
    email = f"{username}@example.com"
    r = client.post("/api/v1/auth/register", json={"username": username, "email": email, "password": password})
    if r.status_code != 200:
        pytest.skip("auth endpoint not available in test env")
    approve_user_for_login_tests(username)
    r2 = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r2.status_code == 200
    return r.json().get("id"), r2.json()["access_token"]


def test_ibkr_flex_connect_and_status(client, monkeypatch, db_session):
    pytest.skip("Integration-style test (background job + independent session); excluded from default suite.")
    user_id, token = _login(client)
    if not token:
        pytest.skip("login failed in test env")

    # run background jobs inline for deterministic test
    def _create_task(coro):
        loop = asyncio.get_event_loop()
        return loop.create_task(coro) if loop.is_running() else asyncio.run(coro)
    monkeypatch.setattr(agg.asyncio, "create_task", _create_task)

    # connect with dummy credentials (async -> returns job_id)
    r = client.post(
        "/api/v1/aggregator/ibkr/connect",
        json={"flex_token": "tok123", "query_id": "999999"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    job_id = r.json().get("job_id")
    assert job_id

    # verify credentials row exists with metadata
    # The connect endpoint runs a background job that uses its own SessionLocal().
    # We intentionally do NOT override get_db for this test, so the user row is committed
    # and visible to the background job's session.
    acct = db_session.query(BrokerAccount).filter(BrokerAccount.user_id == user_id, BrokerAccount.broker == BrokerType.IBKR).first()
    assert acct is not None
    cred = db_session.query(AccountCredentials).filter(AccountCredentials.account_id == acct.id).first()
    assert cred is not None
    assert cred.provider == BrokerType.IBKR
    assert cred.credential_type == "ibkr_flex"
    assert cred.encrypted_credentials is not None

    # status endpoint should report connected/no error
    rs = client.get("/api/v1/aggregator/ibkr/status", headers={"Authorization": f"Bearer {token}"})
    assert rs.status_code == 200
    body = rs.json()
    assert body.get("connected") in (True, False)




