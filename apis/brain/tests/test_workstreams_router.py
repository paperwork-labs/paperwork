"""``POST /api/v1/workstreams/reorder`` — auth, validation, PR payload."""

from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app as fastapi_app
from app.schemas.workstream import Workstream, WorkstreamsFile, workstreams_file_to_json_dict
from app.services import workstream_reorder as reorder_svc


def _minimal_file() -> WorkstreamsFile:
    streams = [
        Workstream(
            id="WS-99-a",
            title="Abc title for reorder",
            track="Z",
            priority=0,
            status="pending",
            percent_done=0,
            owner="brain",
            brief_tag="track:reorder-a",
            blockers=[],
            last_pr=None,
            last_activity="2026-04-27T12:00:00Z",
            last_dispatched_at=None,
            notes="",
            estimated_pr_count=1,
            github_actions_workflow=None,
            related_plan=None,
        ),
        Workstream(
            id="WS-99-b",
            title="Bcd title for reorder",
            track="Z",
            priority=1,
            status="pending",
            percent_done=0,
            owner="brain",
            brief_tag="track:reorder-b",
            blockers=[],
            last_pr=None,
            last_activity="2026-04-27T12:00:00Z",
            last_dispatched_at=None,
            notes="",
            estimated_pr_count=1,
            github_actions_workflow=None,
            related_plan=None,
        ),
    ]
    return WorkstreamsFile(version=1, updated="2026-04-27T12:00:00Z", workstreams=streams)


@pytest.mark.asyncio
async def test_reorder_401_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_INTERNAL_TOKEN", "secret-reorder-token")
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/workstreams/reorder",
            json={"ordered_ids": ["WS-99-a", "WS-99-b"]},
        )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_reorder_422_id_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_INTERNAL_TOKEN", "secret-reorder-token")
    monkeypatch.setattr(
        "app.services.workstream_reorder.load_workstreams_file",
        lambda **_: _minimal_file(),
    )
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/workstreams/reorder",
            headers={"Authorization": "Bearer secret-reorder-token"},
            json={"ordered_ids": ["WS-99-a"]},
        )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_reorder_202_and_pr_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_INTERNAL_TOKEN", "secret-reorder-token")
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "gh-test-token")
    monkeypatch.setattr(settings, "GITHUB_REPO", "paperwork-labs/paperwork")

    monkeypatch.setattr(
        "app.services.workstream_reorder.load_workstreams_file",
        lambda **_: _minimal_file(),
    )

    captured: dict[str, str] = {}

    async def _fake_open(ordered_ids: list[str]) -> dict:  # type: ignore[type-arg]
        f = _minimal_file()
        by_id = {w.id: w for w in f.workstreams}
        new_order = [by_id[i] for i in ordered_ids]
        for i, w in enumerate(new_order):
            new_order[i] = w.model_copy(update={"priority": i})
        nf = WorkstreamsFile(version=1, updated="2026-04-27T13:00:00Z", workstreams=new_order)
        payload = json.dumps(workstreams_file_to_json_dict(nf), indent=2) + "\n"
        captured["json"] = payload
        return {"number": 4242, "html_url": "https://github.com/paperwork-labs/paperwork/pull/4242"}

    monkeypatch.setattr(reorder_svc, "open_reorder_workstreams_pr", _fake_open)

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/workstreams/reorder",
            headers={"Authorization": "Bearer secret-reorder-token"},
            json={"ordered_ids": ["WS-99-b", "WS-99-a"]},
        )

    assert r.status_code == 202
    body = r.json()
    assert body["pr_number"] == 4242
    assert "pull/4242" in body["pr_url"]

    data = json.loads(captured["json"])
    ids = [w["id"] for w in data["workstreams"]]
    assert ids == ["WS-99-b", "WS-99-a"]
    assert [w["priority"] for w in data["workstreams"]] == [0, 1]
