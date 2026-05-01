"""Smoke tests for /api/v1/memory/* endpoints (Wave AUTO PR-AU1).

Uses the standard mock-DB pattern from conftest.py — no live database required.
All DB-touching paths are patched; the goal is to verify routing, auth, and
response shape rather than retrieval correctness (which lives in test_memory.py).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.database import get_db
from app.main import app

_SECRET = "test-secret-value"


@pytest.fixture(autouse=True)
def _patch_secret(monkeypatch):
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", _SECRET)


@pytest.fixture(autouse=True)
def _override_db():
    async def mock_db():
        db = AsyncMock()
        # search_episodes returns []
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
def _patch_redis():
    with patch("app.routers.memory._get_redis_optional", return_value=None):
        yield


@pytest.fixture(autouse=True)
def _patch_memory_svc():
    with (
        patch(
            "app.routers.memory.memory_svc.search_episodes", new_callable=AsyncMock
        ) as mock_search,
        patch(
            "app.routers.memory.memory_svc.get_fatigue_ids", new_callable=AsyncMock
        ) as mock_fatigue,
        patch("app.routers.memory.memory_svc.mark_recalled", new_callable=AsyncMock),
        patch("app.routers.memory.memory_svc.store_episode", new_callable=AsyncMock) as mock_store,
    ):
        mock_search.return_value = []
        mock_fatigue.return_value = set()
        mock_episode = MagicMock()
        mock_episode.id = 42
        mock_store.return_value = mock_episode
        yield


@pytest.fixture(autouse=True)
def _patch_proc_mem():
    with patch("app.routers.memory.proc_mem_svc.find_rules_for_context", return_value=[]):
        yield


@pytest.fixture(autouse=True)
def _patch_pr_outcomes():
    with patch("app.routers.memory.pr_outcomes_svc.list_pr_outcomes_for_query", return_value=[]):
        yield


def _headers(secret: str = _SECRET) -> dict[str, str]:
    return {"X-Brain-Secret": secret}


@pytest.mark.asyncio
async def test_recall_decisions_returns_200():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(
            "/api/v1/memory/recall-decisions",
            params={"query": "architecture decisions"},
            headers=_headers(),
        )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "results" in data["data"]
    assert data["data"]["query"] == "architecture decisions"


@pytest.mark.asyncio
async def test_recall_decisions_missing_query_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(
            "/api/v1/memory/recall-decisions",
            headers=_headers(),
        )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_recall_decisions_bad_auth_returns_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(
            "/api/v1/memory/recall-decisions",
            params={"query": "test"},
            headers={"X-Brain-Secret": "wrong"},
        )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_recall_pr_history_returns_200():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(
            "/api/v1/memory/recall-pr-history",
            params={"keywords": "ws-82,memory-layer", "days": "14"},
            headers=_headers(),
        )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "results" in data["data"]
    assert data["data"]["days"] == 14
    assert "ws-82" in data["data"]["keywords"]


@pytest.mark.asyncio
async def test_recall_pr_history_missing_keywords_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(
            "/api/v1/memory/recall-pr-history",
            headers=_headers(),
        )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_episodic_themes_returns_200():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(
            "/api/v1/memory/episodic-themes",
            params={"days": "7"},
            headers=_headers(),
        )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "themes" in data["data"]
    assert data["data"]["episode_count"] == 0


@pytest.mark.asyncio
async def test_procedural_rules_returns_200():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(
            "/api/v1/memory/procedural-rules",
            params={"domain": "cpa tax filing"},
            headers=_headers(),
        )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "rules" in data["data"]
    assert data["data"]["domain"] == "cpa tax filing"


@pytest.mark.asyncio
async def test_procedural_rules_missing_domain_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(
            "/api/v1/memory/procedural-rules",
            headers=_headers(),
        )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_cross_context_returns_200():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(
            "/api/v1/memory/cross-context",
            params={"query": "deploy budget", "contexts": "paperwork-labs,sankalp-personal"},
            headers=_headers(),
        )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "results_by_context" in data["data"]
    assert set(data["data"]["contexts"]) == {"paperwork-labs", "sankalp-personal"}


@pytest.mark.asyncio
async def test_cross_context_empty_contexts_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(
            "/api/v1/memory/cross-context",
            params={"query": "test", "contexts": "  ,  "},
            headers=_headers(),
        )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_remember_episodic_returns_201():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/memory/remember",
            json={
                "type": "episodic",
                "content": {"summary": "Deployed ws82 memory layer successfully"},
            },
            headers=_headers(),
        )
    assert res.status_code == 201
    data = res.json()
    assert data["success"] is True
    assert data["data"]["type"] == "episodic"
    assert data["data"]["source"] == "autopilot:episodic"
    assert data["data"]["episode_id"] == 42


@pytest.mark.asyncio
async def test_remember_semantic_returns_201():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/memory/remember",
            json={
                "type": "semantic",
                "content": {"text": "Brain uses BRAIN_API_SECRET for internal auth"},
                "persona_id": "cpa",
            },
            headers=_headers(),
        )
    assert res.status_code == 201
    data = res.json()
    assert data["data"]["source"] == "autopilot:semantic"


@pytest.mark.asyncio
async def test_remember_invalid_type_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/memory/remember",
            json={"type": "unknown", "content": {"summary": "test"}},
            headers=_headers(),
        )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_remember_missing_summary_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/memory/remember",
            json={"type": "episodic", "content": {"importance": 0.9}},
            headers=_headers(),
        )
    assert res.status_code == 422
