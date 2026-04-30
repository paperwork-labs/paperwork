"""Credential expiry check from Brain APScheduler (T1.4).

Replaces the **Credential Expiry Check** n8n workflow (``0 8 * * *``) that
fetched the Studio vault secret list, bucketed expiries, and conditionally
posted to the engineering channel — see
``infra/hetzner/workflows/retired/credential-expiry-check.json``.

WS-69 PR J: Slack post removed; alerts land in the Brain Conversations stream.
Urgency is derived from days-to-expiry: critical ≤1d, high ≤7d, normal ≤30d.
"""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import httpx
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.schedulers._history import SchedulerRunSkipped, run_with_scheduler_record
from app.schemas.conversation import ConversationCreate, UrgencyLevel
from app.services.conversations import create_conversation

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

JOB_ID = "brain_credential_expiry"
_HTTP_TIMEOUT = 30.0


def _format_expiry_body(secrets: list[dict[str, Any]]) -> tuple[bool, str, UrgencyLevel]:
    """Return (should_post, message_markdown, urgency)."""
    now = datetime.now(UTC)
    expiring: list[dict[str, Any]] = []
    for s in secrets:
        raw = s.get("expires_at")
        if not raw:
            continue
        try:
            exp = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        days_left = math.ceil((exp - now).total_seconds() / (24 * 60 * 60))
        expires_date = exp.date().isoformat()
        name = s.get("name") or "?"
        service = s.get("service")
        svc: str = service if isinstance(service, str) and service else "unknown"
        item = {
            "name": name,
            "service": svc,
            "daysLeft": days_left,
            "expiresDate": expires_date,
        }
        if days_left > -7 and days_left <= 30:
            expiring.append(item)

    expiring.sort(key=lambda x: int(x["daysLeft"]))

    if not expiring:
        return False, "No credentials expiring within 30 days.", "info"

    critical = [x for x in expiring if int(x["daysLeft"]) <= 1]
    urgent = [x for x in expiring if 1 < int(x["daysLeft"]) <= 7]
    warning = [x for x in expiring if 7 < int(x["daysLeft"]) <= 14]
    notice = [x for x in expiring if 14 < int(x["daysLeft"]) <= 30]

    urgency: UrgencyLevel = "normal"
    if critical:
        urgency = "critical"
    elif urgent:
        urgency = "high"

    def _format_list(items: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for s in items:
            dl = int(s["daysLeft"])
            dur = "EXPIRED" if dl <= 0 else f"{dl} days"
            lines.append(f"  - **{s['name']}** ({s['service']}) — {dur} ({s['expiresDate']})")
        return "\n".join(lines)

    parts: list[str] = ["**Credential Expiry Report**\n"]
    if critical:
        parts.append(f"**EXPIRED / EXPIRING TODAY:**\n{_format_list(critical)}\n")
    if urgent:
        parts.append(f"**Expiring this week:**\n{_format_list(urgent)}\n")
    if warning:
        parts.append(f"**Expiring in 2 weeks:**\n{_format_list(warning)}\n")
    if notice:
        parts.append(f"**Expiring within 30 days:**\n{_format_list(notice)}\n")
    parts.append("Rotate these before expiry to avoid outages. See `.env.secrets` for locations.")
    return True, "\n".join(parts), urgency


async def _fetch_vault_secrets() -> list[dict[str, Any]]:
    api_key = (settings.SECRETS_API_KEY or "").strip()
    base = (settings.STUDIO_URL or "").strip()
    if not api_key or not base:
        raise RuntimeError("SECRETS_API_KEY or STUDIO_URL not configured")
    url = f"{base.rstrip('/')}/api/secrets"
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        res = await client.get(url, headers=headers)
    res.raise_for_status()
    body = res.json()
    if not body.get("success"):
        err = str(body.get("error") or "secrets_list_failed")
        raise RuntimeError(f"Vault list failed: {err}")
    data = body.get("data")
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


async def _run_credential_expiry_body() -> None:
    raw = await _fetch_vault_secrets()
    should_post, text, urgency = _format_expiry_body(raw)
    if not should_post:
        raise SchedulerRunSkipped()

    needs_founder_action = urgency in ("critical", "high")
    create_conversation(
        ConversationCreate(
            title="Credential Expiry Report",
            body_md=text,
            tags=["alert"],
            urgency=urgency,
            persona="ea",
            needs_founder_action=needs_founder_action,
        )
    )


async def run_credential_expiry_check() -> None:
    await run_with_scheduler_record(
        JOB_ID,
        _run_credential_expiry_body,
        metadata={"source": "brain_credential_expiry", "cutover": "T1.4"},
        reraise=True,
    )


def install(scheduler: AsyncIOScheduler) -> None:
    """Register credential expiry check (ex-Credential Expiry Check / n8n)."""
    scheduler.add_job(
        run_credential_expiry_check,
        trigger=CronTrigger.from_crontab("0 8 * * *", timezone=UTC),
        id=JOB_ID,
        name="Credential Expiry (Brain, ex-Credential Expiry Check / n8n)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info("APScheduler job %r registered (08:00 UTC, matches n8n expression)", JOB_ID)
