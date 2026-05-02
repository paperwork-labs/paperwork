"""Persistence for ingested Cursor agent transcript turn pairs.

medallion: ops
"""

from __future__ import annotations

import uuid  # noqa: TC003 — Mapped[uuid.UUID] column type
from datetime import datetime  # noqa: TC003 — needed at runtime by SQLAlchemy
from typing import Any

from sqlalchemy import DateTime, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TranscriptEpisode(Base):
    """One user→assistant turn extracted from a Cursor JSONL transcript."""

    __tablename__ = "transcript_episodes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    transcript_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    assistant_message: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    entities: Mapped[list[Any]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    persona_slugs: Mapped[list[Any]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    episode_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        server_default=text("'{}'::jsonb"),
    )
