"""Brain-owned Sprint Close scheduler (Track K)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import httpx
import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.models.scheduler_run import SchedulerRun
from app.schedulers import _history, sprint_close
from app.schedulers.sprint_close import install, run_sprint_close

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def test_registers_one_job_id() -> None:
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "brain_sprint_close"
    t = jobs[0].trigger
    assert isinstance(t, CronTrigger)
    ref = CronTrigger.from_crontab("0 21 * * 5", timezone=UTC)
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
        return_value={"response": "retro body", "persona": "strategy", "model": "x"},
    )
    monkeypatch.setattr(sprint_close.brain_agent, "process", mock_process)
    append = AsyncMock()
    monkeypatch.setattr(sprint_close, "_github_append_sprint_close_to_knowledge", append)
    await run_sprint_close()
    await db_session.commit()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(SchedulerRun.job_id == "brain_sprint_close"),
        )
    ).scalar_one()
    assert r.status == "success"
    assert r.error_text is None
    append.assert_awaited_once()
    mock_process.assert_awaited_once()
    _args, kwargs = mock_process.call_args
    assert kwargs.get("persona_pin") == "strategy"
    assert kwargs.get("slack_username") == "Sprint Retro"
    assert kwargs.get("slack_icon_emoji") == ":checkered_flag:"


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

    monkeypatch.setattr(sprint_close.brain_agent, "process", _boom)
    await run_sprint_close()
    await db_session.commit()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(SchedulerRun.job_id == "brain_sprint_close"),
        )
    ).scalar_one()
    assert r.status == "error"
    assert r.error_text is not None
    assert "process failed" in (r.error_text or "")


@pytest.mark.asyncio
async def test_github_commit_failure_records_error(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context():
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())
    monkeypatch.setattr(
        sprint_close.brain_agent,
        "process",
        AsyncMock(return_value={"response": "ok", "persona": "strategy"}),
    )

    async def _put_fail(*_a, **kwargs):
        req = httpx.Request(
            "PUT",
            "https://api.github.com/repos/paperwork-labs/paperwork/contents/docs/KNOWLEDGE.md",
        )
        raise httpx.HTTPStatusError(
            "server error", request=req, response=httpx.Response(500, request=req)
        )

    monkeypatch.setattr(sprint_close, "_github_append_sprint_close_to_knowledge", _put_fail)
    await run_sprint_close()
    await db_session.commit()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(SchedulerRun.job_id == "brain_sprint_close"),
        )
    ).scalar_one()
    assert r.status == "error"
    assert r.error_text is not None
