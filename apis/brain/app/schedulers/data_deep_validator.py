"""Monthly data deep validator (Track K / P2.9 n8n cutover).

Replaces the **Data Deep Validator (P2.9)** n8n workflow (``0 3 1 * *``) that
samples state source JSON, cross-checks DOR pages vs repo tax data, and posts
to Slack — see ``infra/hetzner/workflows/data-deep-validator.json`` and
``docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md`` (Track K).
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.schedulers._history import N8nMirrorRunSkipped, run_with_scheduler_record
from app.services import slack_outbound

logger = logging.getLogger(__name__)

JOB_ID = "brain_data_deep_validator"
_GITHUB_REPO = "paperwork-labs/paperwork"
_SAMPLE_SIZE = 10
_CANDIDATE_YEARS = (2026, 2025, 2024)
_DOR_TIMEOUT_S = 15.0
_DOR_MAX_CHARS = 20000
_SLACK_CHANNEL_ID = "C0ALVM4PAE7"
_HTTP_TIMEOUT = 60.0
_DOR_UA = "Mozilla/5.0 (compatible; PaperworkLabs/1.0; data-validator)"


def _owns_data_deep_validator() -> bool:
    return os.getenv("BRAIN_OWNS_DATA_DEEP_VALIDATOR", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _strip_html(body: str) -> str:
    s = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", body, flags=re.IGNORECASE)
    s = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", s, flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:_DOR_MAX_CHARS]


def _pct_with_two_decimals(rate_bps: int) -> str:
    return f"{rate_bps / 100:.2f}"


def _top_rate_pct(income_tax: dict[str, Any]) -> str | None:
    t = income_tax.get("type")
    if t == "none":
        return None
    if t == "flat":
        bps = int(income_tax.get("flat_rate_bps") or 0)
        return _pct_with_two_decimals(bps)
    if t == "progressive":
        max_bps = 0
        brackets = income_tax.get("brackets") or {}
        for _k, blist in brackets.items():
            if not isinstance(blist, list):
                continue
            for b in blist:
                if isinstance(b, dict) and "rate_bps" in b:
                    rb = int(b["rate_bps"])
                    if rb > max_bps:
                        max_bps = rb
        return _pct_with_two_decimals(max_bps) if max_bps else "0.00"
    return None


def _check_dor_match(dor_text: str, top_rate: str) -> bool:
    """Match n8n: rateStr, altRateStr from parseFloat, and ``%`` suffix forms."""
    rate_str = re.sub(r"0$", "", top_rate)
    try:
        alt_rate_str = str(float(top_rate))
    except ValueError:
        alt_rate_str = top_rate
    if rate_str in dor_text:
        return True
    if alt_rate_str in dor_text:
        return True
    if f"{top_rate}%" in dor_text:
        return True
    if f"{alt_rate_str}%" in dor_text:
        return True
    return False


def _github_headers_json() -> dict[str, str]:
    h: dict[str, str] = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "PaperworkLabs-Brain/1.0 (data-deep-validator)",
    }
    token = (settings.GITHUB_TOKEN or "").strip()
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _github_headers_raw() -> dict[str, str]:
    h: dict[str, str] = {
        "Accept": "application/vnd.github.v3.raw",
        "User-Agent": "PaperworkLabs-Brain/1.0 (data-deep-validator)",
    }
    token = (settings.GITHUB_TOKEN or "").strip()
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


async def _list_source_files(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    url = f"https://api.github.com/repos/{settings.GITHUB_REPO or _GITHUB_REPO}/contents/packages/data/src/sources"
    r = await client.get(url, headers=_github_headers_json())
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        return []
    return [x for x in data if isinstance(x, dict)]


async def _run_data_deep_validator_body() -> None:
    if not (settings.SLACK_BOT_TOKEN or "").strip():
        raise N8nMirrorRunSkipped()

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        files = await _list_source_files(client)
        json_files = [
            f
            for f in files
            if str(f.get("name", "")).endswith(".json")
            and not str(f.get("name", "")).startswith("_")
        ]
        n = min(_SAMPLE_SIZE, len(json_files))
        if n <= 0:
            sample: list[dict[str, Any]] = []
        else:
            sample = random.sample(json_files, n)

        states: list[dict[str, Any]] = []
        for f in sample:
            down = f.get("download_url")
            if not down:
                continue
            try:
                r = await client.get(str(down), headers=_github_headers_json())
                r.raise_for_status()
                source = r.json()
            except Exception as e:  # noqa: BLE001 — mirror n8n: skip bad files
                logger.info("data_deep_validator: skip source %s: %s", f.get("name"), e)
                continue
            if not isinstance(source, dict):
                continue
            dor = source.get("dor")
            dor_url = dor.get("url") if isinstance(dor, dict) else None
            tf = source.get("tax_foundation")
            tax_foundation_url = tf.get("url") if isinstance(tf, dict) else None
            states.append(
                {
                    "state": source.get("state"),
                    "state_name": source.get("state_name"),
                    "dor_url": dor_url,
                    "tax_foundation_url": tax_foundation_url,
                }
            )

        results: list[dict[str, Any]] = []
        repo = (settings.GITHUB_REPO or _GITHUB_REPO).strip()
        for st in states:
            state = st.get("state")
            state_name = st.get("state_name")
            st_key = str(state or "?")
            st_label = str(state_name or st_key)
            result: dict[str, Any] = {
                "state": st_key,
                "state_name": st_label,
                "issues": [],
                "status": "ok",
            }
            if not state:
                result["status"] = "error"
                result["issues"].append("Missing state in source JSON")
                results.append(result)
                continue

            stored_data: dict[str, Any] | None = None
            for year in _CANDIDATE_YEARS:
                tax_url = f"https://api.github.com/repos/{repo}/contents/packages/data/src/tax/{year}/{state}.json"
                try:
                    tr = await client.get(tax_url, headers=_github_headers_raw())
                    if tr.status_code == 404:
                        continue
                    tr.raise_for_status()
                    stored_data = json.loads(tr.text)
                    break
                except Exception:  # noqa: BLE001
                    continue

            if not stored_data:
                result["status"] = "error"
                result["issues"].append("Could not fetch stored tax data from GitHub")
                results.append(result)
                continue

            dor_content = ""
            dor_url = st.get("dor_url")
            if dor_url:
                try:
                    dr = await client.get(
                        str(dor_url),
                        headers={"User-Agent": _DOR_UA, "Accept": "text/html"},
                        timeout=_DOR_TIMEOUT_S,
                    )
                    dr.raise_for_status()
                    dor_content = _strip_html(dr.text)
                except Exception as e:  # noqa: BLE001
                    result["issues"].append(f"DOR page fetch failed: {str(e)[:100]}")

            it = stored_data.get("income_tax")
            if dor_content and isinstance(it, dict):
                top = _top_rate_pct(it)
                if top is not None and str(it.get("type")) != "none":
                    if not _check_dor_match(dor_content, top) and len(dor_content) > 500:
                        result["issues"].append(
                            f"Top rate {top}% not found on DOR page (may be layout change)"
                        )

            results.append(result)

    with_issues = [r for r in results if r.get("issues") and len(r["issues"]) > 0]
    clean = [
        r
        for r in results
        if (not r.get("issues") or len(r["issues"]) == 0) and r.get("status") == "ok"
    ]
    total = len(results)
    n_clean = len(clean)
    n_issue = len(with_issues)

    parts: list[str] = [f"*Monthly Data Validator — {total} states sampled*\n"]
    if n_issue > 0:
        parts.append(":warning: *Issues Found*")
        for r in with_issues:
            iss = r.get("issues") or []
            bullet = f"\u2022 *{r.get('state')}* ({r.get('state_name')}): {'; '.join(iss)}"
            parts.append(bullet)
        parts.append("")

    parts.append(f":white_check_mark: {n_clean}/{total} states validated clean")
    if n_issue > 0:
        parts.append(
            "\n:point_right: Investigate flagged states. Run `pnpm review` for full check."
        )
    message = "\n".join(parts)

    out = await slack_outbound.post_message(
        channel_id=_SLACK_CHANNEL_ID,
        text=message,
        username="Data Quality",
        icon_emoji=":mag:",
        unfurl_links=False,
    )
    if not out.get("ok"):
        err = str(out.get("error") or "unknown_slack_error")
        raise RuntimeError(f"Slack post failed: {err}")


async def run_data_deep_validator() -> None:
    await run_with_scheduler_record(
        JOB_ID,
        _run_data_deep_validator_body,
        metadata={"source": "brain_data_deep_validator", "cutover": "T_K"},
        reraise=True,
    )


def install(scheduler: AsyncIOScheduler) -> None:
    """Register the job when :envvar:`BRAIN_OWNS_DATA_DEEP_VALIDATOR` is true."""
    if not _owns_data_deep_validator():
        logger.info(
            "BRAIN_OWNS_DATA_DEEP_VALIDATOR is not true — skipping brain_data_deep_validator job"
        )
        return
    scheduler.add_job(
        run_data_deep_validator,
        trigger=CronTrigger.from_crontab(
            "0 3 1 * *",
            timezone=ZoneInfo("America/Los_Angeles"),
        ),
        id=JOB_ID,
        name="Data Deep Validator (Brain, ex–Data Deep Validator P2.9 / n8n)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info(
        "APScheduler job %r registered (1st of month 03:00 America/Los_Angeles, n8n parity)",
        JOB_ID,
    )
