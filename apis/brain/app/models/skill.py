from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Skill(Base):
    """Platform skill registry (D62). Defines what the Brain can do.
    Tier column gates access: free, personal, team, enterprise."""

    __tablename__ = "brain_skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    tier: Mapped[str] = mapped_column(Text, server_default="free")
    connector_id: Mapped[str | None] = mapped_column(Text)
    tools: Mapped[dict] = mapped_column(JSONB, server_default="[]")
    knowledge_domains: Mapped[dict] = mapped_column(JSONB, server_default="[]")
    requires_connection: Mapped[bool] = mapped_column(Boolean, server_default="false")
    owner_organization_id: Mapped[str] = mapped_column(Text, server_default="platform")
    status: Mapped[str] = mapped_column(Text, server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserSkill(Base):
    """User-skill enablement (D62). Users "install" skills they want active."""

    __tablename__ = "brain_user_skills"

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    organization_id: Mapped[str] = mapped_column(Text, primary_key=True)
    skill_id: Mapped[str] = mapped_column(Text, primary_key=True)
    enabled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    config: Mapped[dict] = mapped_column(JSONB, server_default="{}")
