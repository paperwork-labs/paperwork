from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from celery import shared_task

from backend.database import SessionLocal
from backend.models.broker_account import BrokerAccount, BrokerType, SyncStatus, AccountSync
from backend.services.portfolio.broker_sync_service import broker_sync_service

logger = logging.getLogger(__name__)

STALE_SYNC_THRESHOLD_MINUTES = 10


def _extract_count(result: dict, key: str) -> int | None:
    """Extract a sync count that may be a flat int or nested ``{"synced": N}``."""
    val = result.get(key)
    if isinstance(val, dict):
        return val.get("synced")
    if isinstance(val, (int, float)):
        return int(val)
    return None


SYNC_LOCK_TTL_SECONDS = 1020  # Must exceed time_limit (960s)


@shared_task(name="backend.tasks.account_sync.sync_account_task", soft_time_limit=900, time_limit=960)
def sync_account_task(account_id: int, sync_type: str = "comprehensive") -> dict:
    """Run broker account sync in a Celery worker (separate process).
    
    Uses Redis lock to prevent concurrent syncs for the same account.
    """
    # Acquire per-account lock to prevent concurrent syncs
    lock_key = f"sync:account:{account_id}"
    try:
        from backend.services.cache import redis_client
        lock_acquired = redis_client.set(
            lock_key, "1", nx=True, ex=SYNC_LOCK_TTL_SECONDS
        )
        if not lock_acquired:
            logger.warning(
                "Sync for account %s blocked by concurrent sync (lock held)", account_id
            )
            return {"status": "skipped", "error": "Sync already in progress"}
    except Exception as e:
        logger.warning("Redis lock failed for account %s sync, proceeding: %s", account_id, e)
    
    session = SessionLocal()
    sync_record = None
    started_at = datetime.now(timezone.utc)
    try:
        account = session.query(BrokerAccount).filter(BrokerAccount.id == account_id).first()
        if not account:
            return {"status": "error", "error": f"Account {account_id} not found"}

        account.sync_status = SyncStatus.RUNNING
        account.last_sync_attempt = started_at
        session.commit()

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

        completed_at = datetime.now(timezone.utc)
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
                    sync_record.transactions_synced = (
                        _extract_count(result, "cash_transactions")
                        or _extract_count(result, "transactions")
                    )
                    dr_start = result.get("data_range_start")
                    dr_end = result.get("data_range_end")
                    if dr_start:
                        try:
                            sync_record.data_range_start = datetime.strptime(str(dr_start), "%Y%m%d")
                        except (ValueError, TypeError):
                            pass
                    if dr_end:
                        try:
                            sync_record.data_range_end = datetime.strptime(str(dr_end), "%Y%m%d")
                        except (ValueError, TypeError):
                            pass
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
        if sync_record:
            try:
                sync_record.status = SyncStatus.ERROR
                sync_record.completed_at = datetime.now(timezone.utc)
                sync_record.duration_seconds = int(
                    (sync_record.completed_at - started_at).total_seconds()
                )
                sync_record.error_message = str(e)[:500]
                session.commit()
            except Exception as persist_err:
                logger.warning(
                    "Failed to persist sync error state for account %s: %s",
                    account_id,
                    persist_err,
                )
                session.rollback()

        # Also reset the BrokerAccount status so it's not stuck RUNNING
        try:
            session.rollback()
            acct = session.query(BrokerAccount).filter(BrokerAccount.id == account_id).first()
            if acct and acct.sync_status == SyncStatus.RUNNING:
                acct.sync_status = SyncStatus.ERROR
                acct.sync_error_message = str(e)[:500]
                session.commit()
        except Exception as reset_err:
            logger.warning(
                "Failed to reset BrokerAccount sync status after error for account %s: %s",
                account_id,
                reset_err,
            )
            session.rollback()

        return {"status": "error", "error": str(e)}
    finally:
        session.close()
        # Release sync lock
        try:
            from backend.services.cache import redis_client
            redis_client.delete(lock_key)
        except Exception:
            pass  # Lock will expire on TTL


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


@shared_task(name="backend.tasks.account_sync.sync_all_schwab_accounts")
def sync_all_schwab_accounts() -> dict:
    """Enqueue sync tasks for all enabled Schwab accounts."""
    session = SessionLocal()
    try:
        accounts = (
            session.query(BrokerAccount)
            .filter(
                BrokerAccount.broker == BrokerType.SCHWAB,
                BrokerAccount.is_enabled == True,
            )
            .all()
        )
        enqueued = 0
        results = []
        for acct in accounts:
            try:
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


@shared_task(name="backend.tasks.account_sync.recover_stale_syncs", soft_time_limit=60, time_limit=120)
def recover_stale_syncs() -> dict:
    """Periodic task to reset accounts stuck in RUNNING state.

    Should be scheduled every 5 minutes via Celery Beat or cron.
    """
    session = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=STALE_SYNC_THRESHOLD_MINUTES)
        stale_accounts = (
            session.query(BrokerAccount)
            .filter(
                BrokerAccount.sync_status == SyncStatus.RUNNING,
                BrokerAccount.last_sync_attempt < cutoff,
            )
            .all()
        )

        recovered = 0
        for acct in stale_accounts:
            logger.warning(
                "Recovering stale sync for account %s (stuck since %s)",
                acct.id, acct.last_sync_attempt,
            )
            acct.sync_status = SyncStatus.ERROR
            acct.sync_error_message = (
                f"Sync timed out (stuck RUNNING for >{STALE_SYNC_THRESHOLD_MINUTES} min). "
                "Auto-reset — please retry."
            )

            # Also close any orphaned AccountSync records
            stale_syncs = (
                session.query(AccountSync)
                .filter(
                    AccountSync.account_id == acct.id,
                    AccountSync.status == SyncStatus.RUNNING,
                    AccountSync.started_at < cutoff,
                )
                .all()
            )
            for sr in stale_syncs:
                sr.status = SyncStatus.ERROR
                sr.completed_at = datetime.now(timezone.utc)
                sr.duration_seconds = int((sr.completed_at - sr.started_at).total_seconds())
                sr.error_message = "Timed out — auto-recovered by recover_stale_syncs"

            recovered += 1

        session.commit()
        if recovered:
            logger.info("Recovered %d stale sync(s)", recovered)
        return {"recovered": recovered}
    except Exception as e:
        logger.error("Error in recover_stale_syncs: %s", e)
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close()
