"""Partnership outreach drafts — ex-``partnership-outreach-drafter.json`` (WS-19).

The n8n flow: webhook → OpenAI ``gpt-4o`` (structured JSON) → Slack ``#general``
(``C0AM01NHQ3Y``). Export had no cron; this job runs weekly Friday 14:00 UTC.

medallion: ops
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import httpx
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.schedulers._history import run_with_scheduler_record
from app.schedulers._n8n_slack_format import format_structured_json_for_slack
from app.services import slack_outbound

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_JOB_ID = "partnership_outreach_drafter"
_PARTNERSHIPS_CHANNEL_ID = "C0AM01NHQ3Y"
_SYSTEM_PROMPT = (
    "You are the Partnership Development Assistant for Paperwork Labs (paperworklabs.com). "
    "You support a partnerships co-founder (Founder 2) who has a FAANG background, two young "
    "kids, and 2-3 hours per week. Every deliverable must be ready to use in under 10 minutes.\n\n"
    "Paperwork Labs builds tools that eliminate paperwork:\n"
    "- FileFree (filefree.ai): Free AI-powered tax filing. Shows users their refund amount and "
    "presents personalized financial product recommendations at the moment of highest financial "
    "intent.\n"
    "- LaunchFree (launchfree.ai): Free LLC formation. Users form their LLC for free and get "
    "recommended banking, payroll, insurance, and compliance services.\n"
    "- Distill (distill.tax): B2B compliance automation APIs + CPA SaaS. Partners integrate tax, "
    "formation, and compliance via API.\n\n"
    "Partnership hit list:\n"
    "FileFree: Marcus by Goldman Sachs (HYSA), Wealthfront (HYSA+investment), Betterment "
    "(investment), Fidelity (IRA/brokerage), Column Tax (e-file SDK), Refundo (refund advance).\n"
    "LaunchFree: Mercury (business banking), Relay (business banking), Gusto (payroll), "
    "Deel (international payroll), Next Insurance (business insurance), Northwest RA "
    "(registered agent).\n"
    "Distill: CPA firms, fintech platforms, law firms, accounting software vendors.\n\n"
    "Revenue context: Partnership revenue = 77% of projected FileFree revenue. LaunchFree revenue "
    "comes from banking/payroll/insurance referrals + Compliance-as-a-Service ($49-99/yr).\n\n"
    "Output formats (produce ONE based on request):\n"
    "1. outreach_email: subject, body, CTA. Ready to send.\n"
    "2. deal_summary: one-page brief with partner details, pricing targets, questions.\n"
    "3. call_prep: 5-min read with agenda, our ask, their concerns.\n"
    "4. pipeline_update: partners by status, next actions.\n\n"
    "Return as structured JSON matching the requested format."
)
_USER_PROMPT = (
    "Produce one partnership deliverable for this week. Choose the single most valuable format "
    "(outreach_email, deal_summary, call_prep, or pipeline_update) and return structured JSON "
    "for that format only."
)


async def _openai_partnership_json() -> str:
    api_key = (settings.OPENAI_API_KEY or "").strip()
    if not api_key:
        logger.info("partnership_outreach_drafter: OPENAI_API_KEY unset, skipping")
        return ""
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _USER_PROMPT},
        ],
        "temperature": 0.6,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
            return str(data["choices"][0]["message"]["content"] or "")
    except (httpx.HTTPError, KeyError, json.JSONDecodeError):
        logger.exception("partnership_outreach_drafter: OpenAI call failed")
        return ""


async def _run_body() -> None:
    raw = await _openai_partnership_json()
    if not raw.strip():
        return
    formatted = format_structured_json_for_slack(
        raw,
        header_prefix="Partnership Outreach",
    )
    await slack_outbound.post_message(
        channel_id=_PARTNERSHIPS_CHANNEL_ID,
        text=formatted,
        username="Partnerships",
        icon_emoji=":handshake:",
    )
    logger.info(
        "partnership_outreach_drafter: posted to %s",
        _PARTNERSHIPS_CHANNEL_ID,
    )


async def run_partnership_outreach_drafter() -> None:
    await run_with_scheduler_record(
        _JOB_ID,
        _run_body,
        metadata={"source": "partnership_outreach_drafter", "cutover": "WS-19"},
    )


def install(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        run_partnership_outreach_drafter,
        trigger=CronTrigger(day_of_week="fri", hour=14, minute=0, timezone="UTC"),
        id=_JOB_ID,
        name="Partnership outreach drafter (ex-partnership-outreach-drafter / n8n)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info("APScheduler job %r registered (Friday 14:00 UTC)", _JOB_ID)
