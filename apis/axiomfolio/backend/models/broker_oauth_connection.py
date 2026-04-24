"""BrokerOAuthConnection — generic OAuth credential store for any broker.

This is the persistence layer for the OAuth broker foundation. One row per
``(user_id, broker, provider_account_id)`` triple. Tokens are stored
**encrypted** using Fernet (see ``backend.services.oauth.encryption``); never
write plaintext into ``access_token_encrypted`` / ``refresh_token_encrypted``.

For OAuth 1.0a brokers (E*TRADE) ``refresh_token_encrypted`` holds the
encrypted ``access_token_secret`` since OAuth 1.0a has no refresh token
concept. The status machine and refresh/revoke flow are agnostic to that
detail thanks to the ``OAuthBrokerAdapter`` abstraction.
"""

from __future__ import annotations

import enum
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from . import Base


class OAuthBrokerType(str, enum.Enum):
    """Supported OAuth broker identifiers (must match migration CHECK)."""

    ETRADE_SANDBOX = "etrade_sandbox"
    ETRADE = "etrade"
    SCHWAB = "schwab"
    FIDELITY = "fidelity"
    TASTYTRADE = "tastytrade"
    IBKR = "ibkr"
    ROBINHOOD = "robinhood"
    TRADIER = "tradier"
    TRADIER_SANDBOX = "tradier_sandbox"
    COINBASE = "coinbase"


class OAuthConnectionStatus(str, enum.Enum):
    """Lifecycle states for a stored OAuth connection."""

    PENDING = "PENDING"           # initiate started, no token yet
    ACTIVE = "ACTIVE"             # token usable
    EXPIRED = "EXPIRED"           # token past expiry; needs refresh
    REVOKED = "REVOKED"           # user or provider revoked
    REFRESH_FAILED = "REFRESH_FAILED"  # permanent refresh failure; reauth required
    ERROR = "ERROR"               # transient/unknown error; retry safe


class BrokerOAuthConnection(Base):
    """Per-user OAuth credentials for a single broker + provider account."""

    __tablename__ = "broker_oauth_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # String columns (matched to migration CHECK constraints) keep schema
    # additions cheap; we don't need PG enum migrations every time we add a
    # broker.
    broker = Column(String(32), nullable=False)
    provider_account_id = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, default=OAuthConnectionStatus.PENDING.value)

    access_token_encrypted = Column(Text, nullable=True)
    refresh_token_encrypted = Column(Text, nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    scope = Column(Text, nullable=True)
    environment = Column(String(16), nullable=False, default="sandbox")

    last_refreshed_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    rotation_count = Column(Integer, nullable=False, default=0)

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
        # Postgres UNIQUE on nullable columns allows duplicate NULLs; normalize
        # with COALESCE so one row per (user, broker) when provider_account_id
        # is unknown (e.g. E*TRADE sandbox).
        Index(
            "uq_broker_oauth_user_broker_provider_norm",
            "user_id",
            "broker",
            func.coalesce(provider_account_id, ""),
            unique=True,
        ),
        Index("idx_broker_oauth_user_broker", "user_id", "broker"),
        Index("idx_broker_oauth_status_expiry", "status", "token_expires_at"),
    )

    def is_expiring_within(self, window: timedelta) -> bool:
        """Return True if the access token expires within ``window`` from now.

        Tokens with no expiry recorded are treated as not-expiring (callers
        should treat that as "let the provider tell us"). Tokens already past
        expiry return True.
        """

        if self.token_expires_at is None:
            return False
        now = datetime.now(timezone.utc)
        expires_at = self.token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at <= now + window

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<BrokerOAuthConnection id={self.id} user_id={self.user_id} "
            f"broker={self.broker} status={self.status}>"
        )
