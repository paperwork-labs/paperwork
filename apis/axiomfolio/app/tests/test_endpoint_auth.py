"""Tests for endpoint auth enforcement.

Verifies that market-data endpoints return 401 without a valid JWT
and succeed with one.
"""

import pytest

try:
    from fastapi.testclient import TestClient
    from app.api.main import app

    FASTAPI_AVAILABLE = True
except Exception:
    FASTAPI_AVAILABLE = False


pytestmark = pytest.mark.no_db


@pytest.fixture(scope="module")
def client():
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI TestClient not available in this env")
    try:
        return TestClient(app, raise_server_exceptions=False)
    except TypeError:
        pytest.skip("Starlette TestClient incompatible in this runtime")


class TestSnapshotsAuth:
    """GET /api/v1/market-data/snapshots requires auth."""

    def test_returns_401_without_token(self, client):
        r = client.get("/api/v1/market-data/snapshots")
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"

    def test_returns_401_with_invalid_token(self, client):
        r = client.get(
            "/api/v1/market-data/snapshots",
            headers={"Authorization": "Bearer invalid-token-123"},
        )
        assert r.status_code == 401, f"Expected 401 for bad token, got {r.status_code}"


class TestPricesAuth:
    """GET /api/v1/market-data/prices/{symbol} requires auth."""

    def test_returns_401_without_token(self, client):
        r = client.get("/api/v1/market-data/prices/AAPL")
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"

    def test_returns_401_with_invalid_token(self, client):
        r = client.get(
            "/api/v1/market-data/prices/AAPL",
            headers={"Authorization": "Bearer garbage"},
        )
        assert r.status_code == 401, f"Expected 401 for bad token, got {r.status_code}"


class TestDashboardAuth:
    """GET /api/v1/market-data/dashboard requires auth."""

    def test_returns_401_without_token(self, client):
        r = client.get("/api/v1/market-data/dashboard")
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"


class TestCoverageAuth:
    """GET /api/v1/market-data/coverage requires auth."""

    def test_returns_401_without_token(self, client):
        r = client.get("/api/v1/market-data/coverage")
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"


class TestAuthenticatedAccess:
    """Authenticated requests succeed when ``get_current_user`` resolves (Clerk JWT in prod)."""

    @pytest.fixture
    def auth_headers(self, client):
        from unittest.mock import MagicMock

        from app.api.dependencies import get_current_user, get_market_data_viewer
        from app.models.user import User, UserRole

        u = MagicMock(spec=User)
        u.id = 424242
        u.is_active = True
        u.is_approved = True
        u.role = UserRole.ANALYST
        app.dependency_overrides[get_current_user] = lambda: u
        app.dependency_overrides[get_market_data_viewer] = lambda: u
        try:
            yield {"Authorization": "Bearer test-clerk-session"}
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_market_data_viewer, None)

    def test_snapshots_with_token(self, client, auth_headers):
        r = client.get("/api/v1/market-data/snapshots", headers=auth_headers)
        assert r.status_code != 401, "Authenticated request should not return 401"

    def test_prices_with_token(self, client, auth_headers):
        r = client.get("/api/v1/market-data/prices/AAPL", headers=auth_headers)
        assert r.status_code != 401, "Authenticated request should not return 401"
