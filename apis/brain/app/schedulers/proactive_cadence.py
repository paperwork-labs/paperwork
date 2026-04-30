"""Track C — Brain-owned proactive persona cadence via Brain Conversations (WS-69 PR J).

Runs once per hour, checks every PersonaSpec for a ``proactive_cadence``
setting, and creates a Brain Conversation when the schedule fires:

  - ``daily`` personas post at 14:00 UTC every weekday
  - ``weekly`` personas post Mondays at 15:00 UTC
  - ``monthly`` personas post on the 1st at 16:00 UTC

State is kept in Redis (``brain:cadence:last:{persona}`` → ISO date) to
prevent double-posts across restarts.
"""

from __future__ import annotations

import contextlib
import logging
from datetime import UTC, datetime
from typing import Any

from apscheduler.triggers.cron import CronTrigger

from app.database import async_session_factory
from app.personas import list_specs
from app.redis import get_redis
from app.schemas.conversation import ConversationCreate
from app.services import agent as brain_agent
from app.services.conversations import create_conversation

logger = logging.getLogger(__name__)

_ORG_ID = "paperwork-labs"


def _cadence_prompt(persona: str, cadence: str) -> str:
    horizon = {
        "daily": "the last 24 hours and the next 24 hours",
        "weekly": "the last week and the week ahead",
        "monthly": "the last month and the month ahead",
    }.get(cadence, "the recent work")
    return (
        f"Proactive {cadence} brief for the {persona} persona. "
        f"In 5-8 bullets max, cover {horizon}: wins, risks, decisions needed, "
        "and the single most important thing to act on. Speak as the persona, "
        "in your own voice. No preamble — jump straight to bullets."
    )


def _should_fire(cadence: str, now: datetime) -> bool:
    if cadence == "daily":
        return now.hour == 14 and now.weekday() < 5
    if cadence == "weekly":
        return now.weekday() == 0 and now.hour == 15
    if cadence == "monthly":
        return now.day == 1 and now.hour == 16
    return False


async def _already_posted_today(redis_client: Any, persona: str, today: str) -> bool:
    if redis_client is None:
        return False
    try:
        key = f"brain:cadence:last:{persona}"
        last = await redis_client.get(key)
        if last is None:
            return False
        last_str = last if isinstance(last, str) else last.decode("utf-8")
        return last_str == today
    except Exception:
        logger.debug("cadence redis lookup failed for %s", persona, exc_info=True)
        return False


async def _mark_posted(redis_client: Any, persona: str, today: str) -> None:
    if redis_client is None:
        return
    try:
        key = f"brain:cadence:last:{persona}"
        await redis_client.setex(key, 60 * 60 * 24 * 40, today)
    except Exception:
        logger.debug("cadence redis setex failed for %s", persona, exc_info=True)


async def _post_for_persona(persona: str, cadence: str) -> None:
    """Run Brain as ``persona`` and create a Conversation."""
    redis_client = None
    with contextlib.suppress(RuntimeError):
        redis_client = get_redis()

    async with async_session_factory() as db:
        result = await brain_agent.process(
            db,
            redis_client,
            organization_id=_ORG_ID,
            org_name="Paperwork Labs",
            user_id=f"brain-scheduler:{cadence}",
            message=_cadence_prompt(persona, cadence),
            channel="conversations",
            request_id=f"cadence:{persona}:{datetime.now(UTC).date().isoformat()}",
            persona_pin=persona,
        )
        await db.commit()

    body = (result.get("response") or "").strip()
    if not body:
        logger.warning("cadence for %s returned empty; skipping Conversation create", persona)
        return

    date_str = datetime.now(UTC).date().isoformat()
    create_conversation(
        ConversationCreate(
            title=f"{persona.title()} {cadence.title()} Brief — {date_str}",
            body_md=f"**{persona}** — {cadence} brief\n\n{body}",
            tags=[persona],
            urgency="info",
            persona=persona,
            needs_founder_action=False,
        )
    )


async def _run_cadence_tick() -> None:
    now = datetime.now(UTC)
    today = now.date().isoformat()

    redis_client = None
    with contextlib.suppress(RuntimeError):
        redis_client = get_redis()

    for spec in list_specs():
        cadence = getattr(spec, "proactive_cadence", "never")
        if cadence == "never":
            continue
        if not _should_fire(cadence, now):
            continue
        if await _already_posted_today(redis_client, spec.name, today):
            continue

        try:
            await _post_for_persona(spec.name, cadence)
            await _mark_posted(redis_client, spec.name, today)
            logger.info("cadence posted for %s (%s)", spec.name, cadence)
        except Exception:
            logger.exception("cadence run failed for %s (%s)", spec.name, cadence)


def install(scheduler: Any) -> None:
    scheduler.add_job(
        _run_cadence_tick,
        trigger=CronTrigger(minute=0, timezone="UTC"),
        id="proactive_cadence",
        name="Proactive persona cadence (hourly)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info("proactive_cadence: job registered (hourly, :00 UTC)")
