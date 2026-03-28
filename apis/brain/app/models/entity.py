from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Entity(Base):
    """Knowledge graph node — a person, concept, tool, or thing the Brain knows about."""

    __tablename__ = "agent_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[str] = mapped_column(Text, nullable=False)
    team_id: Mapped[int | None] = mapped_column(Integer)
    circle_id: Mapped[int | None] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_name: Mapped[str | None] = mapped_column(Text)
    # embedding stored as pgvector VECTOR(1536)
    summary: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, server_default=text("0.5"))
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    mention_count: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    status: Mapped[str] = mapped_column(Text, server_default=text("'active'"))
    properties: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))


class EntityEdge(Base):
    """Knowledge graph edge — a relationship between two entities."""

    __tablename__ = "agent_entity_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    target_entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    relation_type: Mapped[str] = mapped_column(Text, nullable=False)
    weight: Mapped[float] = mapped_column(Float, server_default=text("1.0"))
    evidence_episode_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, server_default=text("'{}'::jsonb"))
