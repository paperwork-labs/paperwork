"""MCP (Model Context Protocol) bearer token for read-only portfolio access.

Each row is a per-user, revocable bearer credential issued from the
Settings UI. The plaintext token is shown to the operator exactly once
on creation and never persisted; only the SHA-256 hex digest is stored
so a database leak never yields usable credentials.

Tokens are scoped to one user (``user_id`` FK with ``ON DELETE CASCADE``)
and validated by ``backend/mcp/auth.py``. The accompanying transport
endpoint (``POST /api/v1/mcp/jsonrpc``) enforces that every tool call
runs against ``token.user_id`` — never a client-supplied id.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from . import Base


def _default_expires_at() -> datetime:
    """Default to a 1-year token lifetime in UTC.

    Explicitly timezone-aware so naive comparisons in `is_active` are
    impossible at the call site.
    """
    return datetime.now(UTC) + timedelta(days=365)


class MCPToken(Base):
    """Per-user bearer token granting read-only MCP tool access."""

    __tablename__ = "mcp_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    scopes: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pii_consent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_default_expires_at,
    )

    user = relationship("User", lazy="joined")

    __table_args__ = (Index("ix_mcp_tokens_user_revoked", "user_id", "revoked_at"),)

    def is_active(self, now: datetime | None = None) -> bool:
        """Return True iff the token is neither revoked nor expired."""
        if self.revoked_at is not None:
            return False
        ts = now or datetime.now(UTC)
        exp = self.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        return ts < exp

    def __repr__(self) -> str:
        return (
            f"<MCPToken id={self.id} user_id={self.user_id} "
            f"name={self.name!r} revoked={self.revoked_at is not None}>"
        )
