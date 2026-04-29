"""``GET /api/v1/admin/self-improvement/*`` — Studio self-improvement page."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.database import get_db
from app.main import app


@pytest_asyncio.fixture
async def client_mock_db():
    """ASGI client with mock DB (no Docker Postgres)."""

    async def mock_get_db():
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=result_mock)
        yield db

    app.dependency_overrides[get_db] = mock_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_self_improvement_requires_secret(
    client_mock_db: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "expected-secret")
    res = await client_mock_db.get("/api/v1/admin/self-improvement/learning-state")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_learning_state_shape(
    client_mock_db: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "sec")
    res = await client_mock_db.get(
        "/api/v1/admin/self-improvement/learning-state",
        headers={"X-Brain-Secret": "sec"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    d = body["data"]
    assert d["ok"] is True
    for k in (
        "open_candidates",
        "accepted_candidates",
        "declined_candidates",
        "superseded_candidates",
        "conversion_rate",
    ):
        assert k in d


@pytest.mark.asyncio
async def test_promotions_includes_progress(
    client_mock_db: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "sec")
    res = await client_mock_db.get(
        "/api/v1/admin/self-improvement/promotions",
        headers={"X-Brain-Secret": "sec"},
    )
    assert res.status_code == 200
    d = res.json()["data"]
    assert "progress_to_next_tier_pct" in d
    assert "recent_merges_last_10" in d


@pytest.mark.asyncio
async def test_outcomes_buckets(
    client_mock_db: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "sec")
    res = await client_mock_db.get(
        "/api/v1/admin/self-improvement/outcomes",
        headers={"X-Brain-Secret": "sec"},
    )
    assert res.status_code == 200
    d = res.json()["data"]
    assert "buckets" in d
    assert "reverted" in d["buckets"]


@pytest.mark.asyncio
async def test_retros_list(client_mock_db: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "sec")
    res = await client_mock_db.get(
        "/api/v1/admin/self-improvement/retros?limit=3",
        headers={"X-Brain-Secret": "sec"},
    )
    assert res.status_code == 200
    d = res.json()["data"]
    assert isinstance(d["retros"], list)


@pytest.mark.asyncio
async def test_automation_state(
    client_mock_db: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "sec")
    res = await client_mock_db.get(
        "/api/v1/admin/self-improvement/automation-state",
        headers={"X-Brain-Secret": "sec"},
    )
    assert res.status_code == 200
    d = res.json()["data"]
    assert "scheduler_running" in d
    assert "jobs" in d


@pytest.mark.asyncio
async def test_procedural_memory_rules(
    client_mock_db: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "sec")
    res = await client_mock_db.get(
        "/api/v1/admin/self-improvement/procedural-memory",
        headers={"X-Brain-Secret": "sec"},
    )
    assert res.status_code == 200
    d = res.json()["data"]
    assert d.get("error") is None
    assert d["count"] >= 1
    assert isinstance(d["rules"], list)


@pytest.mark.asyncio
async def test_summary_bundle(client_mock_db: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "sec")
    res = await client_mock_db.get(
        "/api/v1/admin/self-improvement/summary",
        headers={"X-Brain-Secret": "sec"},
    )
    assert res.status_code == 200
    d = res.json()["data"]
    assert "current_tier" in d
    assert "positive_retro_streak_weeks" in d
