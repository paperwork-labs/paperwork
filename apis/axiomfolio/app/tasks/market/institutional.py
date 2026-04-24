"""
SEC 13F institutional holdings ingestion tasks.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from celery import shared_task

from app.database import SessionLocal
from app.tasks.utils.task_utils import task_run

logger = logging.getLogger(__name__)


@shared_task(
    soft_time_limit=600,
    time_limit=720,
)
@task_run("fetch_13f_filings")
def sync_13f(days_back: int = 90, max_filings: int = 50) -> dict:
    """Fetch and parse recent SEC 13F filings for institutional holdings.

    Runs monthly to check for new 13F filings. Filings are quarterly with
    45-day delay, so monthly runs catch new filings efficiently.
    """
    session = SessionLocal()
    try:
        from app.services.market.sec_edgar import (
            fetch_and_parse_13f,
            fetch_recent_13f_filings,
            persist_13f_holdings,
        )

        filings = fetch_recent_13f_filings(
            days_back=days_back,
            max_filings=max_filings,
        )

        if not filings:
            return {"status": "no_filings_found", "processed": 0}

        processed = 0
        total_holdings = 0

        for filing in filings:
            url = filing.get("url")
            if not url:
                continue

            try:
                result = fetch_and_parse_13f(url)
                holdings = result.get("holdings", [])

                if holdings:
                    cik = result.get("institution_cik") or "UNKNOWN"
                    name = result.get("institution_name") or filing.get("title", "Unknown")
                    filing_date = datetime.now(UTC).date()
                    period_date = filing_date

                    inserted = persist_13f_holdings(
                        db=session,
                        institution_cik=cik,
                        institution_name=name,
                        filing_date=filing_date,
                        period_date=period_date,
                        holdings=holdings,
                    )
                    total_holdings += inserted
                    processed += 1

            except Exception as e:
                logger.warning("Failed to process 13F filing %s: %s", url, e)

        session.commit()
        return {
            "status": "ok",
            "filings_found": len(filings),
            "filings_processed": processed,
            "holdings_inserted": total_holdings,
        }
    except Exception:
        logger.exception("sync_13f failed")
        raise
    finally:
        session.close()
