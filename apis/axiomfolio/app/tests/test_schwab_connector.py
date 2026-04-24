import asyncio
from types import SimpleNamespace
from app.services.bronze.aggregator.schwab_connector import SchwabConnector


def test_auth_url_contains_params(monkeypatch):
    conn = SchwabConnector(client_id="cid", client_secret="sec", redirect_uri="http://localhost/cb")
    url = conn.get_authorization_url(state="abc123", trading=False)
    assert "response_type=code" in url
    assert "client_id=cid" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%2Fcb" in url
    assert "scope=read" in url
    assert "state=abc123" in url


def test_auth_url_trading_scope(monkeypatch):
    conn = SchwabConnector(client_id="cid", client_secret="sec", redirect_uri="http://localhost/cb")
    url = conn.get_authorization_url(state="abc123", trading=True)
    # Scope is URL-encoded; implementation may use '+' (space) or '%20'.
    assert "scope=read" in url and "trade" in url


def test_exchange_code_and_refresh_tokens(monkeypatch):
    # Mock httpx.AsyncClient.post
    class DummyResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, data=None, **kwargs):
            if data.get("grant_type") == "authorization_code":
                return DummyResponse(200, {"access_token": "at", "refresh_token": "rt"})
            if data.get("grant_type") == "refresh_token":
                return DummyResponse(200, {"access_token": "at2", "refresh_token": "rt2"})
            return DummyResponse(400, {"error": "bad_request"})

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", DummyClient)
    conn = SchwabConnector(client_id="cid", client_secret="sec", redirect_uri="http://localhost/cb")
    tokens = asyncio.get_event_loop().run_until_complete(conn.exchange_code_for_tokens("code"))
    assert tokens["access_token"] == "at" and tokens["refresh_token"] == "rt"
    tokens2 = asyncio.get_event_loop().run_until_complete(conn.refresh_tokens("rt"))
    assert tokens2["access_token"] == "at2" and tokens2["refresh_token"] == "rt2"


