"""
Broker-Agnostic Portfolio Sync Service
======================================

Universal sync coordinator that routes to broker-specific services.
This service provides a unified interface for syncing portfolio data
from any supported broker, while keeping the core models broker-neutral.
"""

import logging
import asyncio
import json
from typing import Dict
from datetime import datetime, timezone

from backend.database import SessionLocal
from backend.models import BrokerAccount
from backend.services.portfolio.ibkr import IBKRSyncService
from backend.services.portfolio.tastytrade_sync_service import TastyTradeSyncService
from backend.models.broker_account import BrokerType

logger = logging.getLogger(__name__)


def _import_schwab_service():
    """Lazy import for Schwab to avoid circular dependencies."""
    from backend.services.portfolio.schwab_sync_service import SchwabSyncService
    return SchwabSyncService()


def _import_etrade_service():
    """Lazy import for E*TRADE bronze sync service.

    The bronze package pulls in ``requests`` at import time for its HMAC-
    signed client; deferring keeps ``BrokerSyncService`` importable from
    test harnesses that stub broker I/O.
    """
    from backend.services.bronze.etrade import ETradeSyncService
    return ETradeSyncService()


def _import_tradier_service():
    """Lazy import for the Tradier bronze sync service.

    Same rationale as :func:`_import_etrade_service` — the bronze client
    imports ``requests`` eagerly; keep the dispatcher light to import.
    """
    from backend.services.bronze.tradier import TradierSyncService
    return TradierSyncService()


def _import_coinbase_service():
    """Lazy import for the Coinbase bronze sync service."""

    from backend.services.bronze.coinbase import CoinbaseSyncService
    return CoinbaseSyncService()


def _build_partial_sync_message(completeness: Dict) -> str:
    """Build a user-facing message for SyncStatus.PARTIAL (G22).

    The validator can return PARTIAL for two distinct reasons:
      1. Required sections missing from the broker report (``missing_required``).
      2. A pipeline writer errored on a section that *was* present
         (``pipeline_step_errored`` warning code, with ``missing_required`` empty).

    Reading only ``missing_required`` would render an empty ``[]`` in case (2),
    silently hiding the real cause. We instead derive the message from the
    structured ``warnings`` list so both failure modes surface accurately.
    Truncated to 500 chars to fit ``BrokerAccount.sync_error_message``.
    """
    completeness = completeness or {}
    missing = list(completeness.get("missing_required", []))
    warnings = completeness.get("warnings", []) or []
    errored_sections = sorted(
        {
            w.get("section")
            for w in warnings
            if isinstance(w, dict) and w.get("code") == "pipeline_step_errored"
        }
        - {None}
    )

    parts = []
    if missing:
        parts.append(f"missing required broker report sections {missing}")
    if errored_sections:
        parts.append(f"pipeline writer errored on {errored_sections}")

    if parts:
        return (
            f"Partial sync: {'; '.join(parts)}. See sync history for full warnings."
        )[:500]

    return (
        "Partial sync: pipeline reported degraded completeness; see sync history "
        "for details."
    )[:500]


class BrokerSyncService:
    """
    Universal broker sync service that coordinates between broker-specific services.

    This service:
    1. Routes sync requests to appropriate broker-specific services
    2. Ensures all data is stored in broker-agnostic models
    3. Provides unified sync interface for frontend
    4. Handles account management and sync orchestration
    """

    def __init__(self):
        # DI registry (instances) – tests can override per BrokerType
        self._broker_services = {}

    def get_available_brokers(self):
        return [
            BrokerType.IBKR,
            BrokerType.TASTYTRADE,
            BrokerType.SCHWAB,
            BrokerType.ETRADE,
            BrokerType.TRADIER,
            BrokerType.TRADIER_SANDBOX,
            BrokerType.COINBASE,
        ]

    def _get_broker_service(self, broker_type):
        from backend.models.broker_account import BrokerType

        if not isinstance(broker_type, BrokerType):
            raise ValueError(f"Unsupported broker: {broker_type}")

        # Return cached instance if available (enables DI in tests)
        if broker_type in self._broker_services:
            return self._broker_services[broker_type]

        # Factory registry with lazy imports to preserve @patch in tests
        factories = {
            BrokerType.IBKR: lambda: IBKRSyncService(),
            BrokerType.TASTYTRADE: lambda: TastyTradeSyncService(),
            BrokerType.SCHWAB: _import_schwab_service,
            BrokerType.ETRADE: _import_etrade_service,
            BrokerType.TRADIER: _import_tradier_service,
            BrokerType.TRADIER_SANDBOX: _import_tradier_service,
            BrokerType.COINBASE: _import_coinbase_service,
        }

        factory = factories.get(broker_type)
        if not factory:
            raise ValueError(f"Unsupported broker: {broker_type}")

        instance = factory()
        self._broker_services[broker_type] = instance
        return instance

    def sync_account(
        self, account_id: str, db=None, sync_type: str = "comprehensive"
    ) -> Dict:
        """
        Sync any broker account using the appropriate broker-specific service.

        Args:
            account_id: BrokerAccount.id in database
            sync_type: 'comprehensive', 'positions_only', 'transactions_only'
        """
        # Tests pass in db session directly
        session = db or SessionLocal()
        try:
            # Get broker account
            # Accept either DB primary key (int) or broker account_number (str)
            if isinstance(account_id, int):
                broker_account = (
                    session.query(BrokerAccount)
                    .filter(BrokerAccount.id == account_id)
                    .first()
                )
            else:
                broker_account = (
                    session.query(BrokerAccount)
                    .filter(BrokerAccount.account_number == str(account_id))
                    .first()
                )
            if not broker_account:
                return {
                    "status": "error",
                    "error": f"Broker account {account_id} not found",
                }

            logger.info(
                f"Starting {sync_type} sync for {broker_account.broker} account {broker_account.account_number}"
            )

            # Route to appropriate broker service
            service = self._get_broker_service(broker_account.broker)

            # Unified adapter for broker-specific implementations (sync or async)
            def _run(maybe_coro_or_value):
                import inspect

                if inspect.isawaitable(maybe_coro_or_value):
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Schedule onto current loop and wait
                        return loop.run_until_complete(maybe_coro_or_value)
                    else:
                        return loop.run_until_complete(maybe_coro_or_value)
                return maybe_coro_or_value

            # Enforce unified contract across all broker services
            if not hasattr(service, "sync_account_comprehensive"):
                raise ValueError(
                    f"Unsupported broker service implementation for: {broker_account.broker}"
                )
            # Multi-tenancy: pass user_id to services that accept it so
            # the downstream query is scoped to one tenant
            # (account_number is not globally unique). Older adapters
            # (Schwab/TT/IBKR) silently ignore the kwarg today — tighten when
            # each adapter is next touched.
            import inspect as _inspect
            _sig = _inspect.signature(service.sync_account_comprehensive)
            _kwargs: Dict[str, object] = {}
            if "user_id" in _sig.parameters:
                _kwargs["user_id"] = broker_account.user_id
            result = _run(
                service.sync_account_comprehensive(
                    broker_account.account_number, session, **_kwargs
                )
            )

            # Update sync status
            broker_account.last_successful_sync = datetime.now(timezone.utc)
            from backend.models.broker_account import SyncStatus

            broker_account.sync_status = SyncStatus.SUCCESS
            account_type_warnings = (
                result.get("account_type_warnings", [])
                if isinstance(result, dict)
                else []
            )
            if account_type_warnings:
                broker_account.sync_error_message = (
                    "ACCOUNT_TYPE_WARNING "
                    + json.dumps(account_type_warnings[:3], separators=(",", ":"))
                )[:500]
            else:
                broker_account.sync_error_message = None
            session.commit()

            return result

        except ValueError:
            # Let unknown broker errors propagate to tests
            raise
        except Exception as e:
            logger.error(f"Error syncing account {account_id}: {e}")
            # Update account status if possible
            try:
                from backend.models.broker_account import SyncStatus

                # Rollback failed work from underlying service first
                session.rollback()
                # Re-fetch a clean instance and persist error status
                if "broker_account" in locals() and broker_account:
                    fresh = (
                        session.query(BrokerAccount)
                        .filter(
                            BrokerAccount.account_number
                            == broker_account.account_number
                        )
                        .first()
                    )
                    if fresh:
                        fresh.sync_status = SyncStatus.ERROR
                        fresh.sync_error_message = str(e)
                        session.commit()
            except Exception as status_err:
                logger.warning(
                    "Failed to update sync error status for %s: %s", account_id, status_err
                )
            return {"status": "error", "error": str(e)}
        finally:
            if db is None:
                session.close()

    async def sync_account_async(
        self, account_id: str, db=None, sync_type: str = "comprehensive"
    ) -> Dict:
        """Async variant to avoid nested event loop issues under FastAPI."""
        session = db or SessionLocal()
        try:
            if isinstance(account_id, int):
                broker_account = (
                    session.query(BrokerAccount)
                    .filter(BrokerAccount.id == account_id)
                    .first()
                )
            else:
                broker_account = (
                    session.query(BrokerAccount)
                    .filter(BrokerAccount.account_number == str(account_id))
                    .first()
                )
            if not broker_account:
                return {
                    "status": "error",
                    "error": f"Broker account {account_id} not found",
                }

            logger.info(
                f"Starting {sync_type} sync for {broker_account.broker} account {broker_account.account_number}"
            )

            service = self._get_broker_service(broker_account.broker)

            if not hasattr(service, "sync_account_comprehensive"):
                raise ValueError(
                    f"Unsupported broker service implementation for: {broker_account.broker}"
                )

            # See note in sync_account(): scope to user_id for services
            # that accept it (E*TRADE today; other brokers to follow).
            import inspect as _inspect_async
            _sig_async = _inspect_async.signature(service.sync_account_comprehensive)
            _kwargs_async: Dict[str, object] = {}
            if "user_id" in _sig_async.parameters:
                _kwargs_async["user_id"] = broker_account.user_id
            maybe_coro = service.sync_account_comprehensive(
                broker_account.account_number, session, **_kwargs_async
            )
            import inspect

            result = await maybe_coro if inspect.isawaitable(maybe_coro) else maybe_coro

            # G22 — honour completeness status from the pipeline.
            # Previously this always set SUCCESS regardless of pipeline outcome,
            # producing the "BrokerAccount=success but AccountSync=error" split
            # state that hid partial syncs. Now we map the result.status verbatim:
            #   "error"   -> SyncStatus.ERROR (no last_successful_sync update)
            #   "partial" -> SyncStatus.PARTIAL (last_successful_sync NOT bumped —
            #                staleness checks must continue to surface degradation;
            #                bumping the success timestamp on a degraded sync would
            #                mask ongoing completeness problems from health monitors)
            #   else      -> SyncStatus.SUCCESS
            from backend.models.broker_account import SyncStatus

            result_status = result.get("status") if isinstance(result, dict) else None

            if result_status == "error":
                broker_account.sync_status = SyncStatus.ERROR
                broker_account.sync_error_message = str(
                    result.get("error", "Unknown error")
                )[:500]
            elif result_status == "partial":
                broker_account.sync_status = SyncStatus.PARTIAL
                completeness = (
                    result.get("completeness", {}) if isinstance(result, dict) else {}
                )
                broker_account.sync_error_message = _build_partial_sync_message(
                    completeness
                )
            else:
                broker_account.last_successful_sync = datetime.now(timezone.utc)
                broker_account.sync_status = SyncStatus.SUCCESS
                account_type_warnings = (
                    result.get("account_type_warnings", [])
                    if isinstance(result, dict)
                    else []
                )
                if account_type_warnings:
                    broker_account.sync_error_message = (
                        "ACCOUNT_TYPE_WARNING "
                        + json.dumps(account_type_warnings[:3], separators=(",", ":"))
                    )[:500]
                else:
                    broker_account.sync_error_message = None
            session.commit()
            return result

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error syncing account {account_id}: {e}")
            try:
                from backend.models.broker_account import SyncStatus

                session.rollback()
                if "broker_account" in locals() and broker_account:
                    fresh = (
                        session.query(BrokerAccount)
                        .filter(
                            BrokerAccount.account_number
                            == broker_account.account_number
                        )
                        .first()
                    )
                    if fresh:
                        fresh.sync_status = SyncStatus.ERROR
                        fresh.sync_error_message = str(e)
                        session.commit()
            except Exception as status_err:
                logger.warning(
                    "Failed to update sync error status for %s: %s", account_id, status_err
                )
            return {"status": "error", "error": str(e)}
        finally:
            if db is None:
                session.close()

    def sync_all_accounts(self, db=None) -> Dict:
        """Sync all broker accounts for a user."""
        session = db or SessionLocal()
        try:
            accounts = (
                session.query(BrokerAccount)
                .filter(BrokerAccount.is_enabled == True)
                .all()
            )

            results = {}
            for account in accounts:
                account_key = f"{account.broker.value}_{account.account_number}"
                try:
                    results[account_key] = self.sync_account(
                        account.account_number, session
                    )
                except ValueError as ve:
                    # Skip unsupported brokers gracefully
                    results[account_key] = {"status": "skipped", "reason": str(ve)}
                    continue

            return results

        except Exception as e:
            logger.error(f"Error syncing all enabled accounts: {e}")
            return {"status": "error", "error": str(e)}
        finally:
            if db is None:
                session.close()


# Global instance
broker_sync_service = BrokerSyncService()
