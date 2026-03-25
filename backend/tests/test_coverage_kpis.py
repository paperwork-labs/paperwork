from fastapi.testclient import TestClient
import pytest

from backend.api.main import app
from backend.api.dependencies import get_market_data_viewer
from backend.models.user import UserRole
from backend.config import settings


client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def allow_market_data_viewer():
    class _DummyUser:
        role = UserRole.ADMIN
        is_active = True
        email = "admin@example.com"

    app.dependency_overrides[get_market_data_viewer] = lambda: _DummyUser()
    yield
    app.dependency_overrides.pop(get_market_data_viewer, None)


def test_coverage_kpi_help_all_5m_covered_when_stale_m5_zero(monkeypatch):
    # Force public visibility so viewer dependency is used consistently
    monkeypatch.setattr(settings, "MARKET_DATA_SECTION_PUBLIC", True)

    resp = client.get("/api/v1/market-data/coverage")
    assert resp.status_code == 200
    payload = resp.json()

    kpis = payload.get("meta", {}).get("kpis") or []
    assert isinstance(kpis, list)
    stale_card = next((k for k in kpis if k.get("id") == "stale_daily"), None)
    assert stale_card is not None

    stale_m5 = int(payload.get("status", {}).get("stale_m5") or 0)
    help_text = str(stale_card.get("help") or "")
    if stale_m5 == 0:
        assert help_text == "All 5m covered"
    else:
        assert help_text == f"{stale_m5} missing 5m"


