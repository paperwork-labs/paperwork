"""Admin POST /memory/search — keyword, semantic, hybrid memory retrieval."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings
from app.models.episode import Episode

SECRET = "test-memory-search-secret"
TOKEN = "ws82memsearch_alpha"


@pytest.fixture(autouse=True)
def _admin_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", SECRET)


def _headers() -> dict[str, str]:
    return {"X-Brain-Secret": SECRET}


def _post(**kwargs: object):
    return {
        "query": f"{TOKEN} baseline",
        "mode": "keyword",
        "limit": 10,
        **kwargs,
    }


@pytest.mark.asyncio
async def test_keyword_mode_matches_summary_and_metadata(client: AsyncClient, db_session) -> None:
    db_session.add_all(
        [
            Episode(
                organization_id="paperwork-labs",
                source="test:memory-search",
                summary=f"First hit {TOKEN} in summary",
                importance=0.4,
                metadata_={"note": "x"},
            ),
            Episode(
                organization_id="paperwork-labs",
                source="test:memory-search",
                summary="No token here",
                importance=0.5,
                metadata_={"trace": f"{TOKEN} in json"},
            ),
            Episode(
                organization_id="paperwork-labs",
                source="other:src",
                summary="Unrelated",
                importance=0.9,
                metadata_={},
            ),
        ]
    )
    await db_session.commit()

    r = await client.post(
        "/api/v1/admin/memory/search",
        headers=_headers(),
        json={"query": TOKEN, "mode": "keyword", "limit": 10},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["mode_used"] == "keyword"
    summaries = {row["summary"] for row in data["results"]}
    assert any(TOKEN in s for s in summaries)
    assert data["count"] == 2
    for row in data["results"]:
        assert "snippet" in row
        assert len(row["snippet"]) <= 200


@pytest.mark.asyncio
async def test_source_prefix_filter(client: AsyncClient, db_session) -> None:
    db_session.add_all(
        [
            Episode(
                organization_id="paperwork-labs",
                source="autopilot:test",
                summary=f"{TOKEN} autopilot row",
                importance=0.5,
            ),
            Episode(
                organization_id="paperwork-labs",
                source="manual:other",
                summary=f"{TOKEN} manual row",
                importance=0.5,
            ),
        ]
    )
    await db_session.commit()

    r = await client.post(
        "/api/v1/admin/memory/search",
        headers=_headers(),
        json={
            "query": TOKEN,
            "mode": "keyword",
            "source_prefix": "autopilot",
            "limit": 10,
        },
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["count"] == 1
    assert data["results"][0]["source"].startswith("autopilot")


@pytest.mark.asyncio
async def test_min_importance_filter(client: AsyncClient, db_session) -> None:
    db_session.add_all(
        [
            Episode(
                organization_id="paperwork-labs",
                source="test:imp",
                summary=f"low {TOKEN}",
                importance=0.2,
            ),
            Episode(
                organization_id="paperwork-labs",
                source="test:imp",
                summary=f"high {TOKEN}",
                importance=0.85,
            ),
        ]
    )
    await db_session.commit()

    r = await client.post(
        "/api/v1/admin/memory/search",
        headers=_headers(),
        json={
            "query": TOKEN,
            "mode": "keyword",
            "min_importance": 0.5,
            "limit": 10,
        },
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["count"] == 1
    assert data["results"][0]["importance"] == 0.85


@pytest.mark.asyncio
async def test_limit_respected(client: AsyncClient, db_session) -> None:
    for i in range(15):
        db_session.add(
            Episode(
                organization_id="paperwork-labs",
                source="test:lim",
                summary=f"{TOKEN} row {i}",
                importance=0.5,
            )
        )
    await db_session.commit()

    r = await client.post(
        "/api/v1/admin/memory/search",
        headers=_headers(),
        json={"query": TOKEN, "mode": "keyword", "limit": 3},
    )
    assert r.status_code == 200
    assert r.json()["data"]["count"] == 3


@pytest.mark.asyncio
async def test_requires_secret(client: AsyncClient, db_session) -> None:
    db_session.add(
        Episode(
            organization_id="paperwork-labs",
            source="x",
            summary=f"{TOKEN} x",
            importance=0.5,
        )
    )
    await db_session.commit()

    r = await client.post("/api/v1/admin/memory/search", json=_post())
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_invalid_body_empty_query(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/admin/memory/search",
        headers=_headers(),
        json={"query": "", "mode": "keyword"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_invalid_mode(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/admin/memory/search",
        headers=_headers(),
        json={"query": "x", "mode": "fulltext"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_hybrid_falls_back_when_embedding_unavailable(
    client: AsyncClient,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _no_embed(_text: str) -> None:
        return None

    monkeypatch.setattr("app.services.memory.embed_text", _no_embed)

    db_session.add(
        Episode(
            organization_id="paperwork-labs",
            source="test:fb",
            summary=f"fallback {TOKEN} case",
            importance=0.7,
        )
    )
    await db_session.commit()

    r = await client.post(
        "/api/v1/admin/memory/search",
        headers=_headers(),
        json={"query": TOKEN, "mode": "hybrid", "limit": 5},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["mode_used"] == "keyword"
    assert r.headers.get("x-brain-search-mode") == "keyword-fallback"
    assert data["count"] == 1


@pytest.mark.asyncio
async def test_semantic_falls_back_when_embedding_unavailable(
    client: AsyncClient,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _no_embed(_text: str) -> None:
        return None

    monkeypatch.setattr("app.services.memory.embed_text", _no_embed)

    db_session.add(
        Episode(
            organization_id="paperwork-labs",
            source="test:semfb",
            summary=f"{TOKEN} semantic fallback",
            importance=0.6,
        )
    )
    await db_session.commit()

    r = await client.post(
        "/api/v1/admin/memory/search",
        headers=_headers(),
        json={"query": TOKEN, "mode": "semantic", "limit": 5},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["mode_used"] == "keyword"
    assert r.headers.get("x-brain-search-mode") == "keyword-fallback"
