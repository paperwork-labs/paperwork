"""Track I — daily #cfo cost dashboard.

The proactive_cadence scheduler posts a free-form CFO brief every
morning. That's useful for narrative ("runway looks good, watch Anthropic
spend") but doesn't surface the hard numbers on its own.

This scheduler does the opposite: a compact, zero-LLM post that reads
the per-persona cost counters out of Redis and lays them out as a
table. Zero cost, deterministic, and fast to scan. If the org is about
to blow a ceiling it's visible before the CFO brief speculates about it.

We run once a day at 15:30 UTC (≈8:30am PT). That's early enough that
the CFO brief at 14:00 UTC can reference it if needed, but late enough
to catch overnight automation spend.

medallion: ops
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.personas import list_specs
from app.redis import get_redis
from app.services import slack_outbound

logger = logging.getLogger(__name__)

_ORG_ID = "paperwork-labs"
_CFO_CHANNEL = "cfo"


async def _read_spend(redis_client: Any, persona: str) -> float:
    """Read today's cost counter for ``persona``. 0.0 on miss / error."""
    try:
        raw = await redis_client.get(f"cost:daily:{_ORG_ID}:{persona}")
    except Exception:
        logger.debug("cost read failed for %s", persona, exc_info=True)
        return 0.0
    if not raw:
        return 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _format_dashboard(
    rows: list[tuple[str, float, float | None]], total: float,
) -> str:
    """Render a Slack-friendly mrkdwn table.

    rows: [(persona, spent_usd, ceiling_usd)].
    """
    # Sort by spent desc so the biggest movers land at the top.
    rows = sorted(rows, key=lambda r: r[1], reverse=True)
    lines = [f"*CFO · daily cost dashboard — {datetime.now(timezone.utc).date().isoformat()}*"]
    lines.append(f"_Total Brain spend today: *${total:.2f}*_")
    lines.append("```")
    lines.append(f"{'persona':<14} {'spent':>8} {'ceiling':>8} {'used':>6}")
    for persona, spent, ceiling in rows:
        if ceiling and ceiling > 0:
            used_pct = f"{(spent / ceiling) * 100:5.1f}%"
        else:
            used_pct = "   —  "
        ceiling_str = f"${ceiling:.2f}" if ceiling else "  —  "
        lines.append(f"{persona:<14} ${spent:6.2f} {ceiling_str:>8} {used_pct}")
    lines.append("```")

    # Call out any persona over 80% of its ceiling so the CFO can act.
    hot = [
        persona for persona, spent, ceiling in rows
        if ceiling and ceiling > 0 and spent / ceiling >= 0.8
    ]
    if hot:
        lines.append(f":warning: near ceiling (≥80%): *{', '.join(hot)}*")
    else:
        lines.append(":white_check_mark: all personas comfortably under ceiling")
    return "\n".join(lines)


async def _run_dashboard_tick() -> None:
    """Build and post today's CFO cost dashboard."""
    try:
        redis_client = get_redis()
    except RuntimeError:
        logger.warning("cost dashboard: redis unavailable, skipping today's post")
        return

    rows: list[tuple[str, float, float | None]] = []
    total = 0.0
    for spec in list_specs():
        spent = await _read_spend(redis_client, spec.name)
        rows.append((spec.name, spent, spec.daily_cost_ceiling_usd))
        total += spent

    if not rows:
        logger.info("cost dashboard: no personas found, skipping")
        return

    channel_id = settings.SLACK_CFO_CHANNEL_ID or settings.SLACK_ENGINEERING_CHANNEL_ID
    if not channel_id:
        logger.info("cost dashboard: no target channel configured, skipping")
        return

    body = _format_dashboard(rows, total)
    await slack_outbound.post_message(
        channel=channel_id,
        text=body,
        username="CFO",
        icon_emoji=":moneybag:",
        unfurl_links=False,
    )
    logger.info(
        "cost dashboard posted to %s (total=$%.2f, personas=%d)",
        _CFO_CHANNEL, total, len(rows),
    )


def install(scheduler) -> None:
    """Register the daily dashboard job on the shared APScheduler."""
    scheduler.add_job(
        _run_dashboard_tick,
        trigger=CronTrigger(hour=15, minute=30, timezone="UTC"),
        id="cfo_cost_dashboard",
        name="CFO daily cost dashboard",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info(
        "APScheduler job 'cfo_cost_dashboard' registered (daily 15:30 UTC)"
    )
