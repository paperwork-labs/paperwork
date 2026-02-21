from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from celery import shared_task

from backend.database import SessionLocal
from backend.models.broker_account import BrokerAccount, BrokerType, SyncStatus, AccountSync
from backend.services.portfolio.broker_sync_service import broker_sync_service

logger = logging.getLogger(__name__)


def _extract_count(result: dict, key: str) -> int | None:
    """Extract a sync count that may be a flat int or nested ``{"synced": N}``."""
    val = result.get(key)
    if isinstance(val, dict):
        return val.get("synced")
    if isinstance(val, (int, float)):
        return int(val)
    return None


@shared_task(name="backend.tasks.account_sync.sync_account_task")
def sync_account_task(account_id: int, sync_type: str = "comprehensive") -> dict:
    """Run broker account sync in a Celery worker (separate process)."""
    session = SessionLocal()
    sync_record = None
    started_at = datetime.now()
    try:
        account = session.query(BrokerAccount).filter(BrokerAccount.id == account_id).first()
        if not account:
            return {"status": "error", "error": f"Account {account_id} not found"}

        account.sync_status = SyncStatus.RUNNING
        account.last_sync_attempt = started_at
        session.commit()

        # Create AccountSync row for history
        sync_record = AccountSync(
            account_id=account_id,
            sync_type=sync_type,
            status=SyncStatus.RUNNING,
            started_at=started_at,
            sync_trigger="manual",
        )
        session.add(sync_record)
        session.commit()
        session.refresh(sync_record)
        logger.info("Sync started for account %s (%s)", account_id, account.broker.value)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                broker_sync_service.sync_account_async(
                    account_id=account_id, db=session, sync_type=sync_type
                )
            )
        finally:
            loop.close()

        completed_at = datetime.now()
        duration_seconds = int((completed_at - started_at).total_seconds())

        is_error = isinstance(result, dict) and result.get("status") == "error"

        if sync_record:
            sync_record.completed_at = completed_at
            sync_record.duration_seconds = duration_seconds
            if is_error:
                sync_record.status = SyncStatus.ERROR
                sync_record.error_message = str(result.get("error", "Unknown error"))[:500]
            else:
                sync_record.status = SyncStatus.SUCCESS
                sync_record.error_message = None
                if isinstance(result, dict):
                    sync_record.positions_synced = _extract_count(result, "positions")
                    sync_record.transactions_synced = _extract_count(result, "transactions")
            session.commit()

        if is_error:
            logger.warning("Sync returned error for account %s: %s", account_id, result.get("error"))

        return (
            result
            if isinstance(result, dict)
            else {"status": "success", "data": result}
        )
    except Exception as e:
        logger.exception("Sync failed for account %s: %s", account_id, e)
        # Update AccountSync on error
        if sync_record:
            try:
                sync_record.status = SyncStatus.ERROR
                sync_record.completed_at = datetime.now()
                sync_record.duration_seconds = int(
                    (sync_record.completed_at - started_at).total_seconds()
                )
                sync_record.error_message = str(e)
                session.commit()
            except Exception:
                session.rollback()
        return {"status": "error", "error": str(e)}
    finally:
        session.close()


@shared_task(name="backend.tasks.account_sync.sync_all_ibkr_accounts")
def sync_all_ibkr_accounts() -> dict:
    """Enqueue sync tasks for all enabled IBKR accounts."""
    session = SessionLocal()
    try:
        accounts = (
            session.query(BrokerAccount)
            .filter(
                BrokerAccount.broker == BrokerType.IBKR,
                BrokerAccount.is_enabled == True,
            )
            .all()
        )
        enqueued = 0
        results = []
        for acct in accounts:
            try:
                # Use existing Celery task to perform the heavy sync
                from backend.tasks.celery_app import celery_app

                task = celery_app.send_task(
                    "backend.tasks.account_sync.sync_account_task",
                    args=[acct.id, "comprehensive"],
                )
                results.append({"account_id": acct.id, "task_id": task.id})
                enqueued += 1
            except Exception as e:
                results.append({"account_id": acct.id, "error": str(e)})

        return {"status": "queued", "enqueued": enqueued, "results": results}
    finally:
        session.close()
