"""Tests for data_source_monitor (Track K — P2.8)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import httpx
import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.scheduler_run import SchedulerRun
from app.schedulers import _history, data_source_monitor
from app.schedulers.data_source_monitor import install, run_data_source_monitor, _signed32_hash
from app.schedulers.n8n_mirror import N8N_MIRROR_SPECS, install as install_n8n_mirror
from app.schedulers.n8n_mirror import n8n_mirror_env_var_name


@pytest.fixture(autouse=True)
def _reset_mem_hashes() -> None:
    data_source_monitor._mem_hashes.clear()
    yield
    data_source_monitor._mem_hashes.clear()


def test_flag_off_no_job_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRAIN_OWNS_DATA_SOURCE_MONITOR", raising=False)
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    assert len(sched.get_jobs()) == 0


def test_flag_on_registers_one_job_id(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import timezone

    monkeypatch.setenv("BRAIN_OWNS_DATA_SOURCE_MONITOR", "true")
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "brain_data_source_monitor"
    t = jobs[0].trigger
    assert isinstance(t, CronTrigger)
    ref = CronTrigger.from_crontab("0 6 * * 1", timezone=timezone.utc)
    assert t.fields == ref.fields


def test_flag_on_suppresses_matching_n8n_shadow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRAIN_OWNS_DATA_SOURCE_MONITOR", "true")
    for s in N8N_MIRROR_SPECS:
        monkeypatch.delenv(n8n_mirror_env_var_name(s.job_id), raising=False)
    monkeypatch.setattr(settings, "SCHEDULER_N8N_MIRROR_ENABLED", True)
    sched = AsyncIOScheduler(timezone="UTC")
    install_n8n_mirror(sched)
    ids = {j.id for j in sched.get_jobs()}
    assert "n8n_shadow_data_source_monitor" not in ids
    assert "n8n_shadow_brain_daily" in ids


def test_signed32_hash_matches_js_reference() -> None:
    assert _signed32_hash("") == "0"
    assert _signed32_hash("abc") == "96354"
    assert _signed32_hash("hello") == "99162322"
    assert _signed32_hash("test longer string 123") == str(-704007700)


@pytest.mark.asyncio
async def test_first_run_baseline_slack_post(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context():
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())
    monkeypatch.setattr(settings, "SLACK_BOT_TOKEN", "xoxb-test", raising=False)

    async def _one_body(_client: httpx.AsyncClient, _url: str) -> str:
        return "same text"

    monkeypatch.setattr(data_source_monitor, "_fetch_one", _one_body)
    post = AsyncMock(return_value={"ok": True, "ts": "1.0"})
    monkeypatch.setattr(data_source_monitor.slack_outbound, "post_message", post)

    await run_data_source_monitor()
    await db_session.commit()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(SchedulerRun.job_id == "brain_data_source_monitor"),
        )
    ).scalar_one()
    assert r.status == "success"
    post.assert_awaited_once()
    text = str(post.await_args.kwargs.get("text") or "")
    assert "Data Source Monitor — Baseline Set" in text
    assert "Monitoring 5 source(s)" in text


@pytest.mark.asyncio
async def test_no_changes_no_errors_skips(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context():
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())
    monkeypatch.setattr(settings, "SLACK_BOT_TOKEN", "xoxb-test", raising=False)

    async def _one_body(_client: httpx.AsyncClient, _url: str) -> str:
        return "same text"

    monkeypatch.setattr(data_source_monitor, "_fetch_one", _one_body)
    post = AsyncMock(return_value={"ok": True, "ts": "1.0"})
    monkeypatch.setattr(data_source_monitor.slack_outbound, "post_message", post)

    await run_data_source_monitor()
    await db_session.commit()
    post.reset_mock()

    await run_data_source_monitor()
    await db_session.commit()
    r2 = (
        await db_session.execute(
            select(SchedulerRun)
            .where(SchedulerRun.job_id == "brain_data_source_monitor")
            .order_by(SchedulerRun.finished_at.desc())
            .limit(1),
        )
    ).scalar_one()
    assert r2.status == "skipped"
    post.assert_not_awaited()


@pytest.mark.asyncio
async def test_change_detected_posts_alert(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context():
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())
    monkeypatch.setattr(settings, "SLACK_BOT_TOKEN", "xoxb-test", raising=False)

    income = "https://taxfoundation.org/data/all/state/state-income-tax-rates"
    round_no = 0

    async def _fetch_sequential(_client: httpx.AsyncClient, url: str) -> str:
        nonlocal round_no
        if url == income:
            return "v1" if round_no == 0 else "v2"
        return "v1"

    monkeypatch.setattr(data_source_monitor, "_fetch_one", _fetch_sequential)
    post = AsyncMock(return_value={"ok": True, "ts": "1.0"})
    monkeypatch.setattr(data_source_monitor.slack_outbound, "post_message", post)

    await run_data_source_monitor()
    await db_session.commit()
    assert post.await_count == 1
    round_no = 1
    post.reset_mock()

    await run_data_source_monitor()
    await db_session.commit()
    post.assert_awaited_once()
    text = str(post.await_args.kwargs.get("text") or "")
    assert "Data Source Changes Detected" in text
    assert "pnpm parse:tax" in text


@pytest.mark.asyncio
async def test_fetch_error_posts_warning(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context():
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())
    monkeypatch.setattr(settings, "SLACK_BOT_TOKEN", "xoxb-test", raising=False)

    async def _fail_income(_client: httpx.AsyncClient, url: str) -> str:
        if "income-tax-rates" in url:
            raise httpx.HTTPError("unit test fetch failure")
        return "ok body"

    monkeypatch.setattr(data_source_monitor, "_fetch_one", _fail_income)
    post = AsyncMock(return_value={"ok": True, "ts": "1.0"})
    monkeypatch.setattr(data_source_monitor.slack_outbound, "post_message", post)

    await run_data_source_monitor()
    await db_session.commit()
    post.assert_awaited_once()
    text = str(post.await_args.kwargs.get("text") or "")
    assert "Source Fetch Errors" in text
    assert ":warning:" in text
    assert "Tax Foundation - State Income Tax Rates" in text
