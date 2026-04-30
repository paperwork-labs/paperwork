"""Friday 18:00 UTC CFO weekly digest via Brain Conversations (WS-69 PR J).

Reads ``apps/studio/src/data/tracker-index.json`` when the monorepo is
present; otherwise the brief notes that the index is unavailable.
Summarization is one Brain pass with the CFO persona so the post matches
CFO voice. Creates a Conversation instead of posting to Slack.

medallion: ops
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from apscheduler.triggers.cron import CronTrigger

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database import async_session_factory
from app.personas import list_specs
from app.schemas.conversation import ConversationCreate
from app.services import agent as brain_agent
from app.services.conversations import create_conversation

logger = logging.getLogger(__name__)

CFO_PERSONA_LABEL = "CFO"

_ORG_ID = "paperwork-labs"


def _default_tracker_path() -> Path:
    rel = Path("apps") / "studio" / "src" / "data" / "tracker-index.json"
    env = os.environ.get("REPO_ROOT")
    if env:
        return Path(env) / rel
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / rel
        if candidate.exists():
            return candidate
    return Path("/app") / rel


def load_tracker_index(path: Path | None = None) -> dict[str, Any] | None:
    p = path or _default_tracker_path()
    if not p.exists():
        return None
    try:
        return cast("dict[str, Any]", json.loads(p.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return None


def _is_critical_date_open(status: str | None) -> bool:
    if not status:
        return True
    s = status.strip().upper()
    return not (s == "COMPLETE" or s.startswith("DONE"))


def _count_active_plans(tracker: dict[str, Any]) -> int:
    n = 0
    for prod in tracker.get("products") or []:
        for plan in prod.get("plans") or []:
            if (plan.get("status") or "").strip().lower() == "active":
                n += 1
    return n


def _shipped_in_window(sprint: dict[str, Any], as_of: date) -> bool:
    if (sprint.get("status") or "").strip().lower() != "shipped":
        return False
    raw = sprint.get("end")
    if not raw:
        return False
    try:
        end_d = date.fromisoformat(str(raw)[:10])
    except ValueError:
        return False
    start = as_of - timedelta(days=7)
    return start <= end_d <= as_of


def build_friday_tracker_brief(
    tracker: dict[str, Any] | None,
    *,
    as_of: date | None = None,
) -> tuple[str, dict[str, int]]:
    day = as_of or datetime.now(UTC).date()
    if tracker is None:
        note = (
            "*Tracker index unavailable* — the Brain deploy may not include "
            "``apps/studio/src/data/tracker-index.json`` (monorepo path missing or unreadable). "
            "Sprint and plan sections are omitted; continue with general CFO guidance only."
        )
        return note, {
            "active_sprint_count": 0,
            "plan_count": 0,
            "shipped_last_7d_count": 0,
        }

    sprints = [s for s in (tracker.get("sprints") or []) if isinstance(s, dict)]
    active = [s for s in sprints if (s.get("status") or "").strip().lower() == "active"]
    shipped = [s for s in sprints if _shipped_in_window(s, day)]

    lines: list[str] = [f"*Tracker snapshot (as of {day.isoformat()})*"]

    if active:
        lines.append("\n*Active sprints*")
        for s in active:
            title = s.get("title") or s.get("slug") or "(untitled)"
            owner = s.get("owner") or "—"
            lines.append(f"• {title} — owner: {owner}")
    else:
        lines.append("\n*Active sprints:* none listed.")

    if shipped:
        lines.append("\n*Shipped in the last 7 days*")
        for s in shipped:
            title = s.get("title") or s.get("slug") or "(untitled)"
            end = s.get("end") or "?"
            lines.append(f"• {title} (end {end})")
    else:
        lines.append("\n*Shipped in the last 7 days:* none.")

    company = tracker.get("company") or {}
    critical = [c for c in (company.get("critical_dates") or []) if isinstance(c, dict)]
    open_rows = [c for c in critical if _is_critical_date_open(c.get("status"))]

    if open_rows:
        lines.append("\n*Open company critical dates* (status is not DONE/COMPLETE)")
        for c in open_rows:
            m = c.get("milestone") or "(milestone)"
            d = c.get("deadline") or "—"
            st = c.get("status") or "—"
            lines.append(f"• {m} — due: {d} — status: {st}")
    else:
        lines.append("\n*Open company critical dates:* none (or not listed).")

    plan_count = _count_active_plans(tracker)
    lines.append(f"\n*Active product plans (status=active):* {plan_count}")

    brief = "\n".join(lines)
    meta = {
        "active_sprint_count": len(active),
        "plan_count": plan_count,
        "shipped_last_7d_count": len(shipped),
    }
    return brief, meta


def _cfo_user_message(tracker_brief: str) -> str:
    return (
        "You are producing the **Friday CFO digest** for internal leadership.\n\n"
        "## Instructions (follow for this turn)\n"
        "Summarize the *tracker facts* below in **5-8 bullet points**. "
        "For every blocker, dependency, or material risk, name an **explicit owner** "
        "(person or team). Be concise, finance-forward, and actionable. **No preamble** — start "
        "directly with the bullets.\n\n"
        "## Tracker facts (source of truth for this run)\n"
        f"{tracker_brief}\n"
    )


async def _run_friday_digest() -> None:
    try:
        raw = load_tracker_index()
        tracker_brief, meta = build_friday_tracker_brief(raw)
        today = datetime.now(UTC).date().isoformat()

        redis_client = None
        try:
            from app.redis import get_redis

            redis_client = get_redis()
        except RuntimeError:
            pass

        user_message = _cfo_user_message(tracker_brief)

        async with async_session_factory() as db:
            result = await brain_agent.process(
                db,
                redis_client,
                organization_id=_ORG_ID,
                org_name="Paperwork Labs",
                user_id="brain-scheduler:cfo_friday",
                message=user_message,
                channel="conversations",
                request_id=f"cfo-friday-digest:{today}",
                persona_pin="cfo",
            )
            await db.commit()

        body = (result.get("response") or "").strip()
        if not body:
            logger.warning("cfo friday: Brain returned empty response; skipping Conversation")
            return

        create_conversation(
            ConversationCreate(
                title=f"CFO Friday Digest — {today}",
                body_md=f"**{CFO_PERSONA_LABEL}** — Friday digest\n\n{body}",
                tags=["cfo"],
                urgency="normal",
                persona="cfo",
                needs_founder_action=False,
            )
        )
        cost_str = await _format_cost_hint_for_log(redis_client)
        logger.info(
            "event=cfo_friday_digest_posted sprint_count=%d plan_count=%d cost_estimate=%s",
            meta["active_sprint_count"],
            meta["plan_count"],
            cost_str,
        )
    except Exception:
        logger.exception("cfo friday digest run failed — will retry next week")


async def _read_spend(redis_client: Any, persona: str) -> float:
    try:
        raw = await redis_client.get(f"cost:daily:{_ORG_ID}:{persona}")
    except Exception:
        return 0.0
    if not raw:
        return 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


async def _format_cost_hint_for_log(redis_client: Any | None) -> str:
    if redis_client is None:
        return "unavailable"
    try:
        total = 0.0
        for spec in list_specs():
            total += await _read_spend(redis_client, spec.name)
        return f"{total:.2f}usd_today"
    except Exception:
        return "unavailable"


def install(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        _run_friday_digest,
        trigger=CronTrigger(day_of_week="fri", hour=18, minute=0, timezone="UTC"),
        id="cfo_friday_digest",
        name="CFO Friday weekly digest (tracker + persona)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info("APScheduler job 'cfo_friday_digest' registered (Friday 18:00 UTC)")
