"""Brain-owned credential expiry scheduler (T1.4)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.scheduler_run import SchedulerRun
from app.schedulers import _history, credential_expiry
from app.schedulers.credential_expiry import install, run_credential_expiry_check
from app.schedulers.n8n_mirror import N8N_MIRROR_SPECS, install as install_n8n_mirror
from app.schedulers.n8n_mirror import n8n_mirror_env_var_name


def test_flag_off_no_job_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRAIN_OWNS_CREDENTIAL_EXPIRY", raising=False)
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    assert len(sched.get_jobs()) == 0


def test_flag_on_registers_one_job_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAIN_OWNS_CREDENTIAL_EXPIRY", "true")
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "brain_credential_expiry"
    t = jobs[0].trigger
    assert isinstance(t, CronTrigger)
    ref = CronTrigger.from_crontab("0 8 * * *", timezone=timezone.utc)
    assert t.fields == ref.fields


def test_flag_on_suppresses_matching_n8n_shadow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRAIN_OWNS_CREDENTIAL_EXPIRY", "true")
    for s in N8N_MIRROR_SPECS:
        monkeypatch.delenv(n8n_mirror_env_var_name(s.job_id), raising=False)
    monkeypatch.setattr(settings, "SCHEDULER_N8N_MIRROR_ENABLED", True)
    sched = AsyncIOScheduler(timezone="UTC")
    install_n8n_mirror(sched)
    ids = {j.id for j in sched.get_jobs()}
    assert "n8n_shadow_credential_expiry" not in ids
    assert "n8n_shadow_brain_daily" in ids


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
    soon = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
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
