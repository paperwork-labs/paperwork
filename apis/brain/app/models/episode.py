from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, SmallInteger, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Episode(Base):
    """
    Core memory unit. Each episode is a single piece of knowledge the Brain has
    learned — a conversation, document, insight, or observation.
    """

    __tablename__ = "agent_episodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[str] = mapped_column(Text, nullable=False)
    team_id: Mapped[int | None] = mapped_column(Integer)
    circle_id: Mapped[int | None] = mapped_column(Integer)
    user_id: Mapped[str | None] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(Text, server_default=text("'organization'"))
    verified: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str | None] = mapped_column(Text)
    channel: Mapped[str | None] = mapped_column(Text)
    persona: Mapped[str | None] = mapped_column(Text)
    persona_tier: Mapped[str | None] = mapped_column(Text)
    product: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    full_context: Mapped[str | None] = mapped_column(Text)
    # embedding stored as pgvector VECTOR(1536) — added via raw SQL in migration
    embedding_model: Mapped[str] = mapped_column(Text, server_default=text("'text-embedding-3-small'"))
    importance: Mapped[float] = mapped_column(Float, server_default=text("0.5"))
    freshness: Mapped[float] = mapped_column(Float, server_default=text("1.0"))
    quality_signal: Mapped[int | None] = mapped_column(SmallInteger)
    model_used: Mapped[str | None] = mapped_column(Text)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Float)
    visual_context_url: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, server_default=text("'{}'::jsonb"))
