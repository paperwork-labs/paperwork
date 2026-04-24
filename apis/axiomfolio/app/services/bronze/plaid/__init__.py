"""Plaid Investments aggregator — read-only portfolio sync.

Mirror of ``app.services.bronze.ibkr`` in structure. Exports the
service classes used by the broker sync dispatcher and the Plaid API
routes.

Scope per plan ``docs/plans/PLAID_FIDELITY_401K.md``: holdings + balances
only (no trading — Plaid Investments doesn't expose order entry).

* :class:`PlaidClient` — thin SDK wrapper that also handles Fernet
  encrypt/decrypt of access tokens.
* :class:`PlaidSyncService` — implements the ``sync_account_comprehensive``
  protocol consumed by :class:`app.services.portfolio.broker_sync_service.BrokerSyncService`.
* :func:`persist_holdings` — pipeline that upserts :class:`Position` +
  :class:`TaxLot` rows from a holdings payload.

medallion: bronze
"""

from app.services.bronze.plaid.client import (  # noqa: F401
    PlaidAPIError,
    PlaidClient,
    PlaidConfigurationError,
)
from app.services.bronze.plaid.pipeline import (  # noqa: F401
    PipelineResult,
    persist_holdings,
)
from app.services.bronze.plaid.sync_service import PlaidSyncService  # noqa: F401

__all__ = [
    "PlaidAPIError",
    "PlaidClient",
    "PlaidConfigurationError",
    "PipelineResult",
    "persist_holdings",
    "PlaidSyncService",
]
