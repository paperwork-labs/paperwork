"""Workstream dispatcher — top-N ``workflow_dispatch`` cadence (Track Z).

Runs every 30 minutes. Selection mirrors ``dispatchableWorkstreams`` in
``apps/studio/src/lib/workstreams/schema.ts``. Loads candidates from DB epics.

medallion: ops
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.database import async_session_factory
from app.models.epic_hierarchy import Epic
from app.models.workstream_board import WorkstreamDispatchLog
from app.schedulers._history import run_with_scheduler_record
from app.schemas.workstream import dispatchable_workstreams
from app.services import workstream_github as wh
from app.services.workstreams_loader import load_epics_from_db

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

JOB_ID = "workstream_dispatcher"
_TOP_N = 3


@dataclass
class WorkstreamDispatcherResult:
    dispatched_workstream_ids: list[str] = field(default_factory=list)
    dispatch_log_ids: list[int] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None


def _now_ms(now: datetime | None) -> int:
    dt = now or datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp() * 1000)


async def _dispatch_with_session(
    session: AsyncSession,
    *,
    now: datetime | None,
) -> WorkstreamDispatcherResult:
    data = await load_epics_from_db(session)
    candidates = dispatchable_workstreams(data, n=_TOP_N, now_ms=_now_ms(now))
    result = WorkstreamDispatcherResult()
    if not candidates:
        return result

    for ws in candidates:
        ok = await wh.workflow_dispatch(
            ws.github_actions_workflow,
            brief_tag=ws.brief_tag,
            title=ws.title,
            notes=ws.notes,
            related_plan=ws.related_plan,
        )
        if not ok:
            logger.warning("workstream_dispatcher: dispatch failed for %s", ws.id)
            continue

        wf_raw = (ws.github_actions_workflow or "").strip() or "agent-sprint-runner"
        wf_name = wf_raw if wf_raw.endswith((".yml", ".yaml")) else f"{wf_raw}.yml"
        inputs = {
            "brief_tag": ws.brief_tag,
            "title": ws.title,
            "notes": ws.notes,
            "related_plan": ws.related_plan or "",
        }
        dispatched_at = datetime.now(UTC)
        row = WorkstreamDispatchLog(
            workstream_id=ws.id,
            dispatched_at=dispatched_at,
            github_workflow=wf_name,
            inputs_json=inputs,
            github_run_id=None,
        )
        session.add(row)
        epic_row = await session.get(Epic, ws.id)
        if epic_row is not None:
            epic_row.last_dispatched_at = dispatched_at
        await session.commit()
        await session.refresh(row)
        result.dispatched_workstream_ids.append(ws.id)
        result.dispatch_log_ids.append(int(row.id))
        logger.info("workstream_dispatcher: dispatched %s workflow=%s", ws.id, wf_name)

    return result


async def run_workstream_dispatcher(
    now: datetime | None = None,
    db: AsyncSession | None = None,
) -> WorkstreamDispatcherResult:
    """Load epics from Postgres, select dispatchable rows, dispatch workflows, log + cooldown."""
    if not settings.BRAIN_SCHEDULER_ENABLED:
        return WorkstreamDispatcherResult(skipped=True, skip_reason="BRAIN_SCHEDULER_ENABLED=false")

    if db is not None:
        return await _dispatch_with_session(db, now=now)

    try:
        async with async_session_factory() as session:
            return await _dispatch_with_session(session, now=now)
    except Exception:
        logger.warning(
            "workstream_dispatcher: skipping run (no DB session / connection failed)",
            exc_info=True,
        )
        return WorkstreamDispatcherResult()


async def _dispatcher_job_body() -> None:
    res = await run_workstream_dispatcher()
    if res.skipped:
        logger.info("workstream_dispatcher job skipped: %s", res.skip_reason)
        return
    logger.info(
        "workstream_dispatcher tick: ids=%s log_ids=%s",
        res.dispatched_workstream_ids,
        res.dispatch_log_ids,
    )


async def run_workstream_dispatcher_job() -> None:
    await run_with_scheduler_record(
        JOB_ID,
        _dispatcher_job_body,
        metadata={"source": "workstream_dispatcher", "track": "workstreams-board"},
    )


def install(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        run_workstream_dispatcher_job,
        trigger=CronTrigger.from_crontab("*/30 * * * *", timezone=UTC),
        id=JOB_ID,
        name="Workstream dispatcher (Track Z, workflow_dispatch top-N)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info("APScheduler job %r registered (*/30 * * * * UTC)", JOB_ID)
