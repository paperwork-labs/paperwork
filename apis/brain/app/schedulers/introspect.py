"""Serialize APScheduler job list for operator introspection (``GET /internal/schedulers``)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.schedulers.pr_sweep import get_scheduler

# First-party jobs that replaced retired n8n crons (always on when scheduler runs).
_CUTOVER_JOB_IDS: frozenset[str] = frozenset(
    {
        "brain_daily_briefing",
        "brain_weekly_briefing",
        "brain_weekly_strategy",
        "brain_sprint_kickoff",
        "brain_sprint_close",
        "brain_infra_heartbeat",
        "brain_credential_expiry",
        "brain_infra_health",
        "brain_data_source_monitor",
        "brain_data_deep_validator",
        "brain_data_annual_update",
    }
)

# Operational first-party jobs (not ex-n8n cutover replacements).
_OPERATIONAL_JOB_IDS: frozenset[str] = frozenset(
    {
        "sprint_auto_logger",
        "sprint_md_auto_close",
        "brain_agent_sprint_planner",
        "workstream_dispatcher",
        "workstream_progress",
        "workstream_progress_writeback",
    }
)


def classification_for_job_id(job_id: str) -> str:
    if job_id in _CUTOVER_JOB_IDS:
        return "cutover"
    if job_id in _OPERATIONAL_JOB_IDS:
        return "operational"
    return "net-new"


def list_apscheduler_jobs() -> list[dict[str, Any]]:
    """Return one row per registered job, suitable for JSON.

    If the process has no running scheduler (``BRAIN_SCHEDULER_ENABLED=false``),
    returns an empty list.
    """
    sched = get_scheduler()
    if sched is None:
        return []
    out: list[dict[str, Any]] = []
    for job in sched.get_jobs():
        job_id = job.id
        nxt: datetime | None = job.next_run_time
        if nxt is not None and nxt.tzinfo is None:
            nxt = nxt.replace(tzinfo=UTC)
        next_str: str | None
        next_str = nxt.astimezone(UTC).isoformat() if nxt is not None else None
        trig = job.trigger
        try:
            trigger_str = str(trig)
        except Exception:
            trigger_str = repr(trig)
        out.append(
            {
                "id": job_id,
                "name": getattr(job, "name", None) or job_id,
                "next_run": next_str,
                "trigger": trigger_str,
                "enabled": True,
                "classification": classification_for_job_id(job_id),
            }
        )
    out.sort(key=lambda r: r["id"])
    return out
