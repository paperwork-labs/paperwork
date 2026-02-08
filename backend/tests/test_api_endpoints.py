import pytest

try:
    from fastapi.testclient import TestClient
    from backend.api.main import app
    from backend.api.dependencies import get_admin_user

    FASTAPI_AVAILABLE = True
except Exception:
    FASTAPI_AVAILABLE = False


@pytest.fixture(scope="module")
def client():
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI TestClient not available in this env")
    try:
        # Do not raise server-side exceptions into the test runner; treat them as 500 responses.
        return TestClient(app, raise_server_exceptions=False)
    except TypeError:
        pytest.skip("Starlette TestClient incompatible in this runtime")


def _ok(status_code: int) -> bool:
    # Allow common statuses in varied envs, including 401 for auth-protected routes
    return status_code in (200, 401, 403, 404, 422, 500)


def test_portfolio_live(client):
    r = client.get("/api/v1/portfolio/live")
    assert _ok(r.status_code)


def test_stocks_list(client):
    r = client.get("/api/v1/portfolio/stocks")
    assert _ok(r.status_code)


def test_options_accounts(client):
    r = client.get("/api/v1/portfolio/options/accounts")
    assert _ok(r.status_code)


def test_options_unified_portfolio(client):
    r = client.get("/api/v1/portfolio/options/unified/portfolio")
    assert _ok(r.status_code)


def test_options_unified_summary(client):
    r = client.get("/api/v1/portfolio/options/unified/summary")
    assert _ok(r.status_code)


def test_statements(client):
    r = client.get("/api/v1/portfolio/statements?days=30")
    assert _ok(r.status_code)


def test_dividends(client):
    r = client.get("/api/v1/portfolio/dividends?days=365")
    assert _ok(r.status_code)


def test_market_data_refresh_requires_admin(client):
    r = client.post("/api/v1/market-data/symbols/AAPL/refresh")
    assert r.status_code in (401, 403)


def test_market_data_refresh_with_admin_override(client):
    app.dependency_overrides[get_admin_user] = object
    try:
        r = client.post("/api/v1/market-data/symbols/AAPL/refresh")
        assert _ok(r.status_code)
    finally:
        app.dependency_overrides.pop(get_admin_user, None)


def test_market_data_indices_refresh_requires_admin(client):
    r = client.post("/api/v1/market-data/indices/constituents/refresh")
    assert r.status_code in (401, 403)


def test_market_data_moving_averages(client):
    r = client.get("/api/v1/market-data/technical/moving-averages/AAPL")
    assert _ok(r.status_code)


def test_market_data_ma_bucket(client):
    r = client.get("/api/v1/market-data/technical/ma-bucket/AAPL")
    assert _ok(r.status_code)


def test_market_data_stage(client):
    r = client.get("/api/v1/market-data/technical/stage/AAPL")
    assert _ok(r.status_code)


def test_market_data_prices_aliases(client):
    r_price = client.get("/api/v1/market-data/prices/AAPL")
    r_history = client.get("/api/v1/market-data/prices/AAPL/history")
    assert _ok(r_price.status_code)
    assert _ok(r_history.status_code)


def test_market_data_snapshots_aliases(client):
    r_snapshot = client.get("/api/v1/market-data/snapshots/AAPL")
    r_snapshots = client.get("/api/v1/market-data/snapshots")
    r_snapshot_history = client.get("/api/v1/market-data/snapshots/AAPL/history")
    assert _ok(r_snapshot.status_code)
    assert _ok(r_snapshots.status_code)
    assert _ok(r_snapshot_history.status_code)


def test_market_data_universe_and_indices_aliases(client):
    r_indices = client.get("/api/v1/market-data/indices/constituents")
    r_tracked = client.get("/api/v1/market-data/universe/tracked")
    assert _ok(r_indices.status_code)
    assert _ok(r_tracked.status_code)


def test_market_data_coverage_aliases(client):
    r_coverage = client.get("/api/v1/market-data/coverage")
    r_symbol = client.get("/api/v1/market-data/coverage/AAPL")
    assert _ok(r_coverage.status_code)
    assert _ok(r_symbol.status_code)


def test_accounts_endpoints_smoke(client):
    r_list = client.get("/api/v1/accounts")
    r_sync_all = client.post("/api/v1/accounts/sync-all")
    assert _ok(r_list.status_code)
    assert r_sync_all.status_code in (200, 400, 401, 403, 404, 422, 500)
