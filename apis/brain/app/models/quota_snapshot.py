"""Append-only vendor quota snapshots (Vercel, Render, GitHub Actions — parallel tables).

medallion: ops
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Float, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class VercelQuotaSnapshot(Base):
    __tablename__ = "vercel_quota_snapshot"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    project_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    project_name: Mapped[str] = mapped_column(Text, nullable=False)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    deploy_count: Mapped[int] = mapped_column(Integer, nullable=False)
    build_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    source_breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
