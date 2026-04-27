"""J2/J3: Brain admin learning dashboard API (read-only)."""

from datetime import UTC
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.database import get_db
from app.main import app
from app.models.episode import Episode


@pytest.fixture
async def client_mock_db():
    """ASGITransport client with a mock DB (no Docker Postgres)."""

    async def mock_get_db():
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=AsyncMock(
                scalars=lambda: AsyncMock(all=list),
                all=list,
                one=lambda: (0, 0),
            )
        )
        db.add = lambda _x: None
        yield db

    app.dependency_overrides[get_db] = mock_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_brain_learning_forbidden_without_secret(client_mock_db, monkeypatch):
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "configured-secret")
    res = await client_mock_db.get(
        "/api/v1/admin/brain/learning-summary?spark_days=0",
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_brain_learning_forbidden_when_dashboard_disabled(client_mock_db, monkeypatch):
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "s")
    monkeypatch.setattr(settings, "BRAIN_LEARNING_DASHBOARD_ENABLED", False)
    res = await client_mock_db.get(
        "/api/v1/admin/brain/learning-summary?spark_days=0",
        headers={"X-Brain-Secret": "s"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_brain_learning_summary_shape(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "test-learning-secret")
    monkeypatch.setattr(settings, "BRAIN_LEARNING_DASHBOARD_ENABLED", True)

    db_session.add(
        Episode(
            organization_id="paperwork-labs",
            source="brain:slack",
            summary="e2e learning row",
            importance=0.88,
            persona="ea",
            product=None,
        )
    )
    db_session.add(
        Episode(
            organization_id="paperwork-labs",
            source="model_router",
            summary="Routed to flash",
            importance=0.4,
            persona="router",
            model_used="gemini-2.5-flash",
            tokens_in=10,
            tokens_out=5,
        )
    )
    await db_session.commit()

    res = await client.get(
        "/api/v1/admin/brain/learning-summary?spark_days=0",
        headers={"X-Brain-Secret": "test-learning-secret"},
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["success"] is True
    data = payload["data"]
    assert data["totals"]["episodes"] >= 1
    assert data["totals"]["routing_decisions"] >= 1
    assert any(t["model"] == "gemini-2.5-flash" for t in data["model_token_totals"])
    top = data["top_by_importance"]
    assert any("e2e learning" in (x.get("summary") or "") for x in top)


@pytest.mark.asyncio
async def test_brain_episodes_excludes_model_router_by_default(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "test-learning-secret")
    monkeypatch.setattr(settings, "BRAIN_LEARNING_DASHBOARD_ENABLED", True)

    db_session.add(
        Episode(
            organization_id="paperwork-labs",
            source="model_router",
            summary="decision",
            importance=0.4,
        )
    )
    await db_session.commit()

    from datetime import datetime, timedelta

    since = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    res = await client.get(
        f"/api/v1/admin/brain/episodes?since={since}&limit=20",
        headers={"X-Brain-Secret": "test-learning-secret"},
    )
    assert res.status_code == 200
    eps = res.json()["data"]["episodes"]
    assert all(e.get("source") != "model_router" for e in eps)
