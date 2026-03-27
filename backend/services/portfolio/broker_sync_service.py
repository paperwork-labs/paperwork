"""
Broker-Agnostic Portfolio Sync Service
======================================

Universal sync coordinator that routes to broker-specific services.
This service provides a unified interface for syncing portfolio data
from any supported broker, while keeping the core models broker-neutral.
"""

import logging
import asyncio
from typing import Dict
from datetime import datetime

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


def _import_alpaca_service():
    """Lazy import for Alpaca to avoid circular dependencies."""
    from backend.services.portfolio.alpaca_sync_service import AlpacaSyncService
    return AlpacaSyncService()


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
        return [BrokerType.IBKR, BrokerType.TASTYTRADE, BrokerType.SCHWAB, BrokerType.ALPACA]

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
            BrokerType.ALPACA: _import_alpaca_service,
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
            result = _run(
                service.sync_account_comprehensive(
                    broker_account.account_number, session
                )
            )

            # Update sync status
            broker_account.last_successful_sync = datetime.now()
            from backend.models.broker_account import SyncStatus

            broker_account.sync_status = SyncStatus.SUCCESS
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
            except Exception:
                pass
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

            maybe_coro = service.sync_account_comprehensive(
                broker_account.account_number, session
            )
            import inspect

            result = await maybe_coro if inspect.isawaitable(maybe_coro) else maybe_coro

            broker_account.last_successful_sync = datetime.now()
            from backend.models.broker_account import SyncStatus

            broker_account.sync_status = SyncStatus.SUCCESS
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
            except Exception:
                pass
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
