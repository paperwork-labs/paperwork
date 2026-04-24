"""Daily corporate-action sync + apply.

Single Celery entry point per day:

1. Resolve the tracked universe (same source as the rest of the
   market-data pipeline -- prevents drift between "what we fetch
   indicators for" and "what we adjust for splits").
2. Fetch new corp actions for those symbols since N days back. The
   default lookback is 7 days so a multi-day worker outage doesn't
   leave us with a permanent gap.
3. Apply every PENDING action whose ex_date <= today.

Routing
-------
* Queue: ``heavy``. The applier may touch every user's positions for
  every symbol with an ex-date today; soft cap is 1500s, hard cap
  1800s, both matched to ``job_catalog.timeout_s``.
* Lock TTL: 1900s (>= hard_time_limit per ``task_utils.task_run``).

Idempotency
-----------
* Fetcher upserts on ``(symbol, action_type, ex_date)``.
* Applier short-circuits non-PENDING actions and uses the unique
  constraint on ``AppliedCorporateAction(action, user, position, lot)``.
* Re-running the task -- even mid-day, even by hand -- never produces
  duplicate adjustments.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from celery import shared_task

from app.database import SessionLocal
from app.services.silver.corporate_actions.applier import CorporateActionApplier
from app.services.silver.corporate_actions.fetcher import CorporateActionFetcher
from app.tasks.utils.task_utils import (
    _get_tracked_symbols_safe,
    _set_task_status,
    task_run,
)

logger = logging.getLogger(__name__)


_SOFT_LIMIT_SECONDS = 1500
_HARD_LIMIT_SECONDS = 1800


@shared_task(
    name="app.tasks.corporate_actions.daily_apply.daily_corporate_actions",
    soft_time_limit=_SOFT_LIMIT_SECONDS,
    time_limit=_HARD_LIMIT_SECONDS,
    queue="heavy",
)
@task_run("daily_corporate_actions", lock_ttl_seconds=_HARD_LIMIT_SECONDS + 100)
def daily_corporate_actions(fetch_lookback_days: int = 7) -> Dict[str, Any]:
    """Fetch + apply pending corporate actions for the tracked universe.

    Args:
        fetch_lookback_days: how far back the fetcher asks for events.
            Default 7 -- enough buffer to recover from a multi-day
            worker outage without flooding FMP with re-fetches.

    Returns:
        Counter dict for ``JobRun.counters``. Shape mirrors the
        ApplyReport / FetchReport so the admin Operator Actions panel
        can render a single, structured payload.
    """
    _set_task_status("daily_corporate_actions", "running")
    today = datetime.now(timezone.utc).date()
    since = today - timedelta(days=fetch_lookback_days)

    session = SessionLocal()
    try:
        symbols = _get_tracked_symbols_safe(session)
        if not symbols:
            # No-silent-fallback: warn loudly so admin /health can pick
            # up the degradation. We still run the applier in case
            # there are PENDING rows from a manual API call that need
            # to be processed.
            logger.warning(
                "daily_corporate_actions: tracked universe is empty; "
                "skipping fetch but still running applier"
            )
            fetch_counts = {
                "symbols_total": 0,
                "symbols_fetched": 0,
                "symbols_errored": 0,
                "actions_inserted": 0,
                "actions_skipped_duplicate": 0,
            }
        else:
            fetcher = CorporateActionFetcher(session)
            fetch_report = fetcher.fetch_for_symbols(symbols, since_date=since)
            session.commit()
            fetch_counts = {
                "symbols_total": fetch_report.symbols_total,
                "symbols_fetched": fetch_report.symbols_fetched,
                "symbols_errored": fetch_report.symbols_errored,
                "actions_inserted": fetch_report.actions_inserted,
                "actions_skipped_duplicate": (
                    fetch_report.actions_skipped_duplicate
                ),
            }

        applier = CorporateActionApplier(session)
        apply_report = applier.apply_pending(today=today)
        session.commit()

        counters = {
            "status": "ok",
            "ex_date_cutoff": today.isoformat(),
            "fetch": fetch_counts,
            "apply": {
                "actions_total": apply_report.actions_total,
                "actions_applied": apply_report.actions_applied,
                "actions_partial": apply_report.actions_partial,
                "actions_failed": apply_report.actions_failed,
                "actions_skipped": apply_report.actions_skipped,
                "positions_adjusted": apply_report.positions_adjusted,
                "tax_lots_adjusted": apply_report.tax_lots_adjusted,
                "ohlcv_rows_adjusted": apply_report.ohlcv_rows_adjusted,
            },
        }
        logger.info("daily_corporate_actions: %s", counters)
        return counters
    except Exception:
        # Roll back any uncommitted work so the next invocation starts
        # clean. The exception bubbles to ``task_run`` which records
        # it on JobRun and (per Brain config) raises a webhook.
        session.rollback()
        logger.exception("daily_corporate_actions failed")
        raise
    finally:
        session.close()
