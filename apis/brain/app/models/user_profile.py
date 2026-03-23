from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserProfile(Base):
    __tablename__ = "agent_user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str | None] = mapped_column(Text)
    domains: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    gmail_accounts: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    active_hours: Mapped[dict | None] = mapped_column(JSONB)
    communication_prefs: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    personality_snapshot: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    interaction_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    avg_quality_score: Mapped[float | None] = mapped_column(Float)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, server_default=text("'{}'::jsonb"))
