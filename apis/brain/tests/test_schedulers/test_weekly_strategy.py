"""Brain-owned weekly strategy check-in scheduler (T1.6)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import timezone
from unittest.mock import AsyncMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.scheduler_run import SchedulerRun
from app.schedulers import _history, weekly_strategy
from app.schedulers.weekly_strategy import install, run_weekly_strategy
from app.schedulers.n8n_mirror import N8N_MIRROR_SPECS, install as install_n8n_mirror
from app.schedulers.n8n_mirror import n8n_mirror_env_var_name


def test_flag_off_no_job_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRAIN_OWNS_WEEKLY_STRATEGY", raising=False)
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    assert len(sched.get_jobs()) == 0


def test_flag_on_registers_one_job_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAIN_OWNS_WEEKLY_STRATEGY", "true")
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "brain_weekly_strategy"
    t = jobs[0].trigger
    assert isinstance(t, CronTrigger)
    ref = CronTrigger.from_crontab("0 9 * * 1", timezone=timezone.utc)
    assert t.fields == ref.fields


def test_flag_on_suppresses_matching_n8n_shadow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRAIN_OWNS_WEEKLY_STRATEGY", "true")
    for s in N8N_MIRROR_SPECS:
        monkeypatch.delenv(n8n_mirror_env_var_name(s.job_id), raising=False)
    monkeypatch.setattr(settings, "SCHEDULER_N8N_MIRROR_ENABLED", True)
    sched = AsyncIOScheduler(timezone="UTC")
    install_n8n_mirror(sched)
    ids = {j.id for j in sched.get_jobs()}
    assert "n8n_shadow_weekly_strategy" not in ids
    assert "n8n_shadow_brain_daily" in ids


@pytest.mark.asyncio
async def test_run_success_records_scheduler_row(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context():
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())
    mock_process = AsyncMock(
        return_value={"response": "strategy body", "persona": "strategy", "model": "x"},
    )
    monkeypatch.setattr(weekly_strategy.brain_agent, "process", mock_process)
    post = AsyncMock()
    monkeypatch.setattr(weekly_strategy.slack_outbound, "post_message", post)
    await run_weekly_strategy()
    await db_session.commit()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(SchedulerRun.job_id == "brain_weekly_strategy"),
        )
    ).scalar_one()
    assert r.status == "success"
    assert r.error_text is None
    post.assert_awaited_once()
    mock_process.assert_awaited_once()
    _args, kwargs = mock_process.call_args
    assert kwargs.get("persona_pin") == "strategy"


@pytest.mark.asyncio
async def test_run_error_records_and_does_not_raise(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context():
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())

    async def _boom(*_a, **_k):
        raise ValueError("process failed")

    monkeypatch.setattr(weekly_strategy.brain_agent, "process", _boom)
    monkeypatch.setattr(weekly_strategy.slack_outbound, "post_message", AsyncMock())
    await run_weekly_strategy()
    await db_session.commit()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(SchedulerRun.job_id == "brain_weekly_strategy"),
        )
    ).scalar_one()
    assert r.status == "error"
    assert r.error_text is not None
    assert "process failed" in (r.error_text or "")
