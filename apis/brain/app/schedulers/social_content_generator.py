"""Social content pack — ex-``social-content-generator.json`` (WS-19).

WS-69 PR J: Slack post removed; output lands in the Brain Conversations stream.

medallion: ops
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.schedulers._history import run_with_scheduler_record
from app.schemas.conversation import ConversationCreate
from app.services.conversations import create_conversation

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_JOB_ID = "social_content_generator"
_SYSTEM_PROMPT = (
    "You are the social media manager for Paperwork Labs (paperworklabs.com), a venture that "
    "builds tools to eliminate paperwork. Products: FileFree (filefree.ai) — free AI-powered "
    "tax filing, LaunchFree (launchfree.ai) — free LLC formation, Distill (distill.tax) — "
    "B2B compliance automation APIs.\n\n"
    "Your job: create content that makes taxes and business formation feel approachable, build "
    "trust through founder authenticity, and drive users to the appropriate product.\n\n"
    "Platform rules:\n"
    "- TikTok: 15-60s vertical video scripts with hook in first 0.5s. Use trending formats. "
    "Founder-led, casual.\n"
    "- Instagram Reels: Same video re-edited with 20-30 hashtags and long save-bait caption.\n"
    "- X/Twitter: Sharp, concise text. Threads for explainers. "
    "Anti-TurboTax/anti-LegalZoom energy.\n"
    "- YouTube Shorts: Same video with subscribe CTA and keyword-rich description.\n\n"
    "Content pillars: (1) Tax Myths Busted, (2) 'I Filed in X Minutes' Reactions, "
    "(3) W-2 Explainers, (4) Money Tips, (5) Founder Journey, (6) LLC Formation Guides, "
    "(7) Business Tips for New Founders.\n\n"
    "Tone: Smart, calm friend who knows taxes and business. Use 'you/your'. Contractions always. "
    "Anti-TurboTax/anti-LegalZoom but comparative not aggressive.\n\n"
    "Return JSON with keys: title, product (filefree|launchfree|distill), tiktok_script, "
    "instagram_caption, instagram_hashtags, x_tweet, x_thread (array), youtube_description."
)
_USER_PROMPT = (
    "Create one social content pack for this week. Vary the pillar and primary platform emphasis."
)


async def _openai_social_json() -> str:
    api_key = (settings.OPENAI_API_KEY or "").strip()
    if not api_key:
        logger.info("social_content_generator: OPENAI_API_KEY unset, skipping")
        return ""
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _USER_PROMPT},
        ],
        "temperature": 0.8,
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
        logger.exception("social_content_generator: OpenAI call failed")
        return ""


def _format_for_conversation(raw: str, date_str: str) -> str:
    """Convert JSON object to markdown for the Conversation body."""
    if not raw.strip():
        return "No output generated. Check workflow logs."
    try:
        obj: dict[str, object] = json.loads(raw)
        parts: list[str] = [f"**Social Content Pack — {date_str}**\n"]
        for k, v in obj.items():
            label = k.replace("_", " ").title()
            if isinstance(v, list):
                lines = "\n".join(f"  - {item}" for item in v)
                parts.append(f"**{label}:**\n{lines}")
            elif isinstance(v, dict):
                parts.append(f"**{label}:** {json.dumps(v)}")
            else:
                parts.append(f"**{label}:** {v}")
        return "\n\n".join(parts)
    except json.JSONDecodeError:
        return raw


async def _run_body() -> None:
    raw = await _openai_social_json()
    if not raw.strip():
        return
    date_str = datetime.now(UTC).date().isoformat()
    body_md = _format_for_conversation(raw, date_str)
    create_conversation(
        ConversationCreate(
            title=f"Social Content Pack — {date_str}",
            body_md=body_md,
            tags=["social-content"],
            urgency="info",
            persona="social",
            needs_founder_action=False,
        )
    )
    logger.info("social_content_generator: conversation created")


async def run_social_content_generator() -> None:
    await run_with_scheduler_record(
        _JOB_ID,
        _run_body,
        metadata={"source": "social_content_generator", "cutover": "WS-19"},
    )


def install(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        run_social_content_generator,
        trigger=CronTrigger(day_of_week="wed", hour=17, minute=0, timezone="UTC"),
        id=_JOB_ID,
        name="Social content generator (ex-social-content-generator / n8n)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info("APScheduler job %r registered (Wednesday 17:00 UTC)", _JOB_ID)
