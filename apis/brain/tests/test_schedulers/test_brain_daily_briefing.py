"""Brain-owned daily briefing scheduler (T1.2)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.models.scheduler_run import SchedulerRun
from app.schedulers import _history, brain_daily_briefing
from app.schedulers.brain_daily_briefing import install, run_daily_briefing

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def test_registers_one_job_id() -> None:
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "brain_daily_briefing"
    t = jobs[0].trigger
    assert isinstance(t, CronTrigger)
    ref = CronTrigger.from_crontab("0 7 * * *", timezone="UTC")
    assert t.fields == ref.fields


@pytest.mark.asyncio
async def test_run_success_records_scheduler_row(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context():
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())
    mock_process = AsyncMock(return_value={"response": "brief body", "persona": "ea", "model": "x"})
    monkeypatch.setattr(brain_daily_briefing.brain_agent, "process", mock_process)
    post = AsyncMock()
    monkeypatch.setattr(brain_daily_briefing.slack_outbound, "post_message", post)
    await run_daily_briefing()
    await db_session.commit()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(SchedulerRun.job_id == "brain_daily_briefing")
        )
    ).scalar_one()
    assert r.status == "success"
    assert r.error_text is None
    post.assert_awaited_once()


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

    monkeypatch.setattr(brain_daily_briefing.brain_agent, "process", _boom)
    monkeypatch.setattr(brain_daily_briefing.slack_outbound, "post_message", AsyncMock())
    await run_daily_briefing()
    await db_session.commit()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(SchedulerRun.job_id == "brain_daily_briefing")
        )
    ).scalar_one()
    assert r.status == "error"
    assert r.error_text is not None
    assert "process failed" in (r.error_text or "")
