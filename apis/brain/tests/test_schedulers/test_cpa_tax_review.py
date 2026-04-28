"""Tests for ``cpa_tax_review`` scheduler (WS-19)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scheduler_run import SchedulerRun
from app.schedulers import _history, cpa_tax_review
from app.schedulers.cpa_tax_review import install, run_cpa_tax_review


def test_install_registers_thursday_job() -> None:
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "cpa_tax_review"
    t = jobs[0].trigger
    assert isinstance(t, CronTrigger)
    ref = CronTrigger(day_of_week="thu", hour=13, minute=0, timezone="UTC")
    assert t.fields == ref.fields


@pytest.mark.asyncio
async def test_run_invokes_brain_process_with_cpa_persona(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context():
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())
    mock_process = AsyncMock(return_value={"response": "ok", "persona": "cpa"})
    monkeypatch.setattr(cpa_tax_review.brain_agent, "process", mock_process)
    await run_cpa_tax_review()
    await db_session.commit()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(SchedulerRun.job_id == "cpa_tax_review"),
        )
    ).scalar_one()
    assert r.status == "success"
    mock_process.assert_awaited_once()
    _args, kwargs = mock_process.call_args
    assert kwargs.get("persona_pin") == "cpa"
    assert kwargs.get("slack_channel_id") == "C0AM01NHQ3Y"
    assert kwargs.get("slack_username") == "CPA Advisor"
    assert kwargs.get("slack_icon_emoji") == ":nerd_face:"
