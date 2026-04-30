"""Track I — daily CFO cost dashboard via Brain Conversations (WS-69 PR J).

Runs once a day at 15:30 UTC. Reads per-persona cost counters out of Redis
and creates a Conversation instead of posting to the CFO channel.

medallion: ops
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from apscheduler.triggers.cron import CronTrigger

from app.personas import list_specs
from app.redis import get_redis
from app.schemas.conversation import ConversationCreate
from app.services.conversations import create_conversation

logger = logging.getLogger(__name__)

_ORG_ID = "paperwork-labs"


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
    rows: list[tuple[str, float, float | None]],
    total: float,
) -> str:
    rows = sorted(rows, key=lambda r: r[1], reverse=True)
    date_str = datetime.now(UTC).date().isoformat()
    lines = [f"**CFO · daily cost dashboard — {date_str}**"]
    lines.append(f"_Total Brain spend today: **${total:.2f}**_")
    lines.append("```")
    lines.append(f"{'persona':<14} {'spent':>8} {'ceiling':>8} {'used':>6}")
    for persona, spent, ceiling in rows:
        used_pct = f"{spent / ceiling * 100:5.1f}%" if ceiling and ceiling > 0 else "   —  "
        ceiling_str = f"${ceiling:.2f}" if ceiling else "  —  "
        lines.append(f"{persona:<14} ${spent:6.2f} {ceiling_str:>8} {used_pct}")
    lines.append("```")

    hot = [
        persona
        for persona, spent, ceiling in rows
        if ceiling and ceiling > 0 and spent / ceiling >= 0.8
    ]
    if hot:
        lines.append(f"Near ceiling (≥80%): **{', '.join(hot)}**")
    else:
        lines.append("All personas comfortably under ceiling.")
    return "\n".join(lines)


async def _run_dashboard_tick() -> None:
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

    body = _format_dashboard(rows, total)
    date_str = datetime.now(UTC).date().isoformat()
    create_conversation(
        ConversationCreate(
            title=f"CFO Cost Dashboard — {date_str}",
            body_md=body,
            tags=["cfo"],
            urgency="info",
            persona="cfo",
            needs_founder_action=False,
        )
    )
    logger.info(
        "cost dashboard conversation created (total=$%.2f, personas=%d)",
        total,
        len(rows),
    )


def install(scheduler: Any) -> None:
    scheduler.add_job(
        _run_dashboard_tick,
        trigger=CronTrigger(hour=15, minute=30, timezone="UTC"),
        id="cfo_daily_cost_dashboard",
        name="CFO daily cost dashboard (Conversations)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info("APScheduler job 'cfo_daily_cost_dashboard' registered (15:30 UTC)")
