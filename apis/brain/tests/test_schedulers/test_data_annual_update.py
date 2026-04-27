"""Brain-owned annual tax data update scheduler (Track K / P2.10)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.scheduler_run import SchedulerRun
from app.schedulers import _history, data_annual_update
from app.schedulers.n8n_mirror import N8N_MIRROR_SPECS, install as install_n8n_mirror
from app.schedulers.n8n_mirror import n8n_mirror_env_var_name
from app.schedulers.data_annual_update import _build_message, install, run_data_annual_update


def test_flag_off_no_job_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRAIN_OWNS_ANNUAL_DATA", raising=False)
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    assert len(sched.get_jobs()) == 0


def test_flag_on_registers_one_job_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAIN_OWNS_ANNUAL_DATA", "true")
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "brain_data_annual_update"
    t = jobs[0].trigger
    assert isinstance(t, CronTrigger)
    ref = CronTrigger.from_crontab("0 9 1 10 *", timezone=timezone.utc)
    assert t.fields == ref.fields


def test_flag_on_suppresses_matching_n8n_shadow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRAIN_OWNS_ANNUAL_DATA", "true")
    for s in N8N_MIRROR_SPECS:
        monkeypatch.delenv(n8n_mirror_env_var_name(s.job_id), raising=False)
    monkeypatch.setattr(settings, "SCHEDULER_N8N_MIRROR_ENABLED", True)
    sched = AsyncIOScheduler(timezone="UTC")
    install_n8n_mirror(sched)
    ids = {j.id for j in sched.get_jobs()}
    assert "n8n_shadow_annual_data" not in ids
    assert "n8n_shadow_brain_daily" in ids


def test_build_message_includes_next_year() -> None:
    fixed = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
    text = _build_message(fixed)
    assert "TY2027" in text
    assert "Annual Tax Data Update — TY2027" in text
    assert "EXTRACT_TAX_YEAR=2027" in text


def test_build_message_includes_all_ten_checklist_steps() -> None:
    fixed = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
    text = _build_message(fixed)
    assert "1. IRS Revenue Procedure for TY2027" in text
    assert "2. Download new Tax Foundation XLSX" in text
    assert "3. Run formation update:" in text
    assert "4. Run full review:" in text
    assert "5. Run test suite:" in text
    assert "6. Add known-good anchor values for TY2027" in text
    assert "7. Run `pnpm review:approve`" in text
    assert "8. Create PR and merge to main" in text
    assert "9. Verify CI passes on the PR" in text
    assert "10. Post confirmation to #engineering when done" in text
    assert "Tax Foundation State Income Tax Rates" in text
    assert "Reply in this thread with progress updates" in text


@pytest.mark.asyncio
async def test_run_skips_when_slack_token_missing(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context():
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())
    monkeypatch.setattr(settings, "SLACK_BOT_TOKEN", "", raising=False)
    await run_data_annual_update()
    await db_session.commit()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(SchedulerRun.job_id == "brain_data_annual_update"),
        )
    ).scalar_one()
    assert r.status == "skipped"


@pytest.mark.asyncio
async def test_run_success_posts_to_engineering(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context():
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())
    monkeypatch.setattr(settings, "SLACK_BOT_TOKEN", "xoxb-test", raising=False)
    post = AsyncMock(return_value={"ok": True, "ts": "1.0"})
    monkeypatch.setattr(data_annual_update.slack_outbound, "post_message", post)
    await run_data_annual_update()
    await db_session.commit()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(SchedulerRun.job_id == "brain_data_annual_update"),
        )
    ).scalar_one()
    assert r.status == "success"
    assert r.error_text is None
    post.assert_awaited_once()
    assert post.await_args is not None
    _, kwargs = post.await_args
    assert kwargs.get("channel_id") == "C0ALLEKR9FZ"
    assert kwargs.get("username") == "Engineering"
    assert kwargs.get("icon_emoji") == ":calendar:"


@pytest.mark.asyncio
async def test_run_slack_failure_records_error(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context():
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())
    monkeypatch.setattr(settings, "SLACK_BOT_TOKEN", "xoxb-test", raising=False)
    post = AsyncMock(return_value={"ok": False, "error": "channel_not_found"})
    monkeypatch.setattr(data_annual_update.slack_outbound, "post_message", post)
    with pytest.raises(RuntimeError, match="Slack post failed"):
        await run_data_annual_update()
    await db_session.commit()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(SchedulerRun.job_id == "brain_data_annual_update"),
        )
    ).scalar_one()
    assert r.status == "error"
    assert r.error_text is not None
    assert "channel_not_found" in (r.error_text or "")
