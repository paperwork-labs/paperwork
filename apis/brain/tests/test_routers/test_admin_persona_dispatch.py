"""Admin persona autopilot dispatch create (PB-3)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from app.models.episode import Episode

SECRET = "test-persona-dispatch-secret"


@pytest.fixture(autouse=True)
def _admin_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", SECRET)


def _headers() -> dict[str, str]:
    return {"X-Brain-Secret": SECRET}


@pytest.mark.asyncio
async def test_persona_dispatch_happy_path(client: AsyncClient, db_session) -> None:
    extra_meta = {"ticket": "PB-3"}
    body = {
        "task_title": "Fix CI flake",
        "task_description": "Stabilize the flaky router test in brain.",
        "target_repo": "paperwork-labs/paperwork",
        "target_branch_base": "main",
        "suggested_branch_name": "fix/ci-flake",
        "estimated_complexity": "medium",
        "requires_founder_review": True,
        "metadata": extra_meta,
    }
    r = await client.post(
        "/api/v1/admin/personas/cfo/dispatch",
        headers=_headers(),
        json=body,
    )
    assert r.status_code == 200
    data = r.json()["data"]
    task_id = data["task_id"]
    assert task_id.isdigit()
    assert data["status"] == "pending"
    assert data["persona"] == "cfo"
    assert data["requires_founder_review"] is True
    assert data["created_at"].endswith("Z")

    ep = (await db_session.execute(select(Episode).where(Episode.id == int(task_id)))).scalar_one()
    assert ep.organization_id == "paperwork-labs"
    assert ep.source == "autopilot:dispatch:cfo"
    assert ep.summary == "Fix CI flake"
    assert ep.persona == "cfo"
    assert ep.importance == pytest.approx(0.7)
    meta = ep.metadata_
    assert meta["status"] == "pending"
    assert meta["persona"] == "cfo"
    assert meta["task_title"] == "Fix CI flake"
    assert meta["task_description"] == body["task_description"]
    assert meta["target_repo"] == "paperwork-labs/paperwork"
    assert meta["target_branch_base"] == "main"
    assert meta["suggested_branch_name"] == "fix/ci-flake"
    assert meta["estimated_complexity"] == "medium"
    assert meta["requires_founder_review"] is True
    assert meta["created_by"] == "cfo"
    assert meta["ticket"] == "PB-3"
    assert meta["created_at"] == data["created_at"]


@pytest.mark.asyncio
async def test_persona_dispatch_unknown_persona(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/admin/personas/not-a-real-persona-slug/dispatch",
        headers=_headers(),
        json={
            "task_title": "x",
            "task_description": "y",
        },
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_persona_dispatch_requires_secret(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/admin/personas/cfo/dispatch",
        json={"task_title": "t", "task_description": "d"},
    )
    assert r.status_code == 401
    r2 = await client.post(
        "/api/v1/admin/personas/cfo/dispatch",
        headers={"X-Brain-Secret": "wrong"},
        json={"task_title": "t", "task_description": "d"},
    )
    assert r2.status_code == 401


@pytest.mark.asyncio
async def test_persona_dispatch_invalid_body(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/admin/personas/cfo/dispatch",
        headers=_headers(),
        json={"task_description": "missing title"},
    )
    assert r.status_code == 422

    r2 = await client.post(
        "/api/v1/admin/personas/cfo/dispatch",
        headers=_headers(),
        json={
            "task_title": "ok",
            "task_description": "ok",
            "estimated_complexity": "xlarge",
        },
    )
    assert r2.status_code == 422


@pytest.mark.asyncio
async def test_persona_dispatch_no_founder_review_flag_when_false(
    client: AsyncClient,
    db_session,
) -> None:
    r = await client.post(
        "/api/v1/admin/personas/infra-ops/dispatch",
        headers=_headers(),
        json={
            "task_title": "Quick patch",
            "task_description": "Bump timeout.",
            "requires_founder_review": False,
        },
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert "requires_founder_review" not in data
    ep = (
        await db_session.execute(
            select(Episode).where(Episode.id == int(data["task_id"])),
        )
    ).scalar_one()
    assert ep.importance == pytest.approx(0.5)
    assert ep.metadata_["requires_founder_review"] is False


@pytest.mark.asyncio
async def test_persona_dispatch_default_target_repo(client: AsyncClient, db_session) -> None:
    r = await client.post(
        "/api/v1/admin/personas/engineering/dispatch",
        headers=_headers(),
        json={"task_title": "Task", "task_description": "Desc"},
    )
    assert r.status_code == 200
    ep = (
        await db_session.execute(
            select(Episode).where(Episode.id == int(r.json()["data"]["task_id"])),
        )
    ).scalar_one()
    assert ep.metadata_["target_repo"] == "paperwork-labs/paperwork"
