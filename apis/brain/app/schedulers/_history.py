"""Shared persistence for APScheduler job runs (``agent_scheduler_runs``).

Used by the n8n shadow mirror module and first-party Brain crons (T1.2+)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any, Literal

from app.database import async_session_factory
from app.models.scheduler_run import SchedulerRun

logger = logging.getLogger(__name__)


class N8nMirrorRunSkipped(Exception):
    """Inner body may raise this to persist ``skipped`` (not ``error``)."""


async def run_with_scheduler_record(
    job_id: str,
    runner: Callable[[], Awaitable[None]],
    *,
    metadata: dict[str, Any] | None = None,
    reraise: bool = False,
) -> None:
    started = datetime.now(timezone.utc)
    status: Literal["success", "error", "skipped"] = "success"
    error_text: str | None = None
    to_raise: BaseException | None = None
    try:
        await runner()
    except N8nMirrorRunSkipped:
        status = "skipped"
    except Exception as e:
        to_raise = e
        status = "error"
        error_text = str(e)[:20000]
        logger.exception("scheduler job %s failed", job_id)
    finally:
        finished = datetime.now(timezone.utc)
        row = SchedulerRun(
            job_id=job_id,
            started_at=started,
            finished_at=finished,
            status=status,
            error_text=error_text,
            metadata_json=metadata,
        )
        try:
            async with async_session_factory() as db:
                db.add(row)
                await db.commit()
        except Exception:
            logger.exception("Failed to persist scheduler_run for job_id=%s", job_id)
    if reraise and to_raise is not None:
        raise to_raise
