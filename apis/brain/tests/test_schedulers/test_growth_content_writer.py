"""Tests for ``growth_content_writer`` scheduler (WS-19)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scheduler_run import SchedulerRun
from app.schedulers import _history, growth_content_writer
from app.schedulers.growth_content_writer import install, run_growth_content_writer


def test_install_registers_tuesday_job() -> None:
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "growth_content_writer"
    t = jobs[0].trigger
    assert isinstance(t, CronTrigger)
    ref = CronTrigger(day_of_week="tue", hour=16, minute=0, timezone="UTC")
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
    monkeypatch.setattr(growth_content_writer.settings, "OPENAI_API_KEY", "")
    post = AsyncMock()
    monkeypatch.setattr(growth_content_writer.slack_outbound, "post_message", post)
    await run_growth_content_writer()
    await db_session.commit()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(SchedulerRun.job_id == "growth_content_writer"),
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
    monkeypatch.setattr(growth_content_writer.settings, "OPENAI_API_KEY", "sk-test")

    class _FakeResp:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"title":"Hello","product":"filefree","content_type":"post",'
                                '"body":"x","meta_description":"m","target_keyword":"k","cta":"c"}'
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

    monkeypatch.setattr(growth_content_writer.httpx, "AsyncClient", _FakeClient)
    post = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(growth_content_writer.slack_outbound, "post_message", post)
    await run_growth_content_writer()
    await db_session.commit()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(SchedulerRun.job_id == "growth_content_writer"),
        )
    ).scalar_one()
    assert r.status == "success"
    post.assert_awaited_once()
    _args, kwargs = post.call_args
    assert kwargs.get("channel_id") == "C0AM01NHQ3Y"
    assert kwargs.get("username") == "Growth"
    assert "Hello" in (kwargs.get("text") or "")
