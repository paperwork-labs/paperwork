"""PlaidConnection — Plaid Investments aggregator credential store.

Mirrors :mod:`backend.models.broker_oauth_connection` in structure:

* Fernet-encrypted access token at rest (see
  :mod:`backend.services.oauth.encryption`). Plaintext is never written to
  this column.
* Status enum for the lifecycle (``active`` / ``needs_reauth`` / ``revoked``
  / ``error``) so the sync task and admin health dimension can distinguish
  transient failures from terminal re-auth.
* ``(user_id, status)`` composite index so the daily sync fan-out can
  cheaply enumerate only ``active`` connections per tenant.

One row per Plaid *Item*: a ``(user_id, institution_id, Plaid item_id)``
triple typically maps to one household of brokerage accounts
(``broker_accounts`` rows with ``connection_source='plaid'``).

See plan ``docs/plans/PLAID_FIDELITY_401K.md`` §1 and decision D130 in
``docs/KNOWLEDGE.md``. Migration: ``backend/alembic/versions/0075_plaid_integration.py``.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from . import Base


class PlaidConnectionStatus(str, enum.Enum):
    """Lifecycle states for a Plaid Item.

    Values are lowercase to match the ``VARCHAR(32)`` column and the
    migration CHECK constraint. String values (not SQLAlchemy Enum) so
    that adding a new state later is a data migration, not a Postgres
    ``ALTER TYPE`` dance.
    """

    ACTIVE = "active"           # token usable; sync allowed
    NEEDS_REAUTH = "needs_reauth"  # Plaid signalled ITEM_LOGIN_REQUIRED
    REVOKED = "revoked"         # user-initiated disconnect or Plaid revoke
    ERROR = "error"             # transient failure; sync will retry


class PlaidConnection(Base):
    """Per-user Plaid Item (aggregator-sourced broker connection).

    ``access_token_encrypted`` holds the Fernet ciphertext of the Plaid
    access token. Callers MUST decrypt via
    :func:`backend.services.oauth.encryption.decrypt` and must never log
    plaintext (``.cursor/rules/no-silent-fallback.mdc``: tokens are
    sensitive; logging plaintext is a security incident, not a warning).
    """

    __tablename__ = "plaid_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Plaid Item identifier. Unique across all users — Plaid guarantees it,
    # and a UNIQUE constraint catches the impossible "same item wired to two
    # tenants" case loudly instead of silently.
    item_id = Column(String(64), nullable=False, unique=True)

    # Fernet ciphertext of the Plaid access token. TEXT (not fixed width)
    # because MultiFernet output grows with key rotation metadata.
    access_token_encrypted = Column(Text, nullable=False)

    institution_id = Column(String(32), nullable=False)
    institution_name = Column(String(128), nullable=False)

    # Incremental-transactions cursor returned by
    # ``/investments/transactions/sync``. NULL on fresh connections; Plaid
    # recommends an unbounded-length opaque string so we pick TEXT-ish via
    # VARCHAR(256) which fits observed cursors in sandbox + production.
    transactions_cursor = Column(String(256), nullable=True)

    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)

    status = Column(
        String(32),
        nullable=False,
        default=PlaidConnectionStatus.ACTIVE.value,
        server_default=PlaidConnectionStatus.ACTIVE.value,
    )
    environment = Column(
        String(16),
        nullable=False,
        default="sandbox",
        server_default="sandbox",
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship("User")

    __table_args__ = (
        Index("idx_plaid_connections_user_status", "user_id", "status"),
    )

    # -- lifecycle helpers ---------------------------------------------------

    def mark_synced(self, at: datetime) -> None:
        """Record a successful sync and clear the last-error banner.

        Promotes ``error`` -> ``active`` so the next daily pass doesn't
        keep surfacing a stale error message after recovery. Does NOT
        touch ``needs_reauth`` — only a re-exchange of ``public_token`` or
        explicit operator action should clear that state.
        """
        self.last_sync_at = at
        self.last_error = None
        if self.status == PlaidConnectionStatus.ERROR.value:
            self.status = PlaidConnectionStatus.ACTIVE.value

    def mark_error(self, message: str) -> None:
        """Record a transient sync failure.

        ``message`` is truncated to fit the column's informal ~4KB budget
        and MUST NOT contain plaintext tokens. Callers that catch Plaid
        ``ApiException`` should pass ``str(exc)`` or a redacted summary.
        """
        self.status = PlaidConnectionStatus.ERROR.value
        self.last_error = (message or "unknown error")[:4000]

    def mark_needs_reauth(self, message: Optional[str] = None) -> None:
        """Record that Plaid requires the user to reauthorize the Item."""
        self.status = PlaidConnectionStatus.NEEDS_REAUTH.value
        if message is not None:
            self.last_error = message[:4000]

    def mark_revoked(self) -> None:
        """Record a successful user-initiated revoke at Plaid."""
        self.status = PlaidConnectionStatus.REVOKED.value
        self.last_error = None

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<PlaidConnection id={self.id} user_id={self.user_id} "
            f"item_id={self.item_id!r} status={self.status}>"
        )
