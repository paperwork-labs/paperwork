"""Brain-owned annual tax data update scheduler (Track K / P2.10).

WS-69 PR J: Slack dependency removed. Tests updated to assert
Brain Conversation creation instead of slack_outbound.post_message.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.models.scheduler_run import SchedulerRun
from app.schedulers import _history
from app.schedulers.data_annual_update import _build_message, install, run_data_annual_update

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def test_registers_one_job_id() -> None:
    from zoneinfo import ZoneInfo

    la = ZoneInfo("America/Los_Angeles")
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "brain_data_annual_update"
    t = jobs[0].trigger
    assert isinstance(t, CronTrigger)
    assert str(t.timezone) == "America/Los_Angeles"
    ref = CronTrigger.from_crontab("0 9 1 10 *", timezone=la)
    assert t.fields == ref.fields


def test_build_message_includes_next_year() -> None:
    fixed = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    text = _build_message(fixed)
    assert "TY2027" in text
    assert "Annual Tax Data Update — TY2027" in text
    assert "EXTRACT_TAX_YEAR=2027" in text


def test_build_message_includes_all_ten_checklist_steps() -> None:
    fixed = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    text = _build_message(fixed)
    assert "1. IRS Revenue Procedure for TY2027" in text
    assert "2. Download new Tax Foundation XLSX" in text
    assert "3. Run formation update:" in text
    assert "4. Run full review:" in text
    assert "5. Run test suite:" in text
    assert "6. Add known-good anchor values for TY2027" in text
    assert "7. Run `pnpm review:approve`" in text
    assert "8. Create PR and merge to main" in text
    assert "9. Verify CI passes on the PR" in text
    assert "10. Post confirmation to #engineering when done" in text
    assert "taxfoundation.org" in text


@pytest.mark.asyncio
async def test_run_success_creates_conversation(
    db_session: "AsyncSession",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context():
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())

    with patch("app.schedulers.data_annual_update.create_conversation") as mock_conv:
        await run_data_annual_update()
        await db_session.commit()

    r = (
        await db_session.execute(
            select(SchedulerRun).where(SchedulerRun.job_id == "brain_data_annual_update"),
        )
    ).scalar_one()
    assert r.status == "success"
    assert r.error_text is None
    mock_conv.assert_called_once()
    call_arg = mock_conv.call_args[0][0]
    assert "Annual Tax Data Update" in call_arg.title
    assert call_arg.needs_founder_action is True
    assert "data" in call_arg.tags
