"""Brain-owned infra heartbeat scheduler (T1.3)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.models.scheduler_run import SchedulerRun
from app.schedulers import _history, infra_heartbeat
from app.schedulers.infra_heartbeat import install, run_infra_heartbeat

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def test_registers_one_job_id() -> None:
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "brain_infra_heartbeat"
    t = jobs[0].trigger
    assert isinstance(t, CronTrigger)
    ref = CronTrigger.from_crontab("0 8 * * *", timezone="UTC")
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
    create = MagicMock()
    monkeypatch.setattr(infra_heartbeat, "create_conversation", create)
    await run_infra_heartbeat()
    await db_session.commit()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(SchedulerRun.job_id == "brain_infra_heartbeat")
        )
    ).scalar_one()
    assert r.status == "success"
    assert r.error_text is None
    create.assert_called_once()
    call_kw = create.call_args[0][0]
    assert "heartbeat job executed successfully" in (call_kw.body_md or "").lower()


@pytest.mark.asyncio
async def test_run_create_conversation_failure_records_error(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context():
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())
    monkeypatch.setattr(
        infra_heartbeat,
        "create_conversation",
        MagicMock(side_effect=RuntimeError("disk full")),
    )
    with pytest.raises(RuntimeError, match="disk full"):
        await run_infra_heartbeat()
    await db_session.commit()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(SchedulerRun.job_id == "brain_infra_heartbeat")
        )
    ).scalar_one()
    assert r.status == "error"
    assert r.error_text is not None
    assert "disk full" in (r.error_text or "")
