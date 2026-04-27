"""medallion: ops"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FormationStatus(StrEnum):
    DRAFT = "draft"
    DOCUMENTS_READY = "documents_ready"
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class FilingTier(StrEnum):
    API = "api"
    PORTAL = "portal"
    MAIL = "mail"


class Formation(Base):
    """LLC formation request — tracks a single formation from draft to confirmed."""

    __tablename__ = "formations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    state_code: Mapped[str] = mapped_column(String(2), nullable=False)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_purpose: Mapped[str] = mapped_column(
        Text, server_default=text("'Any lawful purpose'")
    )

    registered_agent: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    members: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    principal_address: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    mailing_address: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    status: Mapped[str] = mapped_column(
        String(50), server_default=text("'draft'"), nullable=False
    )
    filing_tier: Mapped[str] = mapped_column(
        String(20), server_default=text("'portal'"), nullable=False
    )

    filing_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confirmation_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    filed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    screenshots: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    error_log: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
