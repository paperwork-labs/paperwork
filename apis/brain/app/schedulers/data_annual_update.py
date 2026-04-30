"""Annual tax data update reminder from Brain APScheduler (Track K / P2.10).

Replaces the **Annual Data Update Trigger (P2.10)** n8n workflow (``0 9 1 10 *``)
that posted the October checklist to the engineering channel — see
``infra/hetzner/workflows/retired/data-annual-update.json``.

WS-69 PR J: Slack post removed; output lands in the Brain Conversations stream.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger

from app.schedulers._history import run_with_scheduler_record
from app.schemas.conversation import ConversationCreate
from app.services.conversations import create_conversation

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

JOB_ID = "brain_data_annual_update"
_TAX_FOUNDATION_URL = "https://taxfoundation.org/data/all/state/state-income-tax-rates"


def _build_message(now: datetime) -> str:
    next_tax_year = now.year + 1
    checklist = [
        f"1. IRS Revenue Procedure for TY{next_tax_year} - check if released at "
        f"https://www.irs.gov/irb (IRS Internal Revenue Bulletin)",
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
        f"**Annual Tax Data Update — TY{next_tax_year}**\n",
        "It's October! Time to extract and validate tax data for the upcoming filing season.\n",
        "**Checklist:**",
    ]
    for item in checklist:
        parts.append(f"- {item}")
    parts.append(f"\n**Key resource**: {_TAX_FOUNDATION_URL}")
    return "\n".join(parts)


async def _run_data_annual_update_body() -> None:
    now = datetime.now(UTC)
    text = _build_message(now)
    next_tax_year = now.year + 1
    create_conversation(
        ConversationCreate(
            title=f"Annual Tax Data Update — TY{next_tax_year}",
            body_md=text,
            tags=["data"],
            urgency="normal",
            persona="ea",
            needs_founder_action=True,
        )
    )


async def run_data_annual_update() -> None:
    await run_with_scheduler_record(
        JOB_ID,
        _run_data_annual_update_body,
        metadata={"source": "brain_data_annual_update", "cutover": "T_K"},
        reraise=True,
    )


def install(scheduler: AsyncIOScheduler) -> None:
    """Register annual data update reminder (ex-P2.10 / n8n)."""
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
        misfire_grace_time=60,
    )
    logger.info(
        "APScheduler job %r registered (1 Oct 09:00 America/Los_Angeles, n8n parity)",
        JOB_ID,
    )
