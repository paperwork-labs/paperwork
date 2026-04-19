"""Persisted AI-generated daily portfolio narratives."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.models import Base


class PortfolioNarrative(Base):
    """One row per (user, calendar date) daily narrative."""

    __tablename__ = "portfolio_narratives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    narrative_date: Mapped[date] = mapped_column(Date, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    summary_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "narrative_date", name="uq_portfolio_narrative_user_date"),
        Index("ix_portfolio_narrative_user_created", "user_id", "created_at"),
    )
