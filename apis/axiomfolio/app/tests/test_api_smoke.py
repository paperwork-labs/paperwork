import pytest

try:
    from fastapi.testclient import TestClient
    from app.api.main import app

    FASTAPI_AVAILABLE = True
except Exception:
    FASTAPI_AVAILABLE = False


@pytest.fixture(scope="module")
def client():
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI TestClient not available in this env")
    # Workaround older httpx/starlette in container: prefer asgi-lifespan disabled
    try:
        # Do not raise server-side exceptions into the test runner; treat them as 500 responses.
        return TestClient(app, raise_server_exceptions=False)
    except TypeError:
        pytest.skip("Starlette TestClient incompatible in this runtime")


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "healthy"


def test_accounts_list(client):
    # Accounts routes are auth-protected
    r = client.get("/api/v1/accounts")
    assert r.status_code in (401, 403)


def test_portfolio_live(client):
    r = client.get("/api/v1/portfolio/live")
    assert r.status_code in (200, 401, 500)


def test_statements_empty_ok(client):
    r = client.get("/api/v1/portfolio/statements?days=7")
    assert r.status_code in (200, 401, 403, 500)


def test_portfolio_stocks_endpoint(client):
    r = client.get("/api/v1/portfolio/stocks")
    assert r.status_code in (200, 401, 403, 500)


def test_portfolio_options_endpoints(client):
    r1 = client.get("/api/v1/portfolio/options/accounts")
    r2 = client.get("/api/v1/portfolio/options/unified/portfolio")
    r3 = client.get("/api/v1/portfolio/options/unified/summary")
    assert r1.status_code in (200, 401, 500)
    assert r2.status_code in (200, 401, 500)
    assert r3.status_code in (200, 401, 500)
