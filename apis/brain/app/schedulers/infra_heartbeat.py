"""Infra status heartbeat from Brain APScheduler (T1.3).

Replaces the **Infra Heartbeat** n8n workflow (``0 8 * * *``) that queries the
n8n REST API and posts a summary to the engineering Slack channel — see
``infra/hetzner/workflows/retired/infra-heartbeat.json`` and
``docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md`` (T1.3).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import httpx
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.schedulers._history import N8nMirrorRunSkipped, run_with_scheduler_record
from app.services import slack_outbound
from app.tools.infra import _n8n_api_root

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

JOB_ID = "brain_infra_heartbeat"
# Same channel as ``infra-heartbeat.json`` (Format Heartbeat node).
_INFRA_HEARTBEAT_SLACK_CHANNEL_ID = "C0ALVM4PAE7"
_HTTP_TIMEOUT = 10.0


def _pacific_display_now() -> str:
    d = datetime.now(ZoneInfo("America/Los_Angeles"))
    hour12 = d.hour % 12
    if hour12 == 0:
        hour12 = 12
    ampm = "AM" if d.hour < 12 else "PM"
    return f"{d.strftime('%b')} {d.day}, {d.year}, {hour12}:{d.minute:02d} {ampm}"


def _format_heartbeat_message(check: dict[str, Any]) -> str:
    now = _pacific_display_now()
    healthy = bool(check.get("healthy"))
    total = int(check.get("totalCount", 0))
    active = int(check.get("activeCount", 0))
    liveness = str(check.get("livenessStatus", "000"))
    inactive_names = check.get("inactiveNames") or []
    if not isinstance(inactive_names, list):
        inactive_names = []
    if healthy:
        return (
            f":white_check_mark: *Daily Heartbeat* — {now}\n\n"
            f"• {active}/{total} workflows active\n"
            f"• n8n reachable ({liveness})\n\n"
            "All systems operational."
        )
    parts: list[str] = [f":warning: *Daily Heartbeat — ISSUES DETECTED* — {now}\n"]
    parts.append(f"• Workflows: {active}/{total} active")
    if inactive_names:
        names = ", ".join(str(n) for n in inactive_names if n)
        if names:
            parts.append(f"• Inactive: {names}")
    parts.append(f"• n8n liveness: {liveness}")
    return "\n".join(parts)


async def _fetch_n8n_workflow_check() -> dict[str, Any]:
    """Match the exported workflow's «Run Health Checks» node output shape."""
    api_key = (settings.N8N_API_KEY or "").strip()
    base = (settings.N8N_URL or "").strip()
    liveness = "000"
    workflows: list[Any] = []
    if not api_key or not base:
        return {
            "healthy": False,
            "totalCount": 0,
            "activeCount": 0,
            "inactiveCount": 0,
            "inactiveNames": [],
            "livenessStatus": liveness,
        }

    root = _n8n_api_root(base)
    headers = {"X-N8N-API-KEY": api_key, "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            wf_res = await client.get(
                f"{root}/workflows",
                headers=headers,
                params={"limit": "250"},
            )
        if wf_res.status_code == 200:
            liveness = "200"
            wf_body = wf_res.json()
            raw = wf_body.get("data") or wf_body.get("workflows") or []
            if isinstance(raw, list):
                workflows = raw
        else:
            liveness = str(wf_res.status_code)
    except Exception:
        liveness = "000"
        workflows = []

    total = len(workflows)
    active = sum(1 for w in workflows if isinstance(w, dict) and w.get("active") is True)
    inactive_names: list[str] = []
    for w in workflows:
        if not isinstance(w, dict):
            continue
        if not w.get("active"):
            name = w.get("name")
            if name:
                inactive_names.append(str(name))
    healthy = active == total and liveness == "200"
    return {
        "healthy": healthy,
        "totalCount": total,
        "activeCount": active,
        "inactiveCount": total - active,
        "inactiveNames": inactive_names,
        "livenessStatus": liveness,
    }


async def _run_infra_heartbeat_body() -> None:
    if not (settings.SLACK_BOT_TOKEN or "").strip():
        raise N8nMirrorRunSkipped()

    check = await _fetch_n8n_workflow_check()
    text = _format_heartbeat_message(check)
    result = await slack_outbound.post_message(
        channel_id=_INFRA_HEARTBEAT_SLACK_CHANNEL_ID,
        text=text,
        username="Engineering",
        icon_emoji=":heartbeat:",
    )
    if not result.get("ok"):
        err = str(result.get("error") or "unknown_slack_error")
        raise RuntimeError(f"Slack post failed: {err}")


async def run_infra_heartbeat() -> None:
    await run_with_scheduler_record(
        JOB_ID,
        _run_infra_heartbeat_body,
        metadata={"source": "brain_infra_heartbeat", "cutover": "T1.3"},
        reraise=True,
    )


def install(scheduler: AsyncIOScheduler) -> None:
    """Register the infra heartbeat (ex-Infra Heartbeat / n8n)."""
    scheduler.add_job(
        run_infra_heartbeat,
        trigger=CronTrigger.from_crontab("0 8 * * *", timezone="UTC"),
        id=JOB_ID,
        name="Infra Heartbeat (Brain, ex-Infra Heartbeat / n8n)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info("APScheduler job %r registered (08:00 UTC, matches n8n expression)", JOB_ID)
