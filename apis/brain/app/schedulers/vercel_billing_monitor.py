"""Hourly Vercel on-demand budget poll — fires Brain Conversation alerts at 50/75/90/100%.

medallion: ops
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from apscheduler.triggers.cron import CronTrigger

from app.schemas.conversation import ConversationCreate
from app.services.conversations import create_conversation
from app.services.vercel_billing_monitor import run

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_JOB_ID = "vercel_billing_monitor_hourly"


def _alert_title_and_body(alert: dict[str, Any]) -> tuple[str, str]:
    """Build Conversation title and markdown body for one billing alert."""
    spent = alert.get("spent_usd")
    budget = alert.get("budget_usd")
    pct = alert.get("pct")
    severity = alert.get("severity", "warning")
    if alert.get("level") == "any_spend":
        title = "Vercel on-demand spend alert ($0 cap)"
        body = (
            f"**Severity:** {severity}\n\n"
            f"{alert.get('message', 'Spend detected against a $0 on-demand budget.')}\n\n"
            f"**Spend this period:** ${spent}\n"
        )
        return title, body

    threshold = alert.get("threshold")
    title = f"Vercel on-demand budget — {pct}% of cap ({severity})"
    body = (
        f"**Workspace:** paperwork-labs (on-demand meter)\n\n"
        f"- **Spend:** ${spent}\n"
        f"- **Budget:** ${budget}\n"
        f"- **Utilization:** {pct}%\n"
        f"- **Threshold crossed:** {int(threshold * 100) if threshold is not None else 'n/a'}%\n"
        f"- **Severity:** {severity}\n\n"
        "_Deduped once per threshold per billing period._\n"
    )
    return title, body


async def _tick() -> None:
    result = run()
    if not result.get("ok"):
        logger.warning("vercel_billing_monitor: skipped (%s)", result.get("reason"))
        return
    alerts = result.get("alerts", [])
    for a in alerts:
        title, body_md = _alert_title_and_body(a)
        create_conversation(
            ConversationCreate(
                title=title,
                body_md=body_md,
                tags=["vercel-budget", "paperwork-labs", "bill-pending"],
                urgency="high",
                persona="cfo",
                needs_founder_action=False,
            )
        )
        logger.info(
            "vercel_billing_monitor: created conversation for alert threshold=%s pct=%s",
            a.get("threshold", a.get("level")),
            a.get("pct"),
        )


def install(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        _tick,
        CronTrigger(minute=0),
        id=_JOB_ID,
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=300,
    )
    logger.info("APScheduler job %r registered (hourly, Vercel on-demand budget)", _JOB_ID)
