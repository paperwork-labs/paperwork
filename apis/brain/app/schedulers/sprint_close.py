"""Brain-owned Sprint Close retro (Track K / STREAMLINE).

Replaces the **Sprint Close** n8n workflow (``0 21 * * 5``) that fetched
TASKS/KNOWLEDGE, called OpenAI, posted to ``#sprints``, and updated
``docs/KNOWLEDGE.md`` — see ``infra/hetzner/workflows/sprint-close.json`` and
``docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md``.

Cutover uses :func:`app.services.agent.process` with ``persona_pin="strategy"``
so Brain fetches context via tools and posts to Slack. This module appends the
retro text to ``docs/KNOWLEDGE.md`` via the GitHub Contents API (``GITHUB_TOKEN``).
"""

from __future__ import annotations

import base64
import logging
import os
from datetime import datetime, timezone

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import async_session_factory
from app.redis import get_redis
from app.schedulers._history import run_with_scheduler_record
from app.services import agent as brain_agent

logger = logging.getLogger(__name__)

_JOB_ID = "brain_sprint_close"
# ``#sprints`` (``sprint-close.json``).
_SPRINT_CHANNEL_ID = "C0AM3APFP99"
_ORG_ID = "paperwork-labs"
_ORG_NAME = "Paperwork Labs"
_GITHUB_CONTENTS_URL = (
    "https://api.github.com/repos/paperwork-labs/paperwork/contents/docs/KNOWLEDGE.md"
)
_HTTP_TIMEOUT = 60.0
_KNOWLEDGE_APPEND_MAX = 8000

_SPRINT_MESSAGE = (
    "It's Friday 9pm. Close this 5-day sprint with an honest retrospective using "
    "docs/TASKS.md, docs/KNOWLEDGE.md, recent commits, and recent closed PRs from "
    "paperwork-labs/paperwork. Return Slack-ready markdown with five sections (each as "
    "a *bold* header on its own line): *What Shipped*, *What Slipped*, *Quality Report*, "
    "*Velocity Check*, *Next Sprint Preview*. Be direct and specific."
)


def _owns_sprint_close() -> bool:
    return os.getenv("BRAIN_OWNS_SPRINT_CLOSE", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _truncate_for_knowledge(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        text = "(no response text)"
    if len(text) > _KNOWLEDGE_APPEND_MAX:
        return text[:_KNOWLEDGE_APPEND_MAX] + "\n\n_(truncated)_"
    return text


async def _github_append_sprint_close_to_knowledge(
    *,
    response_text: str,
    iso_date: str,
) -> None:
    """GET current KNOWLEDGE.md, append sprint-close block, PUT with same ``sha``."""
    token = (os.getenv("GITHUB_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not set; cannot update KNOWLEDGE.md")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    body_text = _truncate_for_knowledge(response_text)
    append_block = f"\n\n### Sprint Close — {iso_date}\n\n{body_text}\n\n"

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        get_resp = await client.get(_GITHUB_CONTENTS_URL, headers=headers)
        get_resp.raise_for_status()
        data = get_resp.json()
        content_b64 = str(data.get("content") or "")
        sha = str(data.get("sha") or "")
        if not sha:
            raise RuntimeError("GitHub GET KNOWLEDGE.md: missing sha")
        current = base64.b64decode(content_b64.replace("\n", "")).decode("utf-8")
        new_bytes = (current + append_block).encode("utf-8")
        new_b64 = base64.b64encode(new_bytes).decode("ascii")
        put_payload = {
            "message": f"docs: log sprint close {iso_date}",
            "content": new_b64,
            "sha": sha,
        }
        put_resp = await client.put(_GITHUB_CONTENTS_URL, headers=headers, json=put_payload)
        if put_resp.status_code < 200 or put_resp.status_code >= 300:
            logger.warning(
                "GitHub PUT KNOWLEDGE.md failed: status=%s body=%s",
                put_resp.status_code,
                (put_resp.text or "")[:2000],
            )
            put_resp.raise_for_status()


async def _run_sprint_close_body() -> None:
    request_id = f"sprint-close:brain:{datetime.now(timezone.utc).isoformat()}"
    redis_client = None
    try:
        redis_client = get_redis()
    except RuntimeError:
        pass
    date_iso = datetime.now(timezone.utc).date().isoformat()
    async with async_session_factory() as db:
        result = await brain_agent.process(
            db,
            redis_client,
            organization_id=_ORG_ID,
            org_name=_ORG_NAME,
            user_id="brain-scheduler:sprint-close",
            message=_SPRINT_MESSAGE,
            channel="slack",
            channel_id=_SPRINT_CHANNEL_ID,
            request_id=request_id,
            persona_pin="strategy",
            slack_channel_id=_SPRINT_CHANNEL_ID,
            slack_username="Sprint Retro",
            slack_icon_emoji=":checkered_flag:",
        )
        await db.commit()
    response_text = str(result.get("response", "") or "")
    await _github_append_sprint_close_to_knowledge(response_text=response_text, iso_date=date_iso)


async def run_sprint_close() -> None:
    """APScheduler entry: Brain process (strategy) posts to ``#sprints``; then KNOWLEDGE.md."""
    await run_with_scheduler_record(
        _JOB_ID,
        _run_sprint_close_body,
        metadata={"source": "brain_sprint_close", "cutover": "T_K"},
    )


def install(scheduler: AsyncIOScheduler) -> None:
    """Register Sprint Close cron when :envvar:`BRAIN_OWNS_SPRINT_CLOSE` is true."""
    if not _owns_sprint_close():
        logger.info("BRAIN_OWNS_SPRINT_CLOSE is not true — skipping brain_sprint_close job")
        return
    scheduler.add_job(
        run_sprint_close,
        trigger=CronTrigger.from_crontab("0 21 * * 5", timezone=timezone.utc),
        id=_JOB_ID,
        name="Sprint Close (Brain, ex–Sprint Close / n8n)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info("APScheduler job %r registered (21:00 UTC Fridays, matches n8n expression)", _JOB_ID)
