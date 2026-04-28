"""Tests for ``qa_security_scan`` scheduler (WS-19)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scheduler_run import SchedulerRun
from app.schedulers import _history, qa_security_scan
from app.schedulers.qa_security_scan import install, run_qa_security_scan


def test_install_registers_monday_job() -> None:
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "qa_security_scan"
    t = jobs[0].trigger
    assert isinstance(t, CronTrigger)
    ref = CronTrigger(day_of_week="mon", hour=14, minute=0, timezone="UTC")
    assert t.fields == ref.fields


@pytest.mark.asyncio
async def test_run_invokes_brain_process_with_qa_persona(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context():
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())
    mock_process = AsyncMock(return_value={"response": "ok", "persona": "qa"})
    monkeypatch.setattr(qa_security_scan.brain_agent, "process", mock_process)
    await run_qa_security_scan()
    await db_session.commit()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(SchedulerRun.job_id == "qa_security_scan"),
        )
    ).scalar_one()
    assert r.status == "success"
    mock_process.assert_awaited_once()
    _args, kwargs = mock_process.call_args
    assert kwargs.get("persona_pin") == "qa"
    assert kwargs.get("slack_channel_id") == "C0ALLEKR9FZ"
    assert kwargs.get("slack_username") == "QA"
    assert kwargs.get("slack_icon_emoji") == ":detective:"
