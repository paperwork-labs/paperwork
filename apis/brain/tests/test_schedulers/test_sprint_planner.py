"""Sprint planning scheduler (autonomous planning prompt)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.models.scheduler_run import SchedulerRun
from app.schedulers import _history, sprint_planner
from app.schedulers.sprint_planner import (
    build_sprint_planning_prompt,
    classify_sprints,
    install,
    load_sprint_records,
    run_sprint_planner,
)

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession


def test_flag_off_no_job_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRAIN_OWNS_SPRINT_PLANNER", raising=False)
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    assert len(sched.get_jobs()) == 0


def test_flag_on_registers_one_job_id_and_la_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAIN_OWNS_SPRINT_PLANNER", "true")
    sched = AsyncIOScheduler(timezone="UTC")
    install(sched)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "brain_sprint_planner"
    t = jobs[0].trigger
    assert isinstance(t, CronTrigger)
    la = ZoneInfo("America/Los_Angeles")
    ref = CronTrigger.from_crontab("0 14 * * 1", timezone=la)
    assert t.fields == ref.fields


def test_build_prompt_classifies_sprint_statuses(tmp_path: Path) -> None:
    sprints = tmp_path / "docs" / "sprints"
    sprints.mkdir(parents=True)
    (sprints / "done_old.md").write_text(
        """---
title: Old ship
status: shipped
last_reviewed: 2026-01-01
sprint:
  end: 2026-03-01
---
# X
## What we learned
- lesson a
""",
        encoding="utf-8",
    )
    (sprints / "stale_ip.md").write_text(
        """---
title: Stale IP
status: in_progress
last_reviewed: 2026-01-01
---
# Y
- [ ] todo
""",
        encoding="utf-8",
    )
    (sprints / "paused.md").write_text(
        """---
title: Paused sprint
status: paused
---
# Z
""",
        encoding="utf-8",
    )
    plans = tmp_path / "docs" / "axiomfolio" / "plans"
    plans.mkdir(parents=True)
    (plans / "orphan_plan.md").write_text(
        """---
status: active
priority: P1
---
# Plan
""",
        encoding="utf-8",
    )

    as_of = date(2026, 4, 26)
    recs = load_sprint_records(tmp_path)
    buckets = classify_sprints(recs, as_of)
    assert any(r.path.name == "paused.md" for r in buckets["paused"])
    assert any(r.path.name == "stale_ip.md" for r in buckets["stale_in_progress"])
    assert any(r.path.name == "done_old.md" for r in buckets["archive_candidates"])

    prompt = build_sprint_planning_prompt(tmp_path, as_of=as_of)
    assert "Stale in-progress" in prompt
    assert "Paused sprints" in prompt
    assert "orphan_plan.md" in prompt or "axiomfolio/plans/orphan_plan.md" in prompt


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
        return_value={"response": "plan body", "persona": "strategy", "model": "x"},
    )
    monkeypatch.setattr(sprint_planner.brain_agent, "process", mock_process)
    post = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(sprint_planner.slack_outbound, "post_message", post)
    monkeypatch.setattr(sprint_planner, "_append_knowledge_snapshot", AsyncMock())
    await run_sprint_planner()
    await db_session.commit()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(SchedulerRun.job_id == "brain_sprint_planner"),
        )
    ).scalar_one()
    assert r.status == "success"
    post.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_missing_slack_token_skips_post_gracefully(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_context():
        yield db_session

    monkeypatch.setattr(_history, "async_session_factory", lambda: _fake_context())
    monkeypatch.setattr(
        sprint_planner.brain_agent, "process", AsyncMock(return_value={"response": "x"})
    )
    monkeypatch.setattr(sprint_planner, "_append_knowledge_snapshot", AsyncMock())
    post = AsyncMock(return_value={"ok": False, "error": "SLACK_BOT_TOKEN not configured"})
    monkeypatch.setattr(sprint_planner.slack_outbound, "post_message", post)
    await run_sprint_planner()
    await db_session.commit()
    post.assert_awaited_once()
    r = (
        await db_session.execute(
            select(SchedulerRun).where(SchedulerRun.job_id == "brain_sprint_planner"),
        )
    ).scalar_one()
    assert r.status == "success"
