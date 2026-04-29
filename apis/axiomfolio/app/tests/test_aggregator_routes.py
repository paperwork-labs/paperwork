import asyncio
import uuid
import jwt
import pytest

from app.api.main import app
from app.api.dependencies import get_current_user, get_db
from app.config import settings
from app.models.broker_account import BrokerAccount, BrokerType, AccountType
from app.tests.auth_test_utils import approve_user_for_login_tests, make_user_dependency_override


try:
    from fastapi.testclient import TestClient

    FASTAPI_AVAILABLE = True
except Exception:
    FASTAPI_AVAILABLE = False


@pytest.fixture(scope="module")
def client():
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI TestClient not available in this env")
    try:
        return TestClient(app, raise_server_exceptions=False)
    except TypeError:
        pytest.skip("Starlette TestClient incompatible in this runtime")


def _login_token(client) -> str:
    # Create a user and login (unique username). Uses default app get_db (SessionLocal);
    # approval must commit so login sees it. Do not pass db_session here when login
    # runs before get_db override (uncommitted approval would be invisible to login).
    username = f"agg_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "Passw0rd!"
    client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    approve_user_for_login_tests(username)
    r_login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert r_login.status_code == 200
    return r_login.json()["access_token"], username


def _create_schwab_account_for_user(username: str, session) -> int:
    # Associate a BrokerAccount to this user by looking up user.id
    from app.models.user import User

    user = session.query(User).filter(User.username == username).first()
    acct = BrokerAccount(
        user_id=user.id,
        broker=BrokerType.SCHWAB,
        account_number=f"S{uuid.uuid4().hex[:6]}",
        account_name="Schwab Test",
        account_type=AccountType.TAXABLE,
    )
    session.add(acct)
    session.commit()
    session.refresh(acct)
    return acct.id


def test_brokers_list(client):
    r = client.post("/api/v1/aggregator/brokers")
    assert r.status_code == 200 and "schwab" in r.json().get("brokers", [])


async def _stub_exchange_code_for_tokens(*args, **kwargs):
    return {"access_token": "AT", "refresh_token": "RT"}


def test_link_and_callback_flow(client, monkeypatch, db_session):
    # Ensure Schwab OAuth is considered configured for this test
    monkeypatch.setattr(settings, "SCHWAB_CLIENT_ID", "cid")
    monkeypatch.setattr(settings, "SCHWAB_CLIENT_SECRET", "csecret")
    monkeypatch.setattr(settings, "SCHWAB_REDIRECT_URI", "http://localhost/cb")

    _login_tuple = _login_token(client)
    _token, username = _login_tuple

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = make_user_dependency_override(username)
    account_id = _create_schwab_account_for_user(username, db_session)

    # Stub httpx.AsyncClient for /schwab/link (probe GET)
    class DummyResponse:
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self._payload = payload or {}
            self.headers = {}
        def json(self):
            return self._payload
    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def get(self, url, params=None, timeout=None):
            return DummyResponse(200)
        async def post(self, url, data=None):
            return DummyResponse(200, {"access_token": "AT", "refresh_token": "RT"})

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", DummyClient)
    # Stub token exchange so callback succeeds regardless of async/thread context
    from app.services.bronze.aggregator.schwab_connector import SchwabConnector
    monkeypatch.setattr(SchwabConnector, "exchange_code_for_tokens", _stub_exchange_code_for_tokens)

    try:
        # Link -> get URL (probe runs inside)
        r_link = client.post(
            "/api/v1/aggregator/schwab/link",
            json={"account_id": account_id, "trading": False},
            headers={"Authorization": "Bearer test"},
        )
        assert r_link.status_code == 200
        url = r_link.json()["url"]
        # Extract state query param from URL for callback
        import urllib.parse as _up
        qs = _up.urlparse(url).query
        params = dict(_up.parse_qsl(qs))
        assert "state" in params
        state = params["state"]

        r_cb = client.get(
            "/api/v1/aggregator/schwab/callback",
            params={"code": "abc", "state": state},
            follow_redirects=False,
        )
        assert r_cb.status_code in (302, 307)
        assert "schwab=linked" in r_cb.headers.get("location", "")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


