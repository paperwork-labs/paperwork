"""Infra health monitor from Brain APScheduler (interval, T1 — Infra Health Check cutover).

Replaces the **Infra Health Check** n8n workflow (30-minute interval) that queries
the n8n REST API and posts deduped alerts to Slack — see
``infra/hetzner/workflows/retired/infra-health-check.json`` and
``docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md``.

This is the **first** first-party job using :class:`IntervalTrigger` (not
``CronTrigger``), distinct from ``brain_infra_heartbeat`` (daily cron, PR #166).
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.schedulers import infra_heartbeat
from app.schedulers._history import N8nMirrorRunSkipped, run_with_scheduler_record
from app.services import slack_outbound

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

JOB_ID = "brain_infra_health"
# ``infra-health-check.json`` «Evaluate and Dedup» (same channel id as in that workflow).
_SLACK_CHANNEL_ID = "C0ALVM4PAE7"
_REDIS_PREFIX = "brain:infra_health:"
_DEFAULT_REMINDER_HOURS = 4


def _reminder_hours() -> float:
    raw = (os.getenv("INFRA_HEALTH_REMINDER_HOURS") or "").strip()
    if not raw:
        return float(_DEFAULT_REMINDER_HOURS)
    try:
        return max(0.0, float(raw))
    except ValueError:
        return float(_DEFAULT_REMINDER_HOURS)


def _fingerprint(check: dict[str, Any]) -> str:
    """Match n8n «currentFingerprint»."""
    h = check.get("healthy")
    a = int(check.get("activeCount", 0))
    t = int(check.get("totalCount", 0))
    liv = str(check.get("livenessStatus", "000"))
    return f"{h}|{a}/{t}|{liv}"


def _format_issue_message(check: dict[str, Any]) -> str:
    parts: list[str] = [":rotating_light: *Infra Health Check — ISSUES DETECTED*\n"]
    parts.append(
        f"*Workflows*: {int(check.get('activeCount', 0))}/{int(check.get('totalCount', 0))} active"
    )
    inactive = check.get("inactiveNames") or []
    if isinstance(inactive, list) and inactive:
        names = ", ".join(str(n) for n in inactive if n)
        if names:
            parts.append(f"  Inactive: {names}")
    parts.append(f"*n8n liveness*: {check.get('livenessStatus', '000')}")
    return "\n".join(parts)


def _format_recovery_message(check: dict[str, Any]) -> str:
    a = int(check.get("activeCount", 0))
    t = int(check.get("totalCount", 0))
    return f":white_check_mark: *Infra Health Check — All clear*\n{a}/{t} workflows active. n8n healthy."  # noqa: E501


async def _get_redis_or_none() -> Any:
    try:
        from app.redis import get_redis

        return get_redis()
    except RuntimeError:
        return None


# Process-local fallback when Redis is not initialized.
_mem_fp: str | None = None
_mem_last_healthy: bool | None = None
_mem_last_slack_at: datetime | None = None


async def _load_dedup_state(redis: Any) -> tuple[str | None, bool | None, datetime | None]:
    if redis is None:
        return _mem_fp, _mem_last_healthy, _mem_last_slack_at
    try:
        prev_fp = await redis.get(f"{_REDIS_PREFIX}last_fingerprint")
        healthy_raw = await redis.get(f"{_REDIS_PREFIX}last_healthy")
        at_raw = await redis.get(f"{_REDIS_PREFIX}last_slack_at")
        prev_healthy: bool | None
        prev_healthy = None if healthy_raw is None else str(healthy_raw) == "1"
        last_slack: datetime | None = None
        if at_raw:
            try:
                last_slack = datetime.fromisoformat(str(at_raw).replace("Z", "+00:00"))
            except ValueError:
                last_slack = None
        return (str(prev_fp) if prev_fp else None, prev_healthy, last_slack)
    except Exception:
        logger.debug("infra_health: redis read failed; using in-memory state", exc_info=True)
        return _mem_fp, _mem_last_healthy, _mem_last_slack_at


async def _set_fp_and_healthy(redis: Any, fp: str, last_healthy: bool) -> None:
    global _mem_fp, _mem_last_healthy
    if redis is None:
        _mem_fp = fp
        _mem_last_healthy = last_healthy
        return
    try:
        await redis.set(f"{_REDIS_PREFIX}last_fingerprint", fp)
        await redis.set(f"{_REDIS_PREFIX}last_healthy", "1" if last_healthy else "0")
    except Exception:
        logger.debug("infra_health: redis write (fp) failed; memory fallback", exc_info=True)
        _mem_fp = fp
        _mem_last_healthy = last_healthy


async def _set_post_state(redis: Any, fp: str, last_healthy: bool, at: datetime) -> None:
    global _mem_fp, _mem_last_healthy, _mem_last_slack_at
    if redis is None:
        _mem_fp = fp
        _mem_last_healthy = last_healthy
        _mem_last_slack_at = at
        return
    try:
        pipe = redis.pipeline()
        pipe.set(f"{_REDIS_PREFIX}last_fingerprint", fp)
        pipe.set(f"{_REDIS_PREFIX}last_healthy", "1" if last_healthy else "0")
        pipe.set(
            f"{_REDIS_PREFIX}last_slack_at",
            at.astimezone(UTC).isoformat(),
        )
        await pipe.execute()
    except Exception:
        logger.debug("infra_health: redis write (post) failed; memory fallback", exc_info=True)
        _mem_fp = fp
        _mem_last_healthy = last_healthy
        _mem_last_slack_at = at


def _n8n_prev_healthy(stored: bool | None) -> bool:
    """``state.lastHealthy !== false`` in n8n."""
    if stored is None:
        return True
    return stored


async def _run_infra_health_body() -> None:
    if not (settings.SLACK_BOT_TOKEN or "").strip():
        raise N8nMirrorRunSkipped()

    check = await infra_heartbeat._fetch_n8n_workflow_check()
    fp = _fingerprint(check)
    h = bool(check.get("healthy"))
    redis = await _get_redis_or_none()
    prev_fp, stored_healthy, last_slack_at = await _load_dedup_state(redis)
    prev_healthy = _n8n_prev_healthy(stored_healthy)
    now = datetime.now(UTC)

    if prev_fp is not None and fp == prev_fp:
        if h:
            return
        rh = _reminder_hours()
        if rh <= 0 or last_slack_at is None or (now - last_slack_at) < timedelta(hours=rh):
            return
        text = _format_issue_message(check)
        result = await slack_outbound.post_message(
            channel_id=_SLACK_CHANNEL_ID,
            text=text,
            username="Engineering",
            icon_emoji=":gear:",
        )
        if not result.get("ok"):
            err = str(result.get("error") or "unknown_slack_error")
            raise RuntimeError(f"Slack post failed: {err}")
        await _set_post_state(redis, fp, h, now)
        return

    if not h:
        text = _format_issue_message(check)
        result = await slack_outbound.post_message(
            channel_id=_SLACK_CHANNEL_ID,
            text=text,
            username="Engineering",
            icon_emoji=":gear:",
        )
        if not result.get("ok"):
            err = str(result.get("error") or "unknown_slack_error")
            raise RuntimeError(f"Slack post failed: {err}")
        await _set_post_state(redis, fp, h, now)
        return
    if not prev_healthy:
        text = _format_recovery_message(check)
        result = await slack_outbound.post_message(
            channel_id=_SLACK_CHANNEL_ID,
            text=text,
            username="Engineering",
            icon_emoji=":gear:",
        )
        if not result.get("ok"):
            err = str(result.get("error") or "unknown_slack_error")
            raise RuntimeError(f"Slack post failed: {err}")
        await _set_post_state(redis, fp, h, now)
        return
    # fp changed (or first run) but n8n would not emit Slack (e.g. still healthy) — persist state only.  # noqa: E501
    await _set_fp_and_healthy(redis, fp, h)


async def run_infra_health() -> None:
    await run_with_scheduler_record(
        JOB_ID,
        _run_infra_health_body,
        metadata={"source": "brain_infra_health", "cutover": "T1_interval"},
        reraise=True,
    )


def install(scheduler: AsyncIOScheduler) -> None:
    """Register 30m Infra Health (ex-Infra Health Check / n8n)."""
    scheduler.add_job(
        run_infra_health,
        trigger=IntervalTrigger(minutes=30),
        id=JOB_ID,
        name="Infra Health Check (Brain, ex-Infra Health Check / n8n, IntervalTrigger)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info("APScheduler job %r registered (30m interval, IntervalTrigger)", JOB_ID)
