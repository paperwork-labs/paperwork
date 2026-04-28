"""Brain-owned credential expiry scheduler (T1.4)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.config import settings
from app.models.scheduler_run import SchedulerRun
from app.schedulers import _history, credential_expiry
from app.schedulers.credential_expiry import install, run_credential_expiry_check

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def test_registers_one_job_id() -> None:
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "brain_credential_expiry"
    t = jobs[0].trigger
    assert isinstance(t, CronTrigger)
    ref = CronTrigger.from_crontab("0 8 * * *", timezone=UTC)
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
    soon = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    fetch = AsyncMock(return_value=[{"name": "test_key", "service": "testsvc", "expires_at": soon}])
    monkeypatch.setattr(credential_expiry, "_fetch_vault_secrets", fetch)
    post = AsyncMock(return_value={"ok": True, "ts": "1.0"})
    monkeypatch.setattr(credential_expiry.slack_outbound, "post_message", post)
    await run_credential_expiry_check()
    await db_session.commit()
    r = (
        await db_session.execute(select(SchedulerRun).where(SchedulerRun.job_id == "brain_credential_expiry"))
    ).scalar_one()
    assert r.status == "success"
    assert r.error_text is None
    post.assert_awaited_once()
    fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_credential_check_raises_records_error(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context():
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())
    monkeypatch.setattr(settings, "SLACK_BOT_TOKEN", "xoxb-test", raising=False)
    monkeypatch.setattr(
        credential_expiry,
        "_fetch_vault_secrets",
        AsyncMock(side_effect=RuntimeError("vault_unreachable")),
    )
    with pytest.raises(RuntimeError, match="vault_unreachable"):
        await run_credential_expiry_check()
    await db_session.commit()
    r = (
        await db_session.execute(select(SchedulerRun).where(SchedulerRun.job_id == "brain_credential_expiry"))
    ).scalar_one()
    assert r.status == "error"
    assert r.error_text is not None
    assert "vault" in (r.error_text or "").lower()
