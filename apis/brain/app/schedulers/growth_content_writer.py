"""Growth marketing content — ex-``growth-content-writer.json`` (WS-19).

The n8n flow used a secured webhook, OpenAI ``gpt-4o`` with a fixed system
prompt (JSON object), formatted mrkdwn, and posted to ``#general``
(``C0AM01NHQ3Y``). The export had no cron; this scheduler runs weekly
(Tuesday 16:00 UTC).

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

_JOB_ID = "growth_content_writer"
_GROWTH_CHANNEL_ID = "C0AM01NHQ3Y"
_SYSTEM_PROMPT = (
    "You are the Head of Growth for Paperwork Labs (paperworklabs.com), focused primarily on "
    "FileFree (filefree.ai) — a free AI-powered tax filing app. Paperwork Labs also builds "
    "LaunchFree (launchfree.ai) for free LLC formation and Distill (distill.tax) for B2B "
    "compliance automation.\n\n"
    "Your job: create marketing content that drives signups, builds trust, and positions "
    "FileFree as the anti-TurboTax and LaunchFree as the anti-LegalZoom.\n\n"
    "Target audience: First-time and early-career filers (18-30), mobile-first, skeptical of "
    "'free' claims. New business owners (25-40) for LaunchFree.\n\n"
    "Brand voice: Smart, calm friend who knows taxes and business formation. Use 'you/your'. "
    "Contractions always. Never 'the taxpayer'. Celebrate wins. Anti-TurboTax/anti-LegalZoom "
    "energy: honest, simple, transparent.\n\n"
    "SEO target keywords: 'how to file taxes for free 2026', 'what is a W2 form', "
    "'standard deduction 2025 amount', 'first time filing taxes guide', "
    "'tax refund calculator 2026', 'how to form an LLC for free', 'LLC formation guide 2026'.\n\n"
    "Return structured JSON with keys: title, product (filefree|launchfree), content_type, "
    "body, meta_description, target_keyword, cta."
)
_USER_PROMPT = (
    "Generate one fresh marketing asset for this week. Pick a product and content_type that "
    "we have not over-used recently; align with one of the SEO keywords when natural."
)


async def _openai_growth_json() -> str:
    api_key = (settings.OPENAI_API_KEY or "").strip()
    if not api_key:
        logger.info("growth_content_writer: OPENAI_API_KEY unset, skipping")
        return ""
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _USER_PROMPT},
        ],
        "temperature": 0.7,
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
        logger.exception("growth_content_writer: OpenAI call failed")
        return ""


async def _run_body() -> None:
    raw = await _openai_growth_json()
    if not raw.strip():
        return
    formatted = format_structured_json_for_slack(raw, header_prefix="Growth Content")
    await slack_outbound.post_message(
        channel_id=_GROWTH_CHANNEL_ID,
        text=formatted,
        username="Growth",
        icon_emoji=":seedling:",
    )
    logger.info("growth_content_writer: posted to %s", _GROWTH_CHANNEL_ID)


async def run_growth_content_writer() -> None:
    await run_with_scheduler_record(
        _JOB_ID,
        _run_body,
        metadata={"source": "growth_content_writer", "cutover": "WS-19"},
    )


def install(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        run_growth_content_writer,
        trigger=CronTrigger(day_of_week="tue", hour=16, minute=0, timezone="UTC"),
        id=_JOB_ID,
        name="Growth content writer (ex-growth-content-writer / n8n)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info("APScheduler job %r registered (Tuesday 16:00 UTC)", _JOB_ID)
