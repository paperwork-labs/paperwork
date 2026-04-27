"""Shadow mirror of n8n cron workflows (T2.2 / STREAMLINE_SSO_DAGS).

When ``SCHEDULER_N8N_MIRROR_ENABLED`` (global) and/or
``SCHEDULER_N8N_MIRROR_<UPPERCASE_JOB_ID>`` (per spec) is true, register
matching schedules on the shared Brain :class:`AsyncIOScheduler` with no-op
handlers that post to ``#engineering-cron-shadow`` only. If a per-spec env var
is unset, the global default applies. Real n8n crons stay enabled until cutover
(T2.4). Per-spec ``BRAIN_OWNS_<JOB>`` flags suppress the matching shadow row so
the first-party Brain cron is the only schedule:

- :envvar:`BRAIN_OWNS_DAILY_BRIEFING` → ``n8n_shadow_brain_daily`` (T1.2)
- :envvar:`BRAIN_OWNS_WEEKLY_STRATEGY` → ``n8n_shadow_weekly_strategy`` (T1.6)
- :envvar:`BRAIN_OWNS_BRAIN_WEEKLY` → ``n8n_shadow_brain_weekly`` (T1.5 — Brain Weekly)
- :envvar:`BRAIN_OWNS_INFRA_HEARTBEAT` → ``n8n_shadow_infra_heartbeat`` (T1.3)
- :envvar:`BRAIN_OWNS_CREDENTIAL_EXPIRY` → ``n8n_shadow_credential_expiry`` (T1.4)
- :envvar:`BRAIN_OWNS_INFRA_HEALTH` → ``n8n_shadow_infra_health`` (30m ``IntervalTrigger``)
- :envvar:`BRAIN_OWNS_SPRINT_KICKOFF` → ``n8n_shadow_sprint_kickoff`` (Track K)
- :envvar:`BRAIN_OWNS_SPRINT_CLOSE` → ``n8n_shadow_sprint_close`` (Track K)
- :envvar:`BRAIN_OWNS_DATA_SOURCE_MONITOR` → ``n8n_shadow_data_source_monitor`` (P2.8)
- :envvar:`BRAIN_OWNS_DATA_DEEP_VALIDATOR` → ``n8n_shadow_data_deep_validator`` (Track K)
- :envvar:`BRAIN_OWNS_DATA_ANNUAL_UPDATE` → ``n8n_shadow_annual_data`` (P2.10, October checklist)

See ``docs/infra/BRAIN_SCHEDULER.md``.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import func, select

from app.config import settings
from app.models.scheduler_run import SchedulerRun
from app.schedulers._history import run_with_scheduler_record
from app.services import slack_outbound

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from sqlalchemy.ext.asyncio import AsyncSession

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


# Inventory from ``infra/hetzner/workflows/*.json`` (``archive/`` and ``retired/`` excluded). See runbook.  # noqa: E501
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
    now = datetime.now(UTC).isoformat()
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


def _brain_owns_brain_weekly() -> bool:
    return os.getenv("BRAIN_OWNS_BRAIN_WEEKLY", "").lower() in (
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


def _brain_owns_credential_expiry() -> bool:
    return os.getenv("BRAIN_OWNS_CREDENTIAL_EXPIRY", "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _brain_owns_weekly_strategy() -> bool:
    return os.getenv("BRAIN_OWNS_WEEKLY_STRATEGY", "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _brain_owns_sprint_kickoff() -> bool:
    return os.getenv("BRAIN_OWNS_SPRINT_KICKOFF", "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _brain_owns_data_source_monitor() -> bool:
    return os.getenv("BRAIN_OWNS_DATA_SOURCE_MONITOR", "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _brain_owns_infra_health() -> bool:
    return os.getenv("BRAIN_OWNS_INFRA_HEALTH", "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _brain_owns_sprint_close() -> bool:
    return os.getenv("BRAIN_OWNS_SPRINT_CLOSE", "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _brain_owns_data_deep_validator() -> bool:
    return os.getenv("BRAIN_OWNS_DATA_DEEP_VALIDATOR", "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _brain_owns_data_annual_update() -> bool:
    return os.getenv("BRAIN_OWNS_DATA_ANNUAL_UPDATE", "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def should_register_n8n_shadow_for_job(job_id: str) -> bool:
    """True when this shadow job should be registered (mirrors :func:`install`).

    Per-spec ``BRAIN_OWNS_<JOB>`` cutover flags suppress the matching shadow row:

    - ``n8n_shadow_brain_daily`` → :envvar:`BRAIN_OWNS_DAILY_BRIEFING` (T1.2)
    - ``n8n_shadow_brain_weekly`` → :envvar:`BRAIN_OWNS_BRAIN_WEEKLY` (T1.5 — Brain Weekly)
    - ``n8n_shadow_weekly_strategy`` → :envvar:`BRAIN_OWNS_WEEKLY_STRATEGY` (T1.6)
    - ``n8n_shadow_infra_heartbeat`` → :envvar:`BRAIN_OWNS_INFRA_HEARTBEAT` (T1.3)
    - ``n8n_shadow_credential_expiry`` → :envvar:`BRAIN_OWNS_CREDENTIAL_EXPIRY` (T1.4)
    - ``n8n_shadow_infra_health`` → :envvar:`BRAIN_OWNS_INFRA_HEALTH` (30m interval)
    - ``n8n_shadow_sprint_kickoff`` → :envvar:`BRAIN_OWNS_SPRINT_KICKOFF` (Track K)
    - ``n8n_shadow_sprint_close`` → :envvar:`BRAIN_OWNS_SPRINT_CLOSE` (Track K)
    - ``n8n_shadow_data_source_monitor`` → :envvar:`BRAIN_OWNS_DATA_SOURCE_MONITOR` (P2.8)
    - ``n8n_shadow_data_deep_validator`` → :envvar:`BRAIN_OWNS_DATA_DEEP_VALIDATOR` (Track K)
    - ``n8n_shadow_annual_data`` → :envvar:`BRAIN_OWNS_DATA_ANNUAL_UPDATE` (P2.10)
    """
    if not is_n8n_mirror_enabled_for_job(job_id):
        return False
    if job_id == "n8n_shadow_brain_daily" and _brain_owns_daily_briefing():
        return False
    if job_id == "n8n_shadow_brain_weekly" and _brain_owns_brain_weekly():
        return False
    if job_id == "n8n_shadow_weekly_strategy" and _brain_owns_weekly_strategy():
        return False
    if job_id == "n8n_shadow_infra_heartbeat" and _brain_owns_infra_heartbeat():
        return False
    if job_id == "n8n_shadow_credential_expiry" and _brain_owns_credential_expiry():
        return False
    if job_id == "n8n_shadow_infra_health" and _brain_owns_infra_health():
        return False
    if job_id == "n8n_shadow_sprint_kickoff" and _brain_owns_sprint_kickoff():
        return False
    if job_id == "n8n_shadow_sprint_close" and _brain_owns_sprint_close():
        return False
    if job_id == "n8n_shadow_data_source_monitor" and _brain_owns_data_source_monitor():
        return False
    if job_id == "n8n_shadow_data_deep_validator" and _brain_owns_data_deep_validator():
        return False
    if job_id == "n8n_shadow_annual_data" and _brain_owns_data_annual_update():
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
    cutoff = datetime.now(UTC) - timedelta(hours=24)
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
