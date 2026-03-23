from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Organization(Base):
    __tablename__ = "agent_organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    parent_organization_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    industry: Mapped[str | None] = mapped_column(Text)
    size_band: Mapped[str | None] = mapped_column(Text)
    brain_name: Mapped[str] = mapped_column(Text, server_default="Brain")
    persona_config: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    data_retention_days: Mapped[int | None] = mapped_column(Integer, server_default="365")
    pii_policy: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    ingestion_policy: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    onboarding_status: Mapped[str] = mapped_column(Text, server_default="setup")
    features_enabled: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    plan: Mapped[str] = mapped_column(Text, server_default="free")
    data_region: Mapped[str] = mapped_column(Text, server_default="us-west")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, server_default="{}")


class Team(Base):
    __tablename__ = "agent_teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, server_default="{}")


class TeamMember(Base):
    __tablename__ = "agent_team_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(50), server_default="member")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
