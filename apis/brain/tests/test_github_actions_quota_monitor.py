"""Tests for GitHub Actions quota monitor (billing + cache snapshots)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import app.services.github_actions_quota_monitor as ghq


def test_parse_billing_maps_totals_and_breakdowns() -> None:
    body = {
        "total_minutes_used": 1500,
        "included_minutes": 3000,
        "total_paid_minutes_used": 0,
        "minutes_used_breakdown": {"UBUNTU": {"total_ms": 1}},
        "total_paid_minutes_used_breakdown": {"UBUNTU": 0},
    }
    parsed = ghq._parse_billing_body(body)
    assert parsed["minutes_used"] == 1500.0
    assert parsed["included_minutes"] == 3000
    assert parsed["minutes_limit"] == 3000.0
    assert parsed["paid_minutes_used"] == 0.0
    assert parsed["minutes_used_breakdown"] == {"UBUNTU": {"total_ms": 1}}
    assert parsed["total_paid_minutes_used_breakdown"] == {"UBUNTU": 0}


def test_github_actions_quota_alarm_private_high_usage() -> None:
    breach, reasons = ghq.github_actions_quota_alarm_decision(
        is_public=False,
        minutes_used=1650.0,
        included_minutes=3000,
        paid_minutes_used=None,
    )
    assert breach is True
    assert any("1600" in r or "included" in r for r in reasons)


def test_github_actions_quota_alarm_public_paid_trigger() -> None:
    breach, reasons = ghq.github_actions_quota_alarm_decision(
        is_public=True,
        minutes_used=0.0,
        included_minutes=None,
        paid_minutes_used=12.5,
    )
    assert breach is True
    assert any("paid" in r.lower() for r in reasons)


def test_github_actions_quota_alarm_public_clean() -> None:
    breach, _reasons = ghq.github_actions_quota_alarm_decision(
        is_public=True,
        minutes_used=0.0,
        included_minutes=None,
        paid_minutes_used=0.0,
    )
    assert breach is False


def test_registers_daily_cron_utc() -> None:
    sched = AsyncIOScheduler(timezone="UTC")
    import importlib

    mod = importlib.import_module("app.schedulers.github_actions_quota_monitor")

    mod.install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == mod.JOB_ID
    trig = jobs[0].trigger
    assert isinstance(trig, CronTrigger)


@pytest.mark.asyncio
async def test_collect_merges_repo_cache_and_billing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ghq.settings, "GITHUB_TOKEN", "tok", raising=False)
    monkeypatch.setattr(ghq.settings, "GITHUB_REPO", "acme/widget", raising=False)

    routes = {
        "/repos/acme/widget": {
            "private": False,
            "visibility": "public",
        },
        "/repos/acme/widget/actions/cache/usage": {
            "active_caches_size_in_bytes": 1000,
            "active_caches_count": 2,
        },
        "/repos/acme/widget/settings/billing/actions": {
            "total_minutes_used": 42,
            "included_minutes": 2000,
            "total_paid_minutes_used": 0,
            "minutes_used_breakdown": {"UBUNTU": 40},
            "total_paid_minutes_used_breakdown": {},
        },
    }

    async def fake_get(*args: object, **kwargs: object) -> MagicMock:
        url = str(
            kwargs.get("url")
            if "url" in kwargs
            else (args[1] if len(args) >= 2 else (args[0] if args else ""))
        )
        r = MagicMock()
        parsed = routes.get(url)
        if parsed is None:
            r.status_code = 404
            r.text = "nope"
        else:
            r.status_code = 200
            r.json = MagicMock(return_value=parsed)
        return r

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=fake_get)
    mock_client.aclose = AsyncMock()

    out = await ghq.collect_github_actions_quota_payload(http_client=mock_client)
    assert out["repo"] == "acme/widget"
    assert out["is_public"] is True
    assert out["minutes_used"] == 42.0
    assert out["cache_size_bytes"] == 1000
    assert out["cache_count"] == 2
    assert out.get("extra_json", {}).get("billing_source") == "repo_settings_billing_actions"


@pytest.mark.asyncio
async def test_run_tick_skips_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ghq.settings, "GITHUB_TOKEN", "", raising=False)
    with patch.object(ghq, "persist_github_actions_quota_snapshot", new=AsyncMock()) as pm:
        await ghq.run_github_actions_quota_monitor_tick()
        pm.assert_not_awaited()
