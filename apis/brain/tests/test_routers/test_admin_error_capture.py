"""POST /admin/memory/error-capture: client errors into episodic memory (WS-82 Track C)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from app.models.episode import Episode

SECRET = "test-error-capture-secret"


@pytest.fixture(autouse=True)
def _admin_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", SECRET)


def _headers() -> dict[str, str]:
    return {"X-Brain-Secret": SECRET}


def _body(**overrides: object) -> dict:
    base: dict[str, object] = {
        "source": "studio",
        "summary": "TypeError: x is undefined",
        "fingerprint": "fp:studio:test1",
        "environment": "production",
        "severity": "error",
        "stack": "at foo.ts:12",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_error_capture_requires_secret(client: AsyncClient) -> None:
    r = await client.post("/api/v1/admin/memory/error-capture", json=_body())
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_error_capture_creates_episode(client: AsyncClient, db_session) -> None:
    r = await client.post(
        "/api/v1/admin/memory/error-capture",
        headers=_headers(),
        json=_body(),
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["deduplicated"] is False
    assert data["occurrence_count"] == 1
    ep_id = data["episode_id"]

    ep = (await db_session.execute(select(Episode).where(Episode.id == ep_id))).scalar_one()
    assert ep.organization_id == "paperwork-labs"
    assert ep.source == "error:capture:studio"
    assert ep.summary == "TypeError: x is undefined"
    assert ep.importance == pytest.approx(0.7)
    meta = dict(ep.metadata_ or {})
    assert meta["fingerprint"] == "fp:studio:test1"
    assert meta["occurrence_count"] == 1
    assert meta["severity"] == "error"
    assert "first_seen_at" in meta


@pytest.mark.asyncio
async def test_error_capture_critical_importance(client: AsyncClient, db_session) -> None:
    r = await client.post(
        "/api/v1/admin/memory/error-capture",
        headers=_headers(),
        json=_body(fingerprint="fp:crit:c1", severity="critical", summary="outage"),
    )
    assert r.status_code == 200
    ep_id = r.json()["data"]["episode_id"]
    ep = (await db_session.execute(select(Episode).where(Episode.id == ep_id))).scalar_one()
    assert ep.importance == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_error_capture_dedup_within_hour(client: AsyncClient, db_session) -> None:
    fp = "fp:dedup:abc"
    r1 = await client.post(
        "/api/v1/admin/memory/error-capture",
        headers=_headers(),
        json=_body(fingerprint=fp, summary="boom"),
    )
    assert r1.status_code == 200
    id1 = r1.json()["data"]["episode_id"]

    r2 = await client.post(
        "/api/v1/admin/memory/error-capture",
        headers=_headers(),
        json=_body(fingerprint=fp, summary="boom again"),
    )
    assert r2.status_code == 200
    d2 = r2.json()["data"]
    assert d2["deduplicated"] is True
    assert d2["episode_id"] == id1
    assert d2["occurrence_count"] == 2

    ep = (await db_session.execute(select(Episode).where(Episode.id == id1))).scalar_one()
    assert int((ep.metadata_ or {})["occurrence_count"]) == 2


@pytest.mark.asyncio
async def test_error_capture_distinct_fingerprint_new_row(client: AsyncClient, db_session) -> None:
    await client.post(
        "/api/v1/admin/memory/error-capture",
        headers=_headers(),
        json=_body(fingerprint="fp:a"),
    )
    r2 = await client.post(
        "/api/v1/admin/memory/error-capture",
        headers=_headers(),
        json=_body(fingerprint="fp:b"),
    )
    assert r2.status_code == 200
    assert r2.json()["data"]["deduplicated"] is False

    rows = (
        (
            await db_session.execute(
                select(Episode).where(Episode.source == "error:capture:studio"),
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2
