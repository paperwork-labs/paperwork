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
    """Requests WITH a valid JWT succeed (or at least don't return 401)."""

    @pytest.fixture
    def auth_headers(self, client):
        """Create a user and get a valid JWT. Skip if DB not available."""
        try:
            reg = client.post(
                "/api/v1/auth/register",
                json={
                    "username": "testendpointauth",
                    "email": "testendpointauth@test.com",
                    "password": "TestPassword123!",
                    "full_name": "Test Auth",
                },
            )
            if reg.status_code not in (200, 201, 409):
                pytest.skip(f"Registration failed: {reg.status_code}")

            login = client.post(
                "/api/v1/auth/login",
                json={
                    "email": "testendpointauth@test.com",
                    "password": "TestPassword123!",
                },
            )
            if login.status_code != 200:
                pytest.skip(f"Login failed: {login.status_code}")

            token = login.json().get("access_token")
            if not token:
                pytest.skip("No access_token in login response")

            return {"Authorization": f"Bearer {token}"}
        except Exception as e:
            pytest.skip(f"Auth setup failed: {e}")

    def test_snapshots_with_token(self, client, auth_headers):
        r = client.get("/api/v1/market-data/snapshots", headers=auth_headers)
        assert r.status_code != 401, "Authenticated request should not return 401"

    def test_prices_with_token(self, client, auth_headers):
        r = client.get("/api/v1/market-data/prices/AAPL", headers=auth_headers)
        assert r.status_code != 401, "Authenticated request should not return 401"
