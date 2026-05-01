"""Tests for POST /api/v1/admin/persona-review."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.database import get_db
from app.main import app

_SECRET = "test-persona-review-secret"


@pytest.fixture(autouse=True)
def _patch_admin_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", _SECRET)


@pytest.fixture(autouse=True)
def _override_db() -> None:
    async def mock_db():
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_result.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()
        yield db

    app.dependency_overrides[get_db] = mock_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def _patch_redis_optional() -> None:
    with patch("app.routers.persona_review._get_redis_optional", return_value=None):
        yield


@pytest.fixture(autouse=True)
def _patch_memory_search() -> None:
    with (
        patch(
            "app.routers.persona_review.memory_svc.search_episodes",
            new_callable=AsyncMock,
        ) as mock_search,
        patch(
            "app.routers.persona_review.memory_svc.get_fatigue_ids",
            new_callable=AsyncMock,
        ) as mock_fatigue,
    ):
        mock_ep = MagicMock()
        mock_ep.source = "autopilot:semantic"
        mock_ep.summary = "Past decision: prefer pydantic v2 models on admin routes."
        mock_search.return_value = [mock_ep]
        mock_fatigue.return_value = set()
        yield


def _headers(secret: str = _SECRET) -> dict[str, str]:
    return {"X-Brain-Secret": secret}


@pytest.mark.asyncio
async def test_persona_review_ok() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/admin/persona-review",
            json={
                "pr_number": 42,
                "persona_id": "engineering",
                "diff_summary": "Adds new FastAPI router for exports.",
            },
            headers=_headers(),
        )
    assert res.status_code == 200
    payload = res.json()
    assert payload["success"] is True
    data = payload["data"]
    assert data["persona_id"] == "engineering"
    assert data["verdict"] == "comment"
    assert len(data["comments"]) >= 1
    assert "Stub review" in data["comments"][0]["body"]
    assert len(data["memory_citations"]) == 1
    assert data["memory_citations"][0]["source"] == "autopilot:semantic"


@pytest.mark.asyncio
async def test_persona_review_unknown_persona() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/admin/persona-review",
            json={
                "pr_number": 1,
                "persona_id": "not-a-real-persona-xyz",
                "diff_summary": "any",
            },
            headers=_headers(),
        )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_persona_review_rejects_missing_secret() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/admin/persona-review",
            json={"pr_number": 1, "persona_id": "engineering", "diff_summary": "x"},
            headers={},
        )
    assert res.status_code == 401
