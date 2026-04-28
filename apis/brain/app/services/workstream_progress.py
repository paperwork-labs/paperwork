"""Hourly workstream progress — ``percent_done`` from GitHub PR search (Track Z)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.database import async_session_factory
from app.models.workstream_board import WorkstreamProgressSnapshot
from app.schedulers._history import run_with_scheduler_record
from app.services import workstream_github as wh
from app.services.workstreams_loader import load_workstreams_file

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_JOB_ID = "workstream_progress"


@dataclass
class WorkstreamProgressResult:
    snapshots_recorded: int = 0
    skipped: bool = False
    skip_reason: str | None = None
    by_workstream_id: dict[str, int] = field(default_factory=dict)


def compute_percent_done(
    merged_prs: int,
    open_prs: int,
    estimated_pr_count: int | None,
) -> tuple[int, int]:
    """Return ``(percent_done, denominator)`` per WORKSTREAMS_BOARD.md."""
    denom = max((estimated_pr_count or (merged_prs + open_prs)), 1)
    pct = min(100, round(merged_prs / denom * 100))
    return pct, denom


def compute_snapshot_status(
    percent_done: int,
    open_prs: int,
    file_status: str,
) -> str:
    if percent_done >= 100 and open_prs == 0:
        return "completed"
    return file_status


async def run_workstream_progress() -> WorkstreamProgressResult:
    if not settings.BRAIN_SCHEDULER_ENABLED:
        return WorkstreamProgressResult(
            skipped=True, skip_reason="BRAIN_SCHEDULER_ENABLED=false"
        )

    data = load_workstreams_file()
    result = WorkstreamProgressResult()

    for ws in data.workstreams:
        merged, open_n = await wh.search_prs_with_brief_tag_in_body(ws.brief_tag)
        pct, denom = compute_percent_done(merged, open_n, ws.estimated_pr_count)
        computed_status = compute_snapshot_status(pct, open_n, ws.status)

        async with async_session_factory() as db:
            snap = WorkstreamProgressSnapshot(
                workstream_id=ws.id,
                recorded_at=datetime.now(UTC),
                percent_done=pct,
                computed_status=computed_status,
                merged_pr_count=merged,
                open_pr_count=open_n,
                denominator=denom,
                extra_json={"brief_tag": ws.brief_tag},
            )
            db.add(snap)
            await db.commit()
            await db.refresh(snap)

        result.snapshots_recorded += 1
        result.by_workstream_id[ws.id] = pct

    logger.info(
        "workstream_progress: recorded %d snapshots",
        result.snapshots_recorded,
    )
    return result


async def _progress_job_body() -> None:
    await run_workstream_progress()


async def run_workstream_progress_job() -> None:
    await run_with_scheduler_record(
        _JOB_ID,
        _progress_job_body,
        metadata={"source": "workstream_progress", "track": "workstreams-board"},
    )


def install(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        run_workstream_progress_job,
        trigger=CronTrigger.from_crontab("0 * * * *", timezone=UTC),
        id=_JOB_ID,
        name="Workstream progress snapshot (Track Z, hourly)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info("APScheduler job %r registered (0 * * * * UTC, hourly)", _JOB_ID)
