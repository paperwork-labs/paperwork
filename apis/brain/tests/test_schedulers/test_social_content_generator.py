"""Tests for ``social_content_generator`` scheduler (WS-19)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scheduler_run import SchedulerRun
from app.schedulers import _history, social_content_generator
from app.schedulers.social_content_generator import install, run_social_content_generator


def test_install_registers_wednesday_job() -> None:
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "social_content_generator"
    t = jobs[0].trigger
    assert isinstance(t, CronTrigger)
    ref = CronTrigger(day_of_week="wed", hour=17, minute=0, timezone="UTC")
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
    monkeypatch.setattr(social_content_generator.settings, "OPENAI_API_KEY", "")
    post = AsyncMock()
    monkeypatch.setattr(social_content_generator.slack_outbound, "post_message", post)
    await run_social_content_generator()
    await db_session.commit()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(SchedulerRun.job_id == "social_content_generator"),
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
    monkeypatch.setattr(social_content_generator.settings, "OPENAI_API_KEY", "sk-test")

    class _FakeResp:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"title":"S","product":"filefree","tiktok_script":"t",'
                                '"instagram_caption":"i","instagram_hashtags":"h",'
                                '"x_tweet":"x","x_thread":[],"youtube_description":"y"}'
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

    monkeypatch.setattr(social_content_generator.httpx, "AsyncClient", _FakeClient)
    post = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(social_content_generator.slack_outbound, "post_message", post)
    await run_social_content_generator()
    await db_session.commit()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(SchedulerRun.job_id == "social_content_generator"),
        )
    ).scalar_one()
    assert r.status == "success"
    post.assert_awaited_once()
    _args, kwargs = post.call_args
    assert kwargs.get("username") == "Social"
    assert "Social Content" in (kwargs.get("text") or "")
