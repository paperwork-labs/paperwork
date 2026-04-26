"""Brain-owned Infra Health Check (30m interval, IntervalTrigger)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.schedulers import _history, infra_health, infra_heartbeat
from app.schedulers.infra_health import install, run_infra_health
from app.schedulers.n8n_mirror import N8N_MIRROR_SPECS, install as install_n8n_mirror
from app.schedulers.n8n_mirror import n8n_mirror_env_var_name


def _reset_mem_state() -> None:
    infra_health._mem_fp = None
    infra_health._mem_last_healthy = None
    infra_health._mem_last_slack_at = None


def test_flag_off_no_job_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRAIN_OWNS_INFRA_HEALTH", raising=False)
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    assert len(sched.get_jobs()) == 0


def test_flag_on_registers_interval_30m(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAIN_OWNS_INFRA_HEALTH", "true")
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "brain_infra_health"
    t = jobs[0].trigger
    assert isinstance(t, IntervalTrigger)
    assert t.interval == timedelta(minutes=30)


def test_flag_on_suppresses_infra_health_shadow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRAIN_OWNS_INFRA_HEALTH", "true")
    for s in N8N_MIRROR_SPECS:
        monkeypatch.delenv(n8n_mirror_env_var_name(s.job_id), raising=False)
    monkeypatch.setattr(settings, "SCHEDULER_N8N_MIRROR_ENABLED", True)
    sched = AsyncIOScheduler(timezone="UTC")
    install_n8n_mirror(sched)
    ids = {j.id for j in sched.get_jobs()}
    assert "n8n_shadow_infra_health" not in ids
    assert "n8n_shadow_brain_daily" in ids


@pytest.mark.asyncio
async def test_dedup_no_duplicate_post_same_state_in_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "SLACK_BOT_TOKEN", "xoxb-test", raising=False)
    unhealthy = {
        "healthy": False,
        "totalCount": 2,
        "activeCount": 1,
        "inactiveCount": 1,
        "inactiveNames": ["x"],
        "livenessStatus": "200",
    }
    monkeypatch.setattr(
        infra_heartbeat,
        "_fetch_n8n_workflow_check",
        AsyncMock(return_value=unhealthy),
    )
    post = AsyncMock(return_value={"ok": True, "ts": "1.0"})
    monkeypatch.setattr(infra_health.slack_outbound, "post_message", post)
    _reset_mem_state()
    await infra_health._run_infra_health_body()
    post.assert_awaited_once()
    await infra_health._run_infra_health_body()
    post.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_slack_error_records_to_scheduler_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored: list = []

    @asynccontextmanager
    async def _fake_context():
        class S:
            async def commit(self) -> None:
                pass

            def add(self, o: object) -> None:
                stored.append(o)

        yield S()

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())
    monkeypatch.setattr(settings, "SLACK_BOT_TOKEN", "xoxb-test", raising=False)
    monkeypatch.setattr(
        infra_heartbeat,
        "_fetch_n8n_workflow_check",
        AsyncMock(
            return_value={
                "healthy": False,
                "totalCount": 1,
                "activeCount": 0,
                "inactiveCount": 1,
                "inactiveNames": ["a"],
                "livenessStatus": "200",
            }
        ),
    )
    post = AsyncMock(return_value={"ok": False, "error": "internal_error"})
    monkeypatch.setattr(infra_health.slack_outbound, "post_message", post)
    _reset_mem_state()
    with pytest.raises(RuntimeError, match="Slack post failed"):
        await run_infra_health()
    assert len(stored) == 1
    assert stored[0].status == "error"
    assert "Slack" in (stored[0].error_text or "")
