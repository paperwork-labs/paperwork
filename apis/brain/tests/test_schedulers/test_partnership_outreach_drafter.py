"""Tests for ``partnership_outreach_drafter`` scheduler (WS-19)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scheduler_run import SchedulerRun
from app.schedulers import _history, partnership_outreach_drafter
from app.schedulers.partnership_outreach_drafter import (
    install,
    run_partnership_outreach_drafter,
)


def test_install_registers_friday_job() -> None:
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "partnership_outreach_drafter"
    t = jobs[0].trigger
    assert isinstance(t, CronTrigger)
    ref = CronTrigger(day_of_week="fri", hour=14, minute=0, timezone="UTC")
    assert t.fields == ref.fields


@pytest.mark.asyncio
async def test_run_skips_when_no_openai_key(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context():
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())
    monkeypatch.setattr(partnership_outreach_drafter.settings, "OPENAI_API_KEY", "")
    post = AsyncMock()
    monkeypatch.setattr(partnership_outreach_drafter.slack_outbound, "post_message", post)
    await run_partnership_outreach_drafter()
    await db_session.commit()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(
                SchedulerRun.job_id == "partnership_outreach_drafter",
            ),
        )
    ).scalar_one()
    assert r.status == "success"
    post.assert_not_called()


@pytest.mark.asyncio
async def test_run_posts_slack_after_openai(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context():
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())
    monkeypatch.setattr(partnership_outreach_drafter.settings, "OPENAI_API_KEY", "sk-test")

    class _FakeResp:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"subject":"Hi","body":"Partnership outreach text","cta":"reply"}'
                            ),
                        },
                    },
                ],
            }

    class _FakeClient:
        def __init__(self, *a, **k) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def post(self, *a, **k):
            return _FakeResp()

    monkeypatch.setattr(partnership_outreach_drafter.httpx, "AsyncClient", _FakeClient)
    post = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(partnership_outreach_drafter.slack_outbound, "post_message", post)
    await run_partnership_outreach_drafter()
    await db_session.commit()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(
                SchedulerRun.job_id == "partnership_outreach_drafter",
            ),
        )
    ).scalar_one()
    assert r.status == "success"
    post.assert_awaited_once()
    _args, kwargs = post.call_args
    assert kwargs.get("channel_id") == "C0AM01NHQ3Y"
    assert kwargs.get("username") == "Partnerships"
    assert "Hi" in (kwargs.get("text") or "")
    assert "Partnership Outreach" in (kwargs.get("text") or "")
