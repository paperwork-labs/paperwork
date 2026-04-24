"""Celery task for historical XML/CSV portfolio backfills."""

from __future__ import annotations

import asyncio
import logging
from datetime import date

from celery import shared_task

from app.database import SessionLocal
from app.models.broker_account import BrokerAccount
from app.models.historical_import_run import (
    HistoricalImportRun,
    HistoricalImportSource,
)
from app.services.bronze.ibkr.historical_import import HistoricalImportService

logger = logging.getLogger(__name__)


@shared_task(
    name="app.tasks.portfolio.historical_import.run_historical_import",
    queue="heavy",
    soft_time_limit=3300,
    time_limit=3600,
    autoretry_for=(),
    max_retries=0,
)
def run_historical_import(
    run_id: int,
    user_id: int,
    account_id: int,
    source: str,
    date_from: str | None = None,
    date_to: str | None = None,
    csv_content: str | None = None,
    xml_content: str | None = None,
) -> dict:
    """Run a single historical import job for one tenant/account."""
    db = SessionLocal()
    try:
        account = (
            db.query(BrokerAccount)
            .filter(
                BrokerAccount.id == account_id,
                BrokerAccount.user_id == user_id,
            )
            .first()
        )
        if account is None:
            raise ValueError("Broker account not found for user")
        run = (
            db.query(HistoricalImportRun)
            .filter(
                HistoricalImportRun.id == run_id,
                HistoricalImportRun.user_id == user_id,
                HistoricalImportRun.account_id == account_id,
            )
            .first()
        )
        if run is None:
            raise ValueError("Historical import run not found for user")

        svc = HistoricalImportService(db)
        if source == HistoricalImportSource.FLEX_XML.value:
            if not date_from or not date_to:
                raise ValueError("date_from and date_to required for flex_xml imports")
            if xml_content:
                return svc.import_xml_content(
                    run=run,
                    account=account,
                    xml_content=xml_content,
                    date_from=date.fromisoformat(date_from),
                    date_to=date.fromisoformat(date_to),
                )
            return asyncio.run(
                svc.import_flex_xml(
                    run=run,
                    account=account,
                    date_from=date.fromisoformat(date_from),
                    date_to=date.fromisoformat(date_to),
                )
            )
        if source == HistoricalImportSource.CSV.value:
            if not csv_content:
                raise ValueError("csv_content required for csv imports")
            return svc.import_csv(run=run, account=account, csv_content=csv_content)
        raise ValueError(f"Unsupported source: {source}")
    except Exception:
        logger.exception(
            "historical import task failed run_id=%s account_id=%s user_id=%s",
            run_id,
            account_id,
            user_id,
        )
        raise
    finally:
        db.close()
