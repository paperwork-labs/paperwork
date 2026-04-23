"""PlaidSyncService — BrokerSyncService-compatible adapter for Plaid.

Implements the ``sync_account_comprehensive(account_number, session,
user_id=...)`` contract consumed by
:class:`backend.services.portfolio.broker_sync_service.BrokerSyncService`.

Unlike the IBKR service this one is synchronous — the Plaid SDK is
blocking and the returned payload is small, so there's no benefit to
an async wrapper.

Return shape matches the other broker services:
``{"status": "success"|"error"|"partial", "pipeline": {...}, "error": "..."}``
so the dispatcher can interpret completeness consistently.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.models.broker_account import BrokerAccount
from backend.models.plaid_connection import (
    PlaidConnection,
    PlaidConnectionStatus,
)
from backend.services.portfolio.plaid.client import (
    PlaidAPIError,
    PlaidClient,
    PlaidConfigurationError,
)
from backend.services.portfolio.plaid.pipeline import (
    PipelineResult,
    persist_holdings,
)

logger = logging.getLogger(__name__)


# Plaid error_codes that mean "the user must re-authorize the Item"
# (we cannot recover by retrying). Everything else is treated as
# transient and surfaces as ``status=error`` with the full error code
# attached so the admin health dimension can count occurrences.
_REAUTH_ERROR_CODES = {
    "ITEM_LOGIN_REQUIRED",
    "ITEM_LOCKED",
    "INVALID_CREDENTIALS",
    "INVALID_MFA",
    "INSUFFICIENT_CREDENTIALS",
    "USER_SETUP_REQUIRED",
    "PENDING_EXPIRATION",
    "PENDING_DISCONNECT",
    "ACCESS_NOT_GRANTED",
}


class PlaidSyncService:
    """Sync one Plaid-sourced broker account.

    This is a per-sync lightweight object; it does not cache the SDK
    client between calls so that settings changes (e.g. PLAID_ENV
    flipped in an operator session) take effect immediately.
    """

    def __init__(self, client_factory=None) -> None:
        # Factory is injectable for tests — default to the real client.
        self._client_factory = client_factory or PlaidClient

    # -- protocol compliance ---------------------------------------------

    def sync_account_comprehensive(
        self,
        account_number: str,
        session: Session,
        *,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Sync one Plaid-backed ``BrokerAccount`` row.

        Args:
            account_number: :attr:`BrokerAccount.account_number`. The
                dispatcher resolves by this string because it's unique
                per tenant; we re-lookup here so we own the session.
            session: SQLAlchemy session owned by the caller.
            user_id: Expected tenant id. When provided, the query is
                scoped so a poisoned account_number in another tenant
                can't be read (defence-in-depth vs. the caller's scoping).

        Returns:
            A dict with keys ``status``, ``pipeline``, and optionally
            ``error`` / ``error_code`` / ``item_id``.
        """
        query = session.query(BrokerAccount).filter(
            BrokerAccount.account_number == str(account_number)
        )
        if user_id is not None:
            query = query.filter(BrokerAccount.user_id == user_id)
        account: Optional[BrokerAccount] = query.first()
        if account is None:
            return {
                "status": "error",
                "error": f"Broker account {account_number!r} not found",
            }

        if (account.connection_source or "direct").lower() != "plaid":
            # Never happens if the dispatcher is correct — defence in depth.
            return {
                "status": "error",
                "error": (
                    f"account_id={account.id} connection_source="
                    f"{account.connection_source!r} is not Plaid"
                ),
            }

        connection = self._resolve_connection(
            session, user_id=account.user_id, broker_account=account
        )
        if connection is None:
            return {
                "status": "error",
                "error": (
                    f"No PlaidConnection found for user_id={account.user_id} "
                    f"account_id={account.id}"
                ),
            }

        try:
            client = self._client_factory()
        except PlaidConfigurationError as exc:
            logger.error("Plaid not configured; sync skipped: %s", exc)
            connection.mark_error(str(exc))
            session.flush()
            return {
                "status": "error",
                "error": "Plaid not configured",
                "item_id": connection.item_id,
            }

        try:
            payload = client.get_holdings(connection.access_token_encrypted)
        except PlaidAPIError as exc:
            return self._handle_plaid_error(connection, session, exc)
        finally:
            client.close()

        # Build the plaid_account_id -> BrokerAccount map scoped to this
        # connection. In phase 1 a single BrokerAccount is mapped via its
        # ``account_number`` (which is the Plaid ``account_id`` per the
        # exchange route); when multi-account Items ship we iterate here.
        broker_accounts_by_plaid_id = self._map_plaid_accounts(
            session,
            user_id=account.user_id,
            plaid_accounts=payload.get("accounts") or [],
        )

        try:
            pipeline_result: PipelineResult = persist_holdings(
                session,
                user_id=account.user_id,
                item_id=connection.item_id,
                broker_accounts_by_plaid_id=broker_accounts_by_plaid_id,
                holdings_payload=payload,
            )
        except AssertionError:
            # Counter drift — re-raise so the task fails loudly and the
            # caller rolls back. NEVER silently swallow.
            connection.mark_error("counter drift in persist_holdings")
            raise

        connection.mark_synced(datetime.now(timezone.utc))
        session.flush()

        status: str = "success"
        if pipeline_result.errors > 0 and pipeline_result.written == 0:
            status = "error"
        elif pipeline_result.errors > 0:
            status = "partial"

        return {
            "status": status,
            "pipeline": pipeline_result.to_dict(),
            "item_id": connection.item_id,
        }

    # -- helpers ---------------------------------------------------------

    def _resolve_connection(
        self,
        session: Session,
        *,
        user_id: int,
        broker_account: BrokerAccount,
    ) -> Optional[PlaidConnection]:
        """Find the PlaidConnection backing a BrokerAccount.

        Single-Item association (current scope): the
        ``BrokerAccount.account_number`` stores the Plaid ``account_id``,
        and Plaid ``account_id``\\ s are globally unique, so we look up the
        single ACTIVE/NEEDS_REAUTH/ERROR connection for this user. When
        multi-Item support lands the caller must attach a
        ``plaid_connection_id`` to the account; raise loudly here if we
        ever see >1 candidate connection without that disambiguator.
        """
        connections: List[PlaidConnection] = (
            session.query(PlaidConnection)
            .filter(
                PlaidConnection.user_id == user_id,
                PlaidConnection.status != PlaidConnectionStatus.REVOKED.value,
            )
            .all()
        )
        if not connections:
            return None
        if len(connections) == 1:
            return connections[0]
        # Multi-connection disambiguation is a phase-2 concern; until a
        # mapping table exists we surface a clear error rather than
        # silently picking one.
        logger.warning(
            "user_id=%s has %d active PlaidConnection rows; phase 1 "
            "supports one — refusing to guess",
            user_id,
            len(connections),
        )
        return None

    def _map_plaid_accounts(
        self,
        session: Session,
        *,
        user_id: int,
        plaid_accounts: List[Dict[str, Any]],
    ) -> Dict[str, BrokerAccount]:
        """Map ``plaid_account_id`` -> :class:`BrokerAccount` for this user.

        The Plaid ``account_id`` is stored in
        ``BrokerAccount.account_number`` for ``connection_source='plaid'``
        rows (populated by the exchange route). That's the join key.
        """
        ids = [a.get("account_id") for a in plaid_accounts if a.get("account_id")]
        if not ids:
            return {}
        rows: List[BrokerAccount] = (
            session.query(BrokerAccount)
            .filter(
                BrokerAccount.user_id == user_id,
                BrokerAccount.connection_source == "plaid",
                BrokerAccount.account_number.in_(ids),
            )
            .all()
        )
        return {r.account_number: r for r in rows}

    def _handle_plaid_error(
        self,
        connection: PlaidConnection,
        session: Session,
        exc: PlaidAPIError,
    ) -> Dict[str, Any]:
        """Classify a Plaid API error and update the connection row."""
        error_code = (exc.error_code or "").upper()
        message = exc.display_message or str(exc)
        if error_code in _REAUTH_ERROR_CODES:
            connection.mark_needs_reauth(f"{error_code}: {message}")
            session.flush()
            return {
                "status": "error",
                "error_code": error_code,
                "error": message,
                "item_id": connection.item_id,
            }
        connection.mark_error(f"{error_code or 'UNKNOWN'}: {message}")
        session.flush()
        return {
            "status": "error",
            "error_code": error_code or None,
            "error": message,
            "item_id": connection.item_id,
        }


__all__ = ["PlaidSyncService"]
