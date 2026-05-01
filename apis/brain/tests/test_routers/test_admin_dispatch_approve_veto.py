"""Admin autopilot dispatch approve / veto (WS-82)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from app.models.episode import Episode

SECRET = "test-dispatch-secret"


@pytest.fixture(autouse=True)
def _admin_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", SECRET)


def _headers() -> dict[str, str]:
    return {"X-Brain-Secret": SECRET}


@pytest.mark.asyncio
async def test_approve_dispatch_happy_path(client: AsyncClient, db_session) -> None:
    db_session.add(
        Episode(
            organization_id="paperwork-labs",
            source="autopilot:dispatch",
            summary="Pending dispatch",
            importance=0.6,
            metadata_={"status": "pending", "task": "x"},
        )
    )
    await db_session.commit()
    res = await db_session.execute(select(Episode).where(Episode.source == "autopilot:dispatch"))
    ep = res.scalar_one()

    r = await client.post(
        f"/api/v1/admin/dispatch/{ep.id}/approve",
        headers=_headers(),
        json={"note": "lgtm"},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["task_id"] == str(ep.id)
    assert data["status"] == "approved"
    assert data["approved_by"] == "founder"
    assert data["approved_at"].endswith("Z")

    await db_session.refresh(ep)
    assert ep.metadata_["status"] == "approved"
    assert ep.metadata_["approval_note"] == "lgtm"
    assert ep.metadata_["approved_by"] == "founder"

    audit = (
        (
            await db_session.execute(
                select(Episode).where(Episode.source == "autopilot:approval"),
            )
        )
        .scalars()
        .all()
    )
    assert len(audit) == 1
    assert audit[0].metadata_.get("dispatch_episode_id") == ep.id


@pytest.mark.asyncio
async def test_veto_dispatch_happy_path(client: AsyncClient, db_session) -> None:
    db_session.add(
        Episode(
            organization_id="paperwork-labs",
            source="autopilot:probe",
            summary="Another pending",
            importance=0.5,
            metadata_={"status": "pending"},
        )
    )
    await db_session.commit()
    res = await db_session.execute(select(Episode).where(Episode.source == "autopilot:probe"))
    ep = res.scalar_one()

    r = await client.post(
        f"/api/v1/admin/dispatch/{ep.id}/veto",
        headers=_headers(),
        json={"reason": "risky"},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["task_id"] == str(ep.id)
    assert data["status"] == "vetoed"
    assert data["vetoed_by"] == "founder"
    assert data["veto_reason"] == "risky"
    assert data["vetoed_at"].endswith("Z")

    await db_session.refresh(ep)
    assert ep.metadata_["status"] == "vetoed"
    assert ep.metadata_["veto_reason"] == "risky"

    audit = (
        await db_session.execute(select(Episode).where(Episode.source == "autopilot:veto"))
    ).scalar_one_or_none()
    assert audit is not None
    assert audit.metadata_.get("dispatch_episode_id") == ep.id


@pytest.mark.asyncio
async def test_dispatch_endpoints_require_secret(client: AsyncClient) -> None:
    r = await client.post("/api/v1/admin/dispatch/1/approve")
    assert r.status_code == 401
    r2 = await client.post(
        "/api/v1/admin/dispatch/1/approve",
        headers={"X-Brain-Secret": "wrong"},
    )
    assert r2.status_code == 401


@pytest.mark.asyncio
async def test_dispatch_unknown_task(client: AsyncClient, db_session) -> None:
    r = await client.post(
        "/api/v1/admin/dispatch/999999/approve",
        headers=_headers(),
    )
    assert r.status_code == 404

    db_session.add(
        Episode(
            organization_id="paperwork-labs",
            source="brain:slack",
            summary="not autopilot",
            importance=0.5,
            metadata_={"status": "pending"},
        )
    )
    await db_session.commit()
    res = await db_session.execute(select(Episode).where(Episode.source == "brain:slack"))
    ep = res.scalar_one()
    r2 = await client.post(
        f"/api/v1/admin/dispatch/{ep.id}/veto",
        headers=_headers(),
        json={},
    )
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_dispatch_conflict_not_pending(client: AsyncClient, db_session) -> None:
    db_session.add(
        Episode(
            organization_id="paperwork-labs",
            source="autopilot:dispatch",
            summary="x",
            importance=0.5,
            metadata_={"status": "approved", "approved_at": "2026-01-01T00:00:00Z"},
        )
    )
    db_session.add(
        Episode(
            organization_id="paperwork-labs",
            source="autopilot:dispatch",
            summary="y",
            importance=0.5,
            metadata_={"status": "vetoed"},
        )
    )
    await db_session.commit()
    rows = (
        (await db_session.execute(select(Episode).where(Episode.summary.in_(["x", "y"]))))
        .scalars()
        .all()
    )
    by_summary = {e.summary: e for e in rows}

    r1 = await client.post(
        f"/api/v1/admin/dispatch/{by_summary['x'].id}/approve",
        headers=_headers(),
    )
    assert r1.status_code == 409

    r2 = await client.post(
        f"/api/v1/admin/dispatch/{by_summary['y'].id}/veto",
        headers=_headers(),
        json={"note": "nope"},
    )
    assert r2.status_code == 409
