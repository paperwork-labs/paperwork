from datetime import datetime

from sqlalchemy import DateTime, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Summary(Base):
    """Periodic roll-up of episodes into higher-level summaries."""

    __tablename__ = "agent_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[str] = mapped_column(Text, nullable=False)
    team_id: Mapped[int | None] = mapped_column(Integer)
    user_id: Mapped[str | None] = mapped_column(Text)
    period: Mapped[str] = mapped_column(Text, nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    # embedding stored as pgvector VECTOR(1536)
    key_decisions: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    key_entities: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    episode_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    model_used: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
