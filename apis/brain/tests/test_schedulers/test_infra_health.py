"""Brain-owned Infra Health Check (30m interval, IntervalTrigger).

WS-69 PR J: Slack + n8n dependencies removed. Tests updated to assert
Brain Conversation creation instead of slack_outbound.post_message.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.schedulers import _history, infra_health
from app.schedulers.infra_health import install, run_infra_health


def _reset_mem_state() -> None:
    infra_health._mem_last_alert_at = None


def test_registers_interval_30m() -> None:
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "brain_infra_health"
    t = jobs[0].trigger
    assert isinstance(t, IntervalTrigger)
    assert t.interval == timedelta(minutes=30)


@pytest.mark.asyncio
async def test_dedup_no_duplicate_conversation_same_state_in_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First unhealthy run creates a Conversation; second run within dedup window is skipped."""
    from app.schedulers._history import SchedulerRunSkipped

    _reset_mem_state()

    with (
        patch(
            "app.schedulers.infra_health._probe_render_health",
            new=AsyncMock(return_value=(False, ["Service A is inactive"])),
        ),
        patch("app.schedulers.infra_health._get_redis_or_none", new=AsyncMock(return_value=None)),
        patch("app.schedulers.infra_health.create_conversation") as mock_conv,
    ):
        # First run → alert posted
        await infra_health._run_infra_health_body()
        assert mock_conv.call_count == 1

        # Second run within dedup window → SchedulerRunSkipped (no duplicate)
        with pytest.raises(SchedulerRunSkipped):
            await infra_health._run_infra_health_body()
        assert mock_conv.call_count == 1


@pytest.mark.asyncio
async def test_healthy_state_skips_via_scheduler_run_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All services healthy → SchedulerRunSkipped raised, no Brain Conversation created."""
    from app.schedulers._history import SchedulerRunSkipped

    _reset_mem_state()

    with (
        patch(
            "app.schedulers.infra_health._probe_render_health",
            new=AsyncMock(return_value=(True, [])),
        ),
        patch("app.schedulers.infra_health._get_redis_or_none", new=AsyncMock(return_value=None)),
        patch("app.schedulers.infra_health.create_conversation") as mock_conv,
    ):
        with pytest.raises(SchedulerRunSkipped):
            await infra_health._run_infra_health_body()
        mock_conv.assert_not_called()


@pytest.mark.asyncio
async def test_run_unhealthy_records_to_scheduler_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unhealthy run → Conversation created and scheduler run row written."""
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
    _reset_mem_state()

    with (
        patch(
            "app.schedulers.infra_health._probe_render_health",
            new=AsyncMock(return_value=(False, ["brain-api is inactive"])),
        ),
        patch("app.schedulers.infra_health._get_redis_or_none", new=AsyncMock(return_value=None)),
        patch("app.schedulers.infra_health.create_conversation"),
    ):
        await run_infra_health()

    assert len(stored) == 1
    assert stored[0].status == "success"
