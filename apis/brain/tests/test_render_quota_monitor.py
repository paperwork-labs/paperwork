"""Tests for Render quota monitor helpers and admin endpoint.

medallion: ops
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import settings
from app.models.render_quota_snapshot import RenderQuotaSnapshot
from app.services import render_quota_monitor as rqm


def test_calendar_month_start_and_label() -> None:
    dt = datetime(2026, 4, 15, 13, 30, tzinfo=UTC)
    assert rqm.current_month_label_utc(dt) == "2026-04"
    start = rqm.calendar_month_start_utc(dt)
    assert start.year == 2026 and start.month == 4 and start.day == 1


def test_deploy_pipeline_minutes_good() -> None:
    t0 = datetime(2026, 4, 28, 1, 0, tzinfo=UTC)
    t1 = datetime(2026, 4, 28, 1, 3, tzinfo=UTC)
    d = {
        "startedAt": t0.isoformat().replace("+00:00", "Z"),
        "finishedAt": t1.isoformat().replace("+00:00", "Z"),
    }
    assert rqm.deploy_pipeline_minutes(d) == pytest.approx(3.0)


def test_render_quota_alarm_no_fire() -> None:
    fire, reasons = rqm.render_quota_alarm_decision(100.0, 500.0)
    assert not fire
    assert reasons == []


def test_render_quota_alarm_above_80pct() -> None:
    fire, reasons = rqm.render_quota_alarm_decision(401.0, 500.0)
    assert fire
    assert any("ratio=" in r for r in reasons)


def test_extract_pipeline_from_usage_nested() -> None:
    body = {"usage": {"pipelineMinutes": 222.0}}
    assert rqm._extract_pipeline_minutes_from_usage(body) == 222.0


@pytest.mark.asyncio
async def test_emit_render_quota_alarm_comments_existing_issue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rqm.settings, "GITHUB_TOKEN", "gh-token")
    monkeypatch.setattr(rqm.settings, "GITHUB_REPO", "paperwork-labs/paperwork")

    search = AsyncMock(return_value=[{"number": 77, "html_url": "http://x"}])
    comment = AsyncMock(return_value="ok")
    create = AsyncMock(return_value="created")

    monkeypatch.setattr("app.tools.github.search_github_issues", search)
    monkeypatch.setattr("app.tools.github.add_github_issue_comment", comment)
    monkeypatch.setattr("app.tools.github.create_github_issue", create)

    await rqm.emit_render_quota_alarm(
        reasons=["test reason"],
        snapshot_id="snap-1",
        pipeline_used=430.0,
        pipeline_included=500.0,
        excerpt={"k": "v"},
    )
    search.assert_awaited_once()
    comment.assert_awaited_once()
    create.assert_not_called()


@pytest.mark.asyncio
async def test_tick_skips_without_render_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rqm.settings, "RENDER_API_KEY", "")
    await rqm.run_render_quota_monitor_tick()


@pytest.mark.asyncio
async def test_admin_render_quota_endpoint(
    client,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "test-secret")
    rec = datetime(2026, 4, 28, 15, 0, tzinfo=UTC)
    db_session.add(
        RenderQuotaSnapshot(
            recorded_at=rec,
            month="2026-04",
            pipeline_minutes_used=120.0,
            pipeline_minutes_included=500.0,
            bandwidth_gb_used=None,
            bandwidth_gb_included=None,
            unbilled_charges_usd=None,
            services_count=3,
            datastores_storage_gb=None,
            workspace_plan=None,
            derived_from="deploy_sum",
            extra_json={
                "top_services_by_minutes": [
                    {"service_id": "srv-x", "name": "api", "approx_minutes": 50.0},
                ],
            },
        )
    )
    await db_session.commit()

    res = await client.get(
        "/api/v1/admin/render-quota",
        headers={"X-Brain-Secret": "test-secret"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    data = body["data"]
    snap = data["snapshot"]
    assert snap["month"] == "2026-04"
    assert snap["derived_from"] == "deploy_sum"
    assert data["top_services_by_minutes"][0]["name"] == "api"


class _Resp:
    def __init__(self, status: int, payload: object) -> None:
        self.status_code = status
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"mock HTTP {self.status_code}")

    def json(self) -> object:
        return self._payload


class _HTTPX:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get(self, url: str, **_kwargs: object) -> _Resp:
        self.calls.append(url)
        t0 = datetime(2026, 4, 28, 12, 0, tzinfo=UTC)
        t1 = datetime(2026, 4, 28, 12, 2, tzinfo=UTC)
        svc_id = "srv-test123"
        if "billing/usage" in url:
            return _Resp(404, {})
        if "/metrics/bandwidth" in url:
            return _Resp(401, {})
        if url.rstrip("/").endswith("/services"):
            return _Resp(
                200,
                {
                    "service": [
                        {"service": {"id": svc_id, "name": "x", "type": "web"}},
                    ],
                    "cursor": None,
                },
            )
        if f"/services/{svc_id}/deploys" in url:
            return _Resp(
                200,
                {
                    "deploys": [
                        {
                            "startedAt": t0.isoformat().replace("+00:00", "Z"),
                            "finishedAt": t1.isoformat().replace("+00:00", "Z"),
                        },
                    ],
                    "cursor": None,
                },
            )
        return _Resp(404, {})

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_run_tick_snapshot_row(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rqm.settings, "RENDER_API_KEY", "tok")
    monkeypatch.setattr(rqm.settings, "RENDER_PIPELINE_MINUTES_INCLUDED", 500.0)

    sess = MagicMock()
    sess.add = MagicMock()
    sess.commit = AsyncMock()
    sess.__aenter__ = AsyncMock(return_value=sess)
    sess.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=sess)
    monkeypatch.setattr(rqm, "async_session_factory", factory)

    async def noop_alarm(**_k: object) -> None:
        return None

    monkeypatch.setattr(rqm, "_emit_github", noop_alarm)

    httpx_stub = _HTTPX()
    tick_at = datetime(2026, 4, 28, 15, 0, tzinfo=UTC)
    await rqm.run_render_quota_monitor_tick(http_client=httpx_stub, at=tick_at)  # type: ignore[arg-type]

    sess.add.assert_called_once()
    row = sess.add.call_args[0][0]
    assert isinstance(row, RenderQuotaSnapshot)
    assert row.pipeline_minutes_used >= 1.99
    assert row.derived_from == "deploy_sum"
    sess.commit.assert_awaited_once()
