"""Persistent GitHub Actions billing + cache snapshots (quota monitor).

medallion: ops
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class GitHubActionsQuotaSnapshot(Base):
    __tablename__ = "github_actions_quota_snapshot"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    repo: Mapped[str] = mapped_column(Text, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False)
    minutes_used: Mapped[float | None] = mapped_column(Float, nullable=True)
    minutes_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    included_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paid_minutes_used: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_paid_minutes_used_breakdown: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    minutes_used_breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    cache_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cache_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extra_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
