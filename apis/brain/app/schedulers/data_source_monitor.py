"""Data source URL monitor from Brain APScheduler (Track K — P2.8).

Replaces the **Data Source Monitor (P2.8)** n8n workflow (``0 6 * * 1``) that
hashes external tax-data pages and posts to Slack — see
``infra/hetzner/workflows/retired/data-source-monitor.json`` and
``docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md``.

State persists in Redis (``brain:data_source_monitor:hashes``) when available; otherwise an
in-memory map for the process lifetime (same pattern as ``infra_health.py``).
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import httpx
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.schedulers._history import N8nMirrorRunSkipped, run_with_scheduler_record
from app.services import slack_outbound

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

JOB_ID = "brain_data_source_monitor"
_REDIS_KEY = "brain:data_source_monitor:hashes"
_SLACK_CHANNEL_ID = "C0ALVM4PAE7"
_USER_AGENT = "Mozilla/5.0 (compatible; PaperworkLabs/1.0; data-monitor)"
_HTTP_TIMEOUT = 15.0

# Process-local fallback when Redis is not initialized or set/get fails.
_mem_hashes: dict[str, str] = {}

_SOURCES: tuple[tuple[str, str, str], ...] = (
    (
        "tf_income_rates",
        "Tax Foundation - State Income Tax Rates",
        "https://taxfoundation.org/data/all/state/state-income-tax-rates",
    ),
    (
        "tf_sales_rates",
        "Tax Foundation - State Sales Tax Rates",
        "https://taxfoundation.org/data/all/state/state-and-local-sales-tax-rates",
    ),
    (
        "tf_corp_rates",
        "Tax Foundation - State Corporate Tax Rates",
        "https://taxfoundation.org/data/all/state/state-corporate-income-tax-rates-brackets",
    ),
    (
        "llcreq_formation",
        "LLC Requirements by State (Formation)",
        "https://llcrequirements.com/",
    ),
    (
        "discern_franchise",
        "Discern Franchise Tax Info",
        "https://www.discern.com/resources/franchise-tax-information",
    ),
)


def _signed32_hash(text: str) -> str:
    """Match n8n ``Data Source Monitor`` rolling hash (``| 0`` per step)."""
    h = 0
    for ch in text:
        h = ((h << 5) - h + ord(ch)) & 0xFFFFFFFF
        if h & 0x80000000:
            h -= 0x100000000
    return str(h)


def _strip_html(body: str) -> str:
    t = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", body, flags=re.IGNORECASE)
    t = re.sub(r"<style[^>]*>[\s\S]*?</style>", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()[:50000]


def _format_slack_message(results: list[dict[str, Any]]) -> str:
    """Build Slack body matching ``data-source-monitor.json`` «Format Alert»."""
    changed = [r for r in results if r.get("changed")]
    errors = [r for r in results if r.get("status") == "error"]
    first_runs = [r for r in results if r.get("isFirstRun")]

    parts: list[str] = []
    if changed:
        parts.append(":rotating_light: *Data Source Changes Detected*\n")
        parts.append("The following tax data sources have changed since last check:")
        for c in changed:
            parts.append(f"\u2022 *{c['name']}*: <{c['url']}|View page>")
        parts.append(
            "\n:point_right: Run `pnpm parse:tax` and `pnpm review` in `packages/data` to update. Also run `pnpm parse:formation` if formation sources changed."  # noqa: E501
        )
    if errors:
        parts.append("\n:warning: *Source Fetch Errors*")
        for e in errors:
            parts.append(f"\u2022 {e['name']}: {e.get('error', '')}")
    if first_runs and not changed:
        parts.append(":white_check_mark: *Data Source Monitor — Baseline Set*\n")
        parts.append(
            f"Monitoring {len(results)} source(s). Will alert on content changes.",
        )
    return "\n".join(parts)


def _should_post_slack(results: list[dict[str, Any]]) -> bool:
    """Mirror n8n: empty output when no changes, no errors, and no first runs."""
    changed = [r for r in results if r.get("changed")]
    errors = [r for r in results if r.get("status") == "error"]
    first_runs = [r for r in results if r.get("isFirstRun")]
    return bool(changed or errors or first_runs)


async def _get_redis_or_none() -> Any:
    try:
        from app.redis import get_redis

        return get_redis()
    except RuntimeError:
        return None


async def _load_hashes(redis: Any) -> dict[str, str]:
    if redis is None:
        return dict(_mem_hashes)
    try:
        raw = await redis.get(_REDIS_KEY)
        if not raw:
            return {}
        data = json.loads(str(raw))
        if not isinstance(data, dict):
            return {}
        return {str(k): str(v) for k, v in data.items()}
    except Exception:
        logger.debug("data_source_monitor: redis read failed; using memory", exc_info=True)
        return dict(_mem_hashes)


async def _save_hashes(redis: Any, hashes: dict[str, str]) -> None:
    global _mem_hashes
    if redis is None:
        _mem_hashes = dict(hashes)
        return
    try:
        await redis.set(_REDIS_KEY, json.dumps(hashes, sort_keys=True))
    except Exception:
        logger.debug("data_source_monitor: redis write failed; memory fallback", exc_info=True)
        _mem_hashes = dict(hashes)


async def _fetch_one(client: httpx.AsyncClient, url: str) -> str:
    res = await client.get(
        url,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "text/html",
        },
    )
    res.raise_for_status()
    return _strip_html(res.text)


async def _run_data_source_monitor_body() -> None:
    if not (settings.SLACK_BOT_TOKEN or "").strip():
        raise N8nMirrorRunSkipped()

    redis = await _get_redis_or_none()
    prior = await _load_hashes(redis)

    results: list[dict[str, Any]] = []
    next_hashes: dict[str, str] = {**prior}

    async with httpx.AsyncClient(
        timeout=_HTTP_TIMEOUT,
        follow_redirects=True,
    ) as client:
        for key, name, url in _SOURCES:
            try:
                text = await _fetch_one(client, url)
                hstr = _signed32_hash(text)
                prev = prior.get(key)
                changed = prev is not None and prev != hstr
                is_first = prev is None
                next_hashes[key] = hstr
                results.append(
                    {
                        "name": name,
                        "url": url,
                        "key": key,
                        "status": "ok",
                        "changed": changed,
                        "isFirstRun": is_first,
                        "contentLength": len(text),
                    },
                )
            except Exception as e:
                err = str(e)[:200]
                results.append(
                    {
                        "name": name,
                        "url": url,
                        "key": key,
                        "status": "error",
                        "error": err,
                        "changed": False,
                        "isFirstRun": False,
                        "contentLength": 0,
                    },
                )

    await _save_hashes(redis, next_hashes)

    if not _should_post_slack(results):
        raise N8nMirrorRunSkipped()

    msg = _format_slack_message(results)
    if not msg.strip():
        raise N8nMirrorRunSkipped()

    out = await slack_outbound.post_message(
        channel_id=_SLACK_CHANNEL_ID,
        text=msg,
        username="Data Quality",
        icon_emoji=":bar_chart:",
    )
    if not out.get("ok"):
        err = str(out.get("error") or "unknown_slack_error")
        raise RuntimeError(f"Slack post failed: {err}")


async def run_data_source_monitor() -> None:
    await run_with_scheduler_record(
        JOB_ID,
        _run_data_source_monitor_body,
        metadata={"source": "brain_data_source_monitor", "cutover": "T_K"},
        reraise=True,
    )


def install(scheduler: AsyncIOScheduler) -> None:
    """Register weekly source monitor (ex-Data Source Monitor P2.8 / n8n)."""
    scheduler.add_job(
        run_data_source_monitor,
        trigger=CronTrigger.from_crontab(
            "0 6 * * 1",
            timezone=ZoneInfo("America/Los_Angeles"),
        ),
        id=JOB_ID,
        name="Data Source Monitor (Brain, ex-Data Source Monitor (P2.8) / n8n)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info(
        "APScheduler job %r registered (Mon 06:00 America/Los_Angeles, n8n parity)",
        JOB_ID,
    )
