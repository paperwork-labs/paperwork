"""Shadow mirror of n8n cron workflows (T2.2 / STREAMLINE_SSO_DAGS).

When ``SCHEDULER_N8N_MIRROR_ENABLED`` (global) and/or
``SCHEDULER_N8N_MIRROR_<UPPERCASE_JOB_ID>`` (per spec) is true, register
matching schedules on the shared Brain :class:`AsyncIOScheduler` with no-op
handlers that post to ``#engineering-cron-shadow`` only. If a per-spec env var
is unset, the global default applies. Real n8n crons stay enabled until cutover
(T2.4). Per-spec ``BRAIN_OWNS_<JOB>`` flags suppress the matching shadow row so
the first-party Brain cron is the only schedule:

- :envvar:`BRAIN_OWNS_DAILY_BRIEFING` → ``n8n_shadow_brain_daily`` (T1.2)
- :envvar:`BRAIN_OWNS_INFRA_HEARTBEAT` → ``n8n_shadow_infra_heartbeat`` (T1.3)

See
"""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.scheduler_run import SchedulerRun
from app.schedulers._history import run_with_scheduler_record
from app.services import slack_outbound

logger = logging.getLogger(__name__)

_run_with_scheduler_record = run_with_scheduler_record

SHADOW_SLACK_CHANNEL = "#engineering-cron-shadow"
N8N_MIRROR_ENV_PREFIX = "SCHEDULER_N8N_MIRROR_"


@dataclass(frozen=True)
class MirrorSpec:
    """One exported n8n workflow with a schedule trigger (for docs/tests)."""

    job_id: str
    n8n_workflow_name: str
    kind: Literal["cron", "interval"]
    # Cron: standard 5-field m/h/dM/MY/dow as in the workflow JSON. Interval: minutes.
    schedule: str
    summary: str


# Inventory from ``infra/hetzner/workflows/*.json`` (``archive/`` excluded). See runbook.
N8N_MIRROR_SPECS: tuple[MirrorSpec, ...] = (
    MirrorSpec(
        "n8n_shadow_brain_daily",
        "Brain Daily Trigger",
        "cron",
        "0 7 * * *",
        "POST /api/v1/brain/process (daily briefing) then Slack #daily-briefing",
    ),
    MirrorSpec(
        "n8n_shadow_brain_weekly",
        "Brain Weekly Trigger",
        "cron",
        "0 18 * * 0",
        "POST Brain process (weekly plan) then Slack",
    ),
    MirrorSpec(
        "n8n_shadow_sprint_kickoff",
        "Sprint Kickoff",
        "cron",
        "0 7 * * 1",
        "POST Brain (persona strategy) + announcement Slack",
    ),
    MirrorSpec(
        "n8n_shadow_sprint_close",
        "Sprint Close",
        "cron",
        "0 21 * * 5",
        "Fetch TASKS/KNOWLEDGE from GitHub, sprint-close automation, Slack",
    ),
    MirrorSpec(
        "n8n_shadow_weekly_strategy",
        "Weekly Strategy Check-in",
        "cron",
        "0 9 * * 1",
        "OpenAI strategy report, format, Slack",
    ),
    MirrorSpec(
        "n8n_shadow_infra_heartbeat",
        "Infra Heartbeat",
        "cron",
        "0 8 * * *",
        "n8n API workflow counts + daily Slack heartbeat",
    ),
    MirrorSpec(
        "n8n_shadow_data_source_monitor",
        "Data Source Monitor (P2.8)",
        "cron",
        "0 6 * * 1",
        "Scrape tax data sources, hash compare, alert Slack on change",
    ),
    MirrorSpec(
        "n8n_shadow_data_deep_validator",
        "Data Deep Validator (P2.9)",
        "cron",
        "0 3 1 * *",
        "Sample state JSON, cross-validate DOR vs repo, monthly Slack",
    ),
    MirrorSpec(
        "n8n_shadow_annual_data",
        "Annual Data Update Trigger (P2.10)",
        "cron",
        "0 9 1 10 *",
        "October checklist for TY rollover, Slack #engineering",
    ),
    MirrorSpec(
        "n8n_shadow_infra_health",
        "Infra Health Check",
        "interval",
        "30m",
        "Every 30m: n8n API, deduped alert Slack on change vs prior state",
    ),
    MirrorSpec(
        "n8n_shadow_credential_expiry",
        "Credential Expiry Check",
        "cron",
        "0 8 * * *",
        "GET vault secrets, expiry buckets, conditional Slack to #alerts",
    ),
)


def n8n_mirror_env_var_name(job_id: str) -> str:
    """``SCHEDULER_N8N_MIRROR_`` + uppercased job id (e.g. ``N8N_SHADOW_BRAIN_DAILY``)."""
    return f"{N8N_MIRROR_ENV_PREFIX}{job_id.upper()}"


def _parse_truthy_env(raw: str) -> bool:
    v = raw.strip().lower()
    if v in ("1", "true", "t", "yes", "y", "on"):
        return True
    if v in ("0", "false", "f", "no", "n", "off", ""):
        return False
    logger.warning("Unrecognized n8n mirror env value %r — treating as false", raw)
    return False


def is_n8n_mirror_enabled_for_job(job_id: str) -> bool:
    """True when this spec should register: per-job env if set, else global default."""
    name = n8n_mirror_env_var_name(job_id)
    if name in os.environ:
        return _parse_truthy_env(os.environ[name])
    return settings.SCHEDULER_N8N_MIRROR_ENABLED


async def _post_shadow(n8n_workflow_name: str, job_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    text = f"[shadow] {n8n_workflow_name} ({job_id}) fired at {now}"
    await slack_outbound.post_message(
        channel=SHADOW_SLACK_CHANNEL,
        text=text,
        username="Brain Cron Shadow",
        icon_emoji=":ghost:",
    )


def _brain_owns_daily_briefing() -> bool:
    return os.getenv("BRAIN_OWNS_DAILY_BRIEFING", "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _brain_owns_infra_heartbeat() -> bool:
    return os.getenv("BRAIN_OWNS_INFRA_HEARTBEAT", "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def should_register_n8n_shadow_for_job(job_id: str) -> bool:
    """True when this shadow job should be registered (mirrors :func:`install`).

    Per-spec ``BRAIN_OWNS_<JOB>`` cutover flags suppress the matching shadow row:

    - ``n8n_shadow_brain_daily`` → :envvar:`BRAIN_OWNS_DAILY_BRIEFING` (T1.2)
    - ``n8n_shadow_infra_heartbeat`` → :envvar:`BRAIN_OWNS_INFRA_HEARTBEAT` (T1.3)
    """
    if not is_n8n_mirror_enabled_for_job(job_id):
        return False
    if job_id == "n8n_shadow_brain_daily" and _brain_owns_daily_briefing():
        return False
    if job_id == "n8n_shadow_infra_heartbeat" and _brain_owns_infra_heartbeat():
        return False
    return True


async def _run_shadow_for_spec(spec: MirrorSpec) -> None:
    async def _body() -> None:
        await _post_shadow(spec.n8n_workflow_name, spec.job_id)

    await _run_with_scheduler_record(
        spec.job_id,
        _body,
        metadata={
            "n8n_workflow_name": spec.n8n_workflow_name,
            "summary": spec.summary,
        },
    )


def _bind_spec(spec: MirrorSpec) -> Callable[[], Awaitable[None]]:
    async def _fn() -> None:
        await _run_shadow_for_spec(spec)

    return _fn


def install(scheduler: AsyncIOScheduler) -> None:
    """Register n8n shadow jobs when the global and/or per-job opt-in is set."""
    enabled = [s for s in N8N_MIRROR_SPECS if should_register_n8n_shadow_for_job(s.job_id)]
    if not enabled:
        logger.info(
            "No n8n shadow mirror jobs enabled; set %s (global) or per-job %s<N8N_SHADOW_…>",
            "SCHEDULER_N8N_MIRROR_ENABLED",
            N8N_MIRROR_ENV_PREFIX,
        )
        return

    _register_specs(scheduler, enabled)
    logger.info(
        "Registered %d n8n cron shadow mirror job(s) on APScheduler (of %d known specs)",
        len(enabled),
        len(N8N_MIRROR_SPECS),
    )


def _register_specs(scheduler: AsyncIOScheduler, specs: list[MirrorSpec]) -> None:
    for spec in specs:
        fn = _bind_spec(spec)
        if spec.kind == "interval":
            assert spec.schedule.endswith("m")
            minutes = int(spec.schedule[:-1])
            trigger: IntervalTrigger | CronTrigger = IntervalTrigger(minutes=minutes)
        else:
            trigger = CronTrigger.from_crontab(spec.schedule, timezone="UTC")
        scheduler.add_job(
            fn,
            trigger=trigger,
            id=spec.job_id,
            name=f"shadow: {spec.n8n_workflow_name}",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )


async def n8n_mirror_status_payload(db: AsyncSession) -> dict[str, Any]:
    """Data for ``GET /admin/scheduler/n8n-mirror/status``."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    per_job: list[dict[str, Any]] = []
    for spec in N8N_MIRROR_SPECS:
        last = (
            await db.execute(
                select(SchedulerRun)
                .where(SchedulerRun.job_id == spec.job_id)
                .order_by(SchedulerRun.finished_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        last_run = last.finished_at.isoformat() if last else None
        last_status: str | None = last.status if last else None
        success_count = int(
            await db.scalar(
                select(func.count(SchedulerRun.id)).where(
                    SchedulerRun.job_id == spec.job_id,
                    SchedulerRun.finished_at >= cutoff,
                    SchedulerRun.status == "success",
                )
            )
            or 0
        )
        error_count = int(
            await db.scalar(
                select(func.count(SchedulerRun.id)).where(
                    SchedulerRun.job_id == spec.job_id,
                    SchedulerRun.finished_at >= cutoff,
                    SchedulerRun.status == "error",
                )
            )
            or 0
        )
        per_job.append(
            {
                "key": spec.job_id,
                "enabled": should_register_n8n_shadow_for_job(spec.job_id),
                "last_run": last_run,
                "last_status": last_status,
                "success_count_24h": success_count,
                "error_count_24h": error_count,
            }
        )
    return {
        "global_enabled": settings.SCHEDULER_N8N_MIRROR_ENABLED,
        "per_job": per_job,
    }
