import pytest
from fastapi.testclient import TestClient
from backend.api.main import app


@pytest.fixture(scope="module")
def client():
    try:
        return TestClient(app, raise_server_exceptions=False)
    except TypeError:
        pytest.skip("Starlette TestClient incompatible in this runtime")


def test_accounts_requires_auth(client):
    r = client.get("/api/v1/accounts")
    # Auth-protected routes return 401/403 when unauthenticated depending on auth backend.
    assert r.status_code in (401, 403)


