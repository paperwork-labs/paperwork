"""Credential expiry check from Brain APScheduler (T1.4).

Replaces the **Credential Expiry Check** n8n workflow (``0 8 * * *``) that
fetches the Studio vault secret list, buckets expiries, and conditionally
posts to Slack — see ``infra/hetzner/workflows/credential-expiry-check.json`` and
``docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md`` (T1.4).
"""

from __future__ import annotations

import logging
import math
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.schedulers._history import N8nMirrorRunSkipped, run_with_scheduler_record
from app.services import slack_outbound

logger = logging.getLogger(__name__)

JOB_ID = "brain_credential_expiry"
# Same channel as ``credential-expiry-check.json`` (``Post to #alerts`` node).
_CREDENTIAL_EXPIRY_SLACK_CHANNEL_ID = "C0ALVM4PAE7"
_HTTP_TIMEOUT = 30.0


def _owns_credential_expiry() -> bool:
    return os.getenv("BRAIN_OWNS_CREDENTIAL_EXPIRY", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _format_expiry_slack_text(secrets: list[dict[str, Any]]) -> tuple[bool, str]:
    """Return (should_post, message). ``should_post`` is False when n8n would no-op.

    Matches the n8n ``Check Expiry Dates`` code node (same buckets and markdown).
    """
    now = datetime.now(timezone.utc)
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
            exp = exp.replace(tzinfo=timezone.utc)
        days_left = int(math.ceil((exp - now).total_seconds() / (24 * 60 * 60)))
        expires_date = exp.date().isoformat()
        name = s.get("name") or "?"
        service = s.get("service")
        if isinstance(service, str) and service:
            svc: str = service
        else:
            svc = "unknown"
        item = {
            "name": name,
            "service": svc,
            "daysLeft": days_left,
            "expiresDate": expires_date,
        }
        if days_left > -7 and days_left <= 30:  # same as n8n: > -7 and <= 30
            expiring.append(item)

    expiring.sort(key=lambda x: int(x["daysLeft"]))

    if not expiring:
        return False, "No credentials expiring within 30 days."

    critical = [x for x in expiring if int(x["daysLeft"]) <= 1]
    urgent = [x for x in expiring if 1 < int(x["daysLeft"]) <= 7]
    warning = [x for x in expiring if 7 < int(x["daysLeft"]) <= 14]
    notice = [x for x in expiring if 14 < int(x["daysLeft"]) <= 30]

    emoji = ":clock1:"
    if critical:
        emoji = ":fire:"
    elif urgent:
        emoji = ":rotating_light:"
    elif warning:
        emoji = ":warning:"

    def _format_list(items: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for s in items:
            dl = int(s["daysLeft"])
            dur = "EXPIRED" if dl <= 0 else f"{dl} days"
            lines.append(f"  • *{s['name']}* ({s['service']}) — {dur} ({s['expiresDate']})")
        return "\n".join(lines)

    parts: list[str] = [f"{emoji} *Credential Expiry Report*\n"]
    if critical:
        parts.append(f":fire: *EXPIRED / EXPIRING TODAY:*\n{_format_list(critical)}\n")
    if urgent:
        parts.append(f":rotating_light: *Expiring this week:*\n{_format_list(urgent)}\n")
    if warning:
        parts.append(f":warning: *Expiring in 2 weeks:*\n{_format_list(warning)}\n")
    if notice:
        parts.append(f":clock1: *Expiring within 30 days:*\n{_format_list(notice)}\n")
    parts.append("_Rotate these before expiry to avoid outages. See `.env.secrets` for locations._")
    return True, "\n".join(parts)


async def _fetch_vault_secrets() -> list[dict[str, Any]]:
    """GET ``/api/secrets`` — same as n8n «Fetch Vault Secrets»."""
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
    out: list[dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict):
            out.append(item)
    return out


async def _run_credential_expiry_body() -> None:
    if not (settings.SLACK_BOT_TOKEN or "").strip():
        raise N8nMirrorRunSkipped()

    raw = await _fetch_vault_secrets()
    should_post, text = _format_expiry_slack_text(raw)
    if not should_post:
        raise N8nMirrorRunSkipped()

    result = await slack_outbound.post_message(
        channel_id=_CREDENTIAL_EXPIRY_SLACK_CHANNEL_ID,
        text=text,
        username="Engineering",
        icon_emoji=":key:",
    )
    if not result.get("ok"):
        err = str(result.get("error") or "unknown_slack_error")
        raise RuntimeError(f"Slack post failed: {err}")


async def run_credential_expiry_check() -> None:
    await run_with_scheduler_record(
        JOB_ID,
        _run_credential_expiry_body,
        metadata={"source": "brain_credential_expiry", "cutover": "T1.4"},
        reraise=True,
    )


def install(scheduler: AsyncIOScheduler) -> None:
    """Register the job when :envvar:`BRAIN_OWNS_CREDENTIAL_EXPIRY` is true."""
    if not _owns_credential_expiry():
        logger.info("BRAIN_OWNS_CREDENTIAL_EXPIRY is not true — skipping brain_credential_expiry job")
        return
    scheduler.add_job(
        run_credential_expiry_check,
        trigger=CronTrigger.from_crontab("0 8 * * *", timezone=timezone.utc),
        id=JOB_ID,
        name="Credential Expiry (Brain, ex–Credential Expiry Check / n8n)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info("APScheduler job %r registered (08:00 UTC, matches n8n expression)", JOB_ID)
