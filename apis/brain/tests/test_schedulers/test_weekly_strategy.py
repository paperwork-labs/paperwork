"""Brain-owned weekly strategy check-in scheduler (T1.6)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.models.scheduler_run import SchedulerRun
from app.schedulers import _history, weekly_strategy
from app.schedulers.weekly_strategy import install, run_weekly_strategy

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def test_registers_one_job_id() -> None:
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "brain_weekly_strategy"
    t = jobs[0].trigger
    assert isinstance(t, CronTrigger)
    ref = CronTrigger.from_crontab("0 9 * * 1", timezone=UTC)
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
