"""WS-69 PR O — prior-month expense rollup as a Brain Conversation (1st 9am PT)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.schemas.conversation import ConversationCreate
from app.services import conversations as conv_svc
from app.services import expenses as expense_svc

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_JOB_ID = "expense_monthly_close_pt"
_TZ = ZoneInfo("America/Los_Angeles")


def _prior_calendar_month(now_pt: datetime) -> tuple[int, int]:
    y, m = now_pt.year, now_pt.month
    if m == 1:
        return y - 1, 12
    return y, m - 1


def run_prior_month_close(now_pt: datetime | None = None) -> str | None:
    """Summarize the prior calendar month and create an info-level Conversation."""
    anchor = now_pt or datetime.now(_TZ)
    anchor = anchor.replace(tzinfo=_TZ) if anchor.tzinfo is None else anchor.astimezone(_TZ)

    year, month = _prior_calendar_month(anchor)
    rollup = expense_svc.compute_monthly_rollup(year, month)
    page = expense_svc.list_expenses(year=year, month=month, limit=5000)
    items = page.items

    _base = settings.FRONTEND_URL.rstrip("/")
    _csv_link = f"{_base}/api/admin/expenses/export.csv?year={year}&month={month}"

    lines: list[str] = [
        f"### Monthly expense close — **{year}-{month:02d}**",
        "",
        f"- **Total:** ${rollup.total_cents / 100:,.2f}",
        f"- **Approved:** ${rollup.approved_cents / 100:,.2f}",
        f"- **Pending:** ${rollup.pending_cents / 100:,.2f}",
        f"- **Flagged:** ${rollup.flagged_cents / 100:,.2f}",
        "",
        f"[Download CSV for this month]({_csv_link})",
        "",
        "**Reimbursable / follow-up checklist** (approved + pending):",
        "",
    ]
    reimb = [e for e in items if e.status in ("approved", "pending")]
    reimb.sort(key=lambda e: e.occurred_at)
    for e in reimb:
        chk = "[ ]"
        lines.append(
            f"- {chk} `{e.occurred_at}` **{e.vendor}** — "
            f"${e.amount_cents / 100:,.2f} · {e.category} · `{e.status}`"
        )
    if not reimb:
        lines.append("_No items in approved/pending for this month._")

    body = "\n".join(lines)

    def _mk() -> str:
        create = ConversationCreate(
            title=f"Expense monthly close — {year}-{month:02d}",
            body_md=body,
            tags=["expense-monthly-close"],
            urgency="info",
            persona="cfo",
            needs_founder_action=False,
        )
        conv = conv_svc.create_conversation(create)
        return conv.id

    derived = expense_svc.derived_repo_root_from_expense_store()
    if derived is not None:
        import os

        old = os.environ.get("REPO_ROOT")
        os.environ["REPO_ROOT"] = derived
        try:
            cid = _mk()
        finally:
            if old is None:
                os.environ.pop("REPO_ROOT", None)
            else:
                os.environ["REPO_ROOT"] = old
    else:
        cid = _mk()
    logger.info("expense_monthly_close: created conversation %s for %04d-%02d", cid, year, month)
    return cid


async def _run_job() -> None:
    try:
        await asyncio.to_thread(run_prior_month_close)
    except Exception:
        logger.exception("expense_monthly_close job failed")


def install(scheduler: AsyncIOScheduler) -> None:
    """First day of each month at 09:00 America/Los_Angeles."""
    scheduler.add_job(
        _run_job,
        trigger=CronTrigger(day=1, hour=9, minute=0, timezone=str(_TZ)),
        id=_JOB_ID,
        name="Expense monthly close (1st 9am PT)",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info("expense_monthly_close scheduled (1st of month 09:00 %s)", _TZ.key)
