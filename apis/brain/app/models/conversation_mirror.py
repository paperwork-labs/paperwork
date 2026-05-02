"""SQL mirror tables for Conversation transcripts — Alembic 012.

JSON files under ``data/conversations/`` remain the Studio thread source-of-truth.
These rows augment persona-authored posts with a queryable Postgres history.

medallion: ops
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — SQLAlchemy column runtime
from typing import Any
from uuid import UUID  # noqa: TC003 — SQLAlchemy PG_UUID column bindings

from sqlalchemy import DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
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
    """Mirror row for ``conversation_messages``."""

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
