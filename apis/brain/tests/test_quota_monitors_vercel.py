"""Tests for Vercel quota monitor (snapshot + alarm helpers).

medallion: ops
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from sqlalchemy import select

from app.config import settings
from app.models.quota_snapshot import VercelQuotaSnapshot
from app.services import vercel_quota_monitor as vqm


def test_vercel_deployments_list_params_without_until() -> None:
    p = vqm.vercel_deployments_list_params("team_x", "prj_y", limit=50)
    assert p == {"teamId": "team_x", "projectId": "prj_y", "limit": "50"}
    assert "until" not in p


def test_vercel_deployments_list_params_with_until() -> None:
    p = vqm.vercel_deployments_list_params("team_x", "prj_y", until="dpl_abc")
    assert p["until"] == "dpl_abc"


def test_next_deployments_until_token_prefers_uid() -> None:
    assert vqm.next_deployments_until_token({"uid": "dpl_z", "createdAt": 123}) == "dpl_z"


def test_next_deployments_until_token_falls_back_to_created_ms() -> None:
    ms = 1_704_067_200_000
    assert vqm.next_deployments_until_token({"createdAt": ms}) == str(ms)


def test_vercel_quota_alarm_no_fire() -> None:
    fire, reasons = vqm.vercel_quota_alarm_decision(10, 100.0)
    assert not fire
    assert reasons == []


def test_vercel_quota_alarm_at_80pct_deploys() -> None:
    fire, reasons = vqm.vercel_quota_alarm_decision(80, 100.0)
    assert fire
    assert any("rolling_24h_deploy_count" in r for r in reasons)


def test_vercel_quota_alarm_at_100pct_deploys() -> None:
    fire, reasons = vqm.vercel_quota_alarm_decision(100, 100.0)
    assert fire
    assert any("rolling_24h_deploy_count" in r for r in reasons)


def test_vercel_quota_alarm_at_80pct_build_minutes() -> None:
    fire, reasons = vqm.vercel_quota_alarm_decision(0, 4800.0)
    assert fire
    assert any("rolling_30d_build_minutes" in r for r in reasons)


def test_vercel_quota_alarm_at_100pct_build_minutes() -> None:
    fire, reasons = vqm.vercel_quota_alarm_decision(0, 6000.0)
    assert fire
    assert any("rolling_30d_build_minutes" in r for r in reasons)


@pytest.mark.asyncio
async def test_persist_snapshots_adds_expected_row_count() -> None:
    """Snapshot insert shape without Postgres (CI-friendly)."""
    session = MagicMock()
    session.add_all = MagicMock()
    session.commit = AsyncMock()
    batch_at = datetime(2026, 4, 27, 12, 0, tzinfo=UTC)
    now_ms = int(batch_at.timestamp() * 1000)
    await vqm.persist_snapshots(
        session,  # type: ignore[arg-type]
        batch_at=batch_at,
        batch_id="mock-batch",
        team_id="team_t",
        now_ms=now_ms,
        per_project=[{"project_id": "prj_1", "project_name": "studio", "deploys": []}],
        team_by_window={
            1: (0, 0.0, {}),
            30: (0, 0.0, {}),
        },
    )
    session.add_all.assert_called_once()
    rows = session.add_all.call_args[0][0]
    assert len(rows) == 4
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_snapshots_inserts_team_and_project_rows(db_session) -> None:
    batch_at = datetime(2026, 4, 27, 12, 0, tzinfo=UTC)
    now_ms = int(batch_at.timestamp() * 1000)
    t0 = now_ms - 3600_000
    deploys = [
        {
            "uid": "d1",
            "createdAt": t0,
            "source": "git",
            "buildingAt": t0,
            "ready": t0 + 60_000,
        }
    ]
    await vqm.persist_snapshots(
        db_session,
        batch_at=batch_at,
        batch_id="test-batch",
        team_id="team_t",
        now_ms=now_ms,
        per_project=[{"project_id": "prj_1", "project_name": "studio", "deploys": deploys}],
        team_by_window={
            1: (1, 1.0, {"git": 1}),
            30: (1, 1.0, {"git": 1}),
        },
    )
    res = await db_session.execute(select(VercelQuotaSnapshot))
    rows = res.scalars().all()
    assert len(rows) == 4
    team_rows = [r for r in rows if r.project_id is None]
    assert len(team_rows) == 2
    assert {r.window_days for r in team_rows} == {1, 30}


class _MockResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            req = httpx.Request("GET", "https://api.vercel.com/v6/deployments")
            raise httpx.HTTPStatusError("err", request=req, response=self)  # type: ignore[arg-type]

    def json(self) -> dict:
        return self._payload


class _MockHttpxClient:
    def __init__(self, deployment_pages: list[dict]) -> None:
        self._pages = list(deployment_pages)
        self.get_calls: list[tuple[str, dict]] = []

    async def get(self, url: str, **kwargs: object) -> _MockResponse:
        params = kwargs.get("params") or {}
        assert isinstance(params, dict)
        self.get_calls.append((url, dict(params)))
        if "/v9/projects" in url:
            return _MockResponse({"projects": [{"id": "prj_1", "name": "one"}]})
        if not self._pages:
            return _MockResponse({"deployments": []})
        return _MockResponse(self._pages.pop(0))

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_fetch_deployments_second_page_sends_until(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vqm.settings, "VERCEL_API_TOKEN", "tok")
    now_ms = 1_704_067_200_000
    since_ms = now_ms - 30 * 86_400_000
    inside = now_ms - 86_400_000
    page1 = {
        "deployments": [
            {"uid": "d_new", "createdAt": now_ms - 1000, "source": "git"},
            {"uid": "d_old", "createdAt": inside, "source": "cli"},
        ]
    }
    page2 = {"deployments": []}
    mock = _MockHttpxClient([page1, page2])
    out = await vqm.fetch_deployments_since(mock, "tok", "team_t", "prj_1", since_ms)  # type: ignore[arg-type]
    assert len(out) == 2
    deploy_calls = [c for c in mock.get_calls if "/v6/deployments" in c[0]]
    assert len(deploy_calls) == 2
    assert "until" not in deploy_calls[0][1]
    assert deploy_calls[1][1].get("until") == "d_old"


@pytest.mark.asyncio
async def test_emit_quota_alarm_comments_existing_issue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vqm.settings, "GITHUB_TOKEN", "gh-token")
    monkeypatch.setattr(vqm.settings, "GITHUB_REPO", "paperwork-labs/paperwork")

    search = AsyncMock(return_value=[{"number": 42, "html_url": "http://x"}])
    comment = AsyncMock(return_value="ok")
    create = AsyncMock(return_value="created")

    monkeypatch.setattr("app.services.vercel_quota_monitor.gh.search_github_issues", search)
    monkeypatch.setattr("app.services.vercel_quota_monitor.gh.add_github_issue_comment", comment)
    monkeypatch.setattr("app.services.vercel_quota_monitor.gh.create_github_issue", create)

    await vqm._emit_quota_alarm(
        reasons=["test reason"],
        batch_id="b1",
        team_24_deploys=99,
        team_30_build=0.0,
        excerpt={"k": "v"},
    )
    search.assert_awaited_once()
    comment.assert_awaited_once()
    create.assert_not_called()


@pytest.mark.asyncio
async def test_admin_vercel_quota_endpoint(
    client,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "test-secret")
    batch_at = datetime(2026, 4, 27, 15, 0, tzinfo=UTC)
    db_session.add(
        VercelQuotaSnapshot(
            created_at=batch_at,
            project_id=None,
            project_name="(team)",
            window_days=1,
            deploy_count=3,
            build_minutes=1.5,
            source_breakdown={"git": 3},
            meta={"batch_id": "x"},
        )
    )
    await db_session.commit()

    res = await client.get(
        "/api/v1/admin/vercel-quota",
        headers={"X-Brain-Secret": "test-secret"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    data = body["data"]
    assert data["count"] >= 1
    assert any(s.get("project_name") == "(team)" for s in data["snapshots"])
