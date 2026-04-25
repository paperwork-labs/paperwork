"""Shadow mirror of n8n cron workflows (T2.2 / STREAMLINE_SSO_DAGS).

When ``SCHEDULER_N8N_MIRROR_ENABLED`` is true, register matching schedules on the
shared Brain :class:`AsyncIOScheduler` with no-op handlers that post to
``#engineering-cron-shadow`` only. Real n8n crons stay enabled until cutover
(T2.4). See ``docs/infra/BRAIN_SCHEDULER.md``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.services import slack_outbound

logger = logging.getLogger(__name__)

SHADOW_SLACK_CHANNEL = "#engineering-cron-shadow"


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


async def _post_shadow(n8n_workflow_name: str, job_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    text = f"[shadow] {n8n_workflow_name} ({job_id}) fired at {now}"
    await slack_outbound.post_message(
        channel=SHADOW_SLACK_CHANNEL,
        text=text,
        username="Brain Cron Shadow",
        icon_emoji=":ghost:",
    )


# --- Per-job coroutines (stable ids for job store) ---


async def _run_shadow_brain_daily() -> None:
    await _post_shadow("Brain Daily Trigger", "n8n_shadow_brain_daily")


async def _run_shadow_brain_weekly() -> None:
    await _post_shadow("Brain Weekly Trigger", "n8n_shadow_brain_weekly")


async def _run_shadow_sprint_kickoff() -> None:
    await _post_shadow("Sprint Kickoff", "n8n_shadow_sprint_kickoff")


async def _run_shadow_sprint_close() -> None:
    await _post_shadow("Sprint Close", "n8n_shadow_sprint_close")


async def _run_shadow_weekly_strategy() -> None:
    await _post_shadow("Weekly Strategy Check-in", "n8n_shadow_weekly_strategy")


async def _run_shadow_infra_heartbeat() -> None:
    await _post_shadow("Infra Heartbeat", "n8n_shadow_infra_heartbeat")


async def _run_shadow_data_source_monitor() -> None:
    await _post_shadow("Data Source Monitor (P2.8)", "n8n_shadow_data_source_monitor")


async def _run_shadow_data_deep_validator() -> None:
    await _post_shadow("Data Deep Validator (P2.9)", "n8n_shadow_data_deep_validator")


async def _run_shadow_annual_data() -> None:
    await _post_shadow("Annual Data Update Trigger (P2.10)", "n8n_shadow_annual_data")


async def _run_shadow_infra_health() -> None:
    await _post_shadow("Infra Health Check", "n8n_shadow_infra_health")


async def _run_shadow_credential_expiry() -> None:
    await _post_shadow("Credential Expiry Check", "n8n_shadow_credential_expiry")


def install(scheduler: AsyncIOScheduler) -> None:
    """Register n8n shadow jobs when the env opt-in is set."""
    if not settings.SCHEDULER_N8N_MIRROR_ENABLED:
        logger.info("SCHEDULER_N8N_MIRROR_ENABLED=false — n8n shadow mirrors not registered")
        return

    _register_all(scheduler)
    logger.info(
        "Registered %d n8n cron shadow mirror job(s) on APScheduler",
        len(N8N_MIRROR_SPECS),
    )


def _register_all(scheduler: AsyncIOScheduler) -> None:
    mapping: dict[str, object] = {
        "n8n_shadow_brain_daily": _run_shadow_brain_daily,
        "n8n_shadow_brain_weekly": _run_shadow_brain_weekly,
        "n8n_shadow_sprint_kickoff": _run_shadow_sprint_kickoff,
        "n8n_shadow_sprint_close": _run_shadow_sprint_close,
        "n8n_shadow_weekly_strategy": _run_shadow_weekly_strategy,
        "n8n_shadow_infra_heartbeat": _run_shadow_infra_heartbeat,
        "n8n_shadow_data_source_monitor": _run_shadow_data_source_monitor,
        "n8n_shadow_data_deep_validator": _run_shadow_data_deep_validator,
        "n8n_shadow_annual_data": _run_shadow_annual_data,
        "n8n_shadow_infra_health": _run_shadow_infra_health,
        "n8n_shadow_credential_expiry": _run_shadow_credential_expiry,
    }
    for spec in N8N_MIRROR_SPECS:
        fn = mapping[spec.job_id]
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
