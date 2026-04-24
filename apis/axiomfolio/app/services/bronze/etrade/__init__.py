"""E*TRADE bronze-layer ingestion.

Sandbox-only currently. The live adapter is a sibling that requires E*TRADE to
approve the application first; adding it is a broker-id flip plus a base
URL swap, not a rewrite.

Public surface:

* :class:`ETradeBronzeClient` — thin wrapper around the signed-request
  helper living in ``app.services.oauth.etrade.ETradeSandboxAdapter``.
  Handles the four endpoints the sync needs (accounts/list, balance,
  portfolio, transactions) and never duplicates the OAuth 1.0a HMAC-SHA1
  signing logic.
* :class:`ETradeSyncService` — mirrors
  ``app.services.portfolio.schwab_sync_service.SchwabSyncService``:
  per-account ``sync_account_comprehensive(account_number, session)`` that
  writes positions, options, transactions, trades, dividends and balances.
  Emits ``written / skipped / errors`` counters per the no-silent-fallback
  rule.

Tokens live in ``app/models/broker_oauth_connection.py`` (not
``AccountCredentials``). The sync service looks up the connection by
``(user_id, broker)`` filtered to the two supported ids (``etrade`` and
``etrade_sandbox``) and decrypts via ``app.services.oauth.encryption``.

medallion: bronze
"""

from app.services.bronze.etrade.client import (
    ETradeAPIError,
    ETradeBronzeClient,
)
from app.services.bronze.etrade.sync_service import ETradeSyncService


__all__ = [
    "ETradeAPIError",
    "ETradeBronzeClient",
    "ETradeSyncService",
]
