"""Brain-owned infra heartbeat scheduler (T1.3)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.scheduler_run import SchedulerRun
from app.schedulers import _history, infra_heartbeat
from app.schedulers.infra_heartbeat import install, run_infra_heartbeat


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
    monkeypatch.setattr(settings, "SLACK_BOT_TOKEN", "xoxb-test", raising=False)
    fetch = AsyncMock(
        return_value={
            "healthy": True,
            "totalCount": 3,
            "activeCount": 3,
            "inactiveCount": 0,
            "inactiveNames": [],
            "livenessStatus": "200",
        }
    )
    monkeypatch.setattr(infra_heartbeat, "_fetch_n8n_workflow_check", fetch)
    post = AsyncMock(return_value={"ok": True, "ts": "1.0"})
    monkeypatch.setattr(infra_heartbeat.slack_outbound, "post_message", post)
    await run_infra_heartbeat()
    await db_session.commit()
    r = (
        await db_session.execute(select(SchedulerRun).where(SchedulerRun.job_id == "brain_infra_heartbeat"))
    ).scalar_one()
    assert r.status == "success"
    assert r.error_text is None
    post.assert_awaited_once()
    fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_slack_error_records_and_reraises(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context():
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())
    monkeypatch.setattr(settings, "SLACK_BOT_TOKEN", "xoxb-test", raising=False)
    monkeypatch.setattr(
        infra_heartbeat,
        "_fetch_n8n_workflow_check",
        AsyncMock(
            return_value={
                "healthy": True,
                "totalCount": 1,
                "activeCount": 1,
                "inactiveCount": 0,
                "inactiveNames": [],
                "livenessStatus": "200",
            }
        ),
    )
    post = AsyncMock(return_value={"ok": False, "error": "internal_error"})
    monkeypatch.setattr(infra_heartbeat.slack_outbound, "post_message", post)
    with pytest.raises(RuntimeError, match="Slack post failed"):
        await run_infra_heartbeat()
    await db_session.commit()
    r = (
        await db_session.execute(select(SchedulerRun).where(SchedulerRun.job_id == "brain_infra_heartbeat"))
    ).scalar_one()
    assert r.status == "error"
    assert r.error_text is not None
    assert "Slack" in (r.error_text or "")
