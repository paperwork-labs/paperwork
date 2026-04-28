"""Render workspace quota snapshots (Brain quota monitor).

medallion: ops
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import Any

from sqlalchemy import BigInteger, DateTime, Float, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RenderQuotaSnapshot(Base):
    __tablename__ = "render_quota_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    month: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    pipeline_minutes_used: Mapped[float] = mapped_column(Float, nullable=False)
    pipeline_minutes_included: Mapped[float] = mapped_column(Float, nullable=False)
    bandwidth_gb_used: Mapped[float | None] = mapped_column(Float, nullable=True)
    bandwidth_gb_included: Mapped[float | None] = mapped_column(Float, nullable=True)
    unbilled_charges_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    services_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    datastores_storage_gb: Mapped[float | None] = mapped_column(Float, nullable=True)
    workspace_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    derived_from: Mapped[str] = mapped_column(Text, nullable=False)
    extra_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
