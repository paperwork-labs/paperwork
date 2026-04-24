"""Public stats endpoint — no authentication."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.constants.public_stats import BROKERS_SUPPORTED


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def test_public_stats_returns_schema_without_auth(client: TestClient):
    r = client.get("/api/v1/public/stats")
    assert r.status_code == 200, r.text
    data = r.json()
    assert set(data.keys()) == {"portfolios_tracked", "charts_rendered_24h", "brokers_supported"}
    assert isinstance(data["portfolios_tracked"], int)
    assert data["portfolios_tracked"] >= 0
    assert isinstance(data["charts_rendered_24h"], int)
    assert data["charts_rendered_24h"] >= 0
    assert data["brokers_supported"] == BROKERS_SUPPORTED
