"""Per-job n8n mirror flags + scheduler_run recording (T1.1)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.scheduler_run import SchedulerRun
from app.schedulers import _history, n8n_mirror
from app.schedulers._history import N8nMirrorRunSkipped
from app.schedulers.n8n_mirror import (
    N8N_MIRROR_SPECS,
    install,
    is_n8n_mirror_enabled_for_job,
    n8n_mirror_env_var_name,
    should_register_n8n_shadow_for_job,
)


def test_n8n_mirror_env_var_name_pattern() -> None:
    assert n8n_mirror_env_var_name("n8n_shadow_brain_daily") == ("SCHEDULER_N8N_MIRROR_N8N_SHADOW_BRAIN_DAILY")


def test_per_job_flag_read_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "SCHEDULER_N8N_MIRROR_ENABLED", False)
    name = n8n_mirror_env_var_name("n8n_shadow_brain_daily")
    monkeypatch.setenv(name, "true")
    assert is_n8n_mirror_enabled_for_job("n8n_shadow_brain_daily") is True
    monkeypatch.setenv(name, "false")
    assert is_n8n_mirror_enabled_for_job("n8n_shadow_brain_daily") is False
    # Other jobs still use global
    other = n8n_mirror_env_var_name("n8n_shadow_sprint_kickoff")
    monkeypatch.delenv(other, raising=False)
    assert is_n8n_mirror_enabled_for_job("n8n_shadow_sprint_kickoff") is False


def test_global_flag_fallback_when_no_per_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for s in N8N_MIRROR_SPECS:
        monkeypatch.delenv(n8n_mirror_env_var_name(s.job_id), raising=False)
    monkeypatch.setattr(settings, "SCHEDULER_N8N_MIRROR_ENABLED", True)
    for s in N8N_MIRROR_SPECS:
        assert is_n8n_mirror_enabled_for_job(s.job_id) is True


def test_per_job_off_overrides_global_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "SCHEDULER_N8N_MIRROR_ENABLED", True)
    name = n8n_mirror_env_var_name("n8n_shadow_brain_daily")
    monkeypatch.setenv(name, "false")
    assert is_n8n_mirror_enabled_for_job("n8n_shadow_brain_daily") is False


def test_brain_owns_daily_briefing_suppresses_n8n_daily_shadow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BRAIN_OWNS_DAILY_BRIEFING", raising=False)
    for s in N8N_MIRROR_SPECS:
        monkeypatch.delenv(n8n_mirror_env_var_name(s.job_id), raising=False)
    monkeypatch.setattr(settings, "SCHEDULER_N8N_MIRROR_ENABLED", True)
    assert should_register_n8n_shadow_for_job("n8n_shadow_brain_daily") is True
    monkeypatch.setenv("BRAIN_OWNS_DAILY_BRIEFING", "true")
    assert should_register_n8n_shadow_for_job("n8n_shadow_brain_daily") is False
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    ids = {j.id for j in sched.get_jobs()}
    assert "n8n_shadow_brain_daily" not in ids
    assert "n8n_shadow_brain_weekly" in ids


def test_one_job_enables_with_global_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for s in N8N_MIRROR_SPECS:
        monkeypatch.delenv(n8n_mirror_env_var_name(s.job_id), raising=False)
    monkeypatch.setattr(settings, "SCHEDULER_N8N_MIRROR_ENABLED", False)
    monkeypatch.setenv(
        n8n_mirror_env_var_name("n8n_shadow_brain_daily"),
        "1",
    )
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "n8n_shadow_brain_daily"


@pytest.mark.asyncio
async def test_run_with_scheduler_record_success(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context():
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())
    # Patch slack so _post_shadow does not need tokens
    monkeypatch.setattr(n8n_mirror.slack_outbound, "post_message", AsyncMock())
    spec = next(s for s in N8N_MIRROR_SPECS if s.job_id == "n8n_shadow_brain_daily")
    await n8n_mirror._run_shadow_for_spec(spec)
    await db_session.commit()
    res = await db_session.execute(select(SchedulerRun).where(SchedulerRun.job_id == spec.job_id))
    rows = res.scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "success"
    assert rows[0].error_text is None


@pytest.mark.asyncio
async def test_run_with_scheduler_record_error(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context():
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())

    async def _boom() -> None:
        raise ValueError("shadow boom")

    await n8n_mirror._run_with_scheduler_record(
        "n8n_shadow_test_err",
        _boom,
        metadata={"k": "v"},
    )
    await db_session.commit()
    res = await db_session.execute(select(SchedulerRun).where(SchedulerRun.job_id == "n8n_shadow_test_err"))
    r = res.scalar_one()
    assert r.status == "error"
    assert "boom" in (r.error_text or "")


@pytest.mark.asyncio
async def test_run_with_scheduler_record_skipped(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context():
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())

    async def _skip() -> None:
        raise N8nMirrorRunSkipped()

    await n8n_mirror._run_with_scheduler_record("n8n_shadow_test_skip", _skip)
    await db_session.commit()
    r = (
        await db_session.execute(select(SchedulerRun).where(SchedulerRun.job_id == "n8n_shadow_test_skip"))
    ).scalar_one()
    assert r.status == "skipped"
