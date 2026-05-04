"""SQL ORM models for the canonical Conversation store — Alembic 012 + 015.

``conversations``         : header row (title, timestamps, metadata JSONB)
``conversation_messages`` : per-message rows (content, role, tsvector, metadata JSONB)

The ``metadata`` / ``message_metadata`` JSONB columns carry all Pydantic-model
fields that do not have dedicated columns.  See ``services/conversations.py``
for the exact mapping.

medallion: ops
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — SQLAlchemy column runtime
from typing import Any
from uuid import UUID  # noqa: TC003 — SQLAlchemy PG_UUID column bindings

from sqlalchemy import DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ConversationRecord(Base):
    """Mirror row for ``conversations``."""

    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )


class ConversationMessageRecord(Base):
    """Mirror row for ``conversation_messages`` (Alembic 012 + 015)."""

    __tablename__ = "conversation_messages"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    persona_slug: Mapped[str | None] = mapped_column(String(100))
    model_used: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    # Added by migration 015 ─────────────────────────────────────────────────
    # TSVECTOR for full-text search; populated by trigger or explicit INSERT.
    content_tsv: Mapped[Any] = mapped_column(
        TSVECTOR,
        nullable=True,
        default=None,
    )
    message_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
