"""Annual tax data update reminder from Brain APScheduler (Track K / P2.10).

Replaces the **Annual Data Update Trigger (P2.10)** n8n workflow (``0 9 1 10 *``) that
posts the October checklist to ``#engineering`` — see
``infra/hetzner/workflows/data-annual-update.json`` and
``docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md`` (Track K).
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.schedulers._history import N8nMirrorRunSkipped, run_with_scheduler_record
from app.services import slack_outbound

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

JOB_ID = "brain_data_annual_update"
# Same as ``data-annual-update.json`` (``Format Checklist Message`` → post node).
_ENGINEERING_SLACK_CHANNEL_ID = "C0ALLEKR9FZ"
_TAX_FOUNDATION_URL = "https://taxfoundation.org/data/all/state/state-income-tax-rates"


def _owns_data_annual_update() -> bool:
    return os.getenv("BRAIN_OWNS_DATA_ANNUAL_UPDATE", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _build_message(now: datetime) -> str:
    """Slack text matching the n8n ``Format Checklist Message``
    + ``Build Update Checklist`` nodes.
    """
    next_tax_year = now.year + 1
    checklist = [
        f"1. IRS Revenue Procedure for TY{next_tax_year} - check if released at "
        f"<https://www.irs.gov/irb|IRS Internal Revenue Bulletin>",
        f"2. Download new Tax Foundation XLSX to packages/data/scripts/fixtures/, "
        f"then run `EXTRACT_TAX_YEAR={next_tax_year} pnpm parse:tax` in `packages/data`",
        "3. Run formation update: `pnpm parse:formation` (fees change annually)",
        "4. Run full review: `pnpm review` — fix all failures",
        "5. Run test suite: `pnpm test` — all 1700+ tests must pass",
        f"6. Add known-good anchor values for TY{next_tax_year} in `tests/sanity.test.ts`",
        "7. Run `pnpm review:approve` to stamp all data as human-reviewed",
        "8. Create PR and merge to main",
        "9. Verify CI passes on the PR",
        "10. Post confirmation to #engineering when done",
    ]
    parts: list[str] = [
        f":calendar: *Annual Tax Data Update — TY{next_tax_year}*\n",
        "It's October! Time to extract and validate tax data for the upcoming filing season.\n",
        "*Checklist:*",
    ]
    for item in checklist:
        parts.append(f"\u2022 {item}")
    parts.append(
        f"\n*Key resource*: <{_TAX_FOUNDATION_URL}|Tax Foundation State Income Tax Rates>"
    )
    parts.append("\n:thread: Reply in this thread with progress updates.")
    return "\n".join(parts)


async def _run_data_annual_update_body() -> None:
    if not (settings.SLACK_BOT_TOKEN or "").strip():
        raise N8nMirrorRunSkipped()
    now = datetime.now(UTC)
    text = _build_message(now)
    result = await slack_outbound.post_message(
        channel_id=_ENGINEERING_SLACK_CHANNEL_ID,
        text=text,
        username="Engineering",
        icon_emoji=":calendar:",
    )
    if not result.get("ok"):
        err = str(result.get("error") or "unknown_slack_error")
        raise RuntimeError(f"Slack post failed: {err}")


async def run_data_annual_update() -> None:
    await run_with_scheduler_record(
        JOB_ID,
        _run_data_annual_update_body,
        metadata={"source": "brain_data_annual_update", "cutover": "T_K"},
        reraise=True,
    )


def install(scheduler: AsyncIOScheduler) -> None:
    """Register the job when :envvar:`BRAIN_OWNS_DATA_ANNUAL_UPDATE` is true."""
    if not _owns_data_annual_update():
        logger.info(
            "BRAIN_OWNS_DATA_ANNUAL_UPDATE is not true — skipping brain_data_annual_update job"
        )
        return
    scheduler.add_job(
        run_data_annual_update,
        trigger=CronTrigger.from_crontab(
            "0 9 1 10 *",
            timezone=ZoneInfo("America/Los_Angeles"),
        ),
        id=JOB_ID,
        name="Annual Data Update (Brain, ex- Annual Data Update Trigger P2.10 / n8n)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    logger.info(
        "APScheduler job %r registered (1 Oct 09:00 America/Los_Angeles, n8n parity)",
        JOB_ID,
    )
