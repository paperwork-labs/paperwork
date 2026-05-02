"""Product rows — Studio admin product registry (WS-82).

medallion: ops
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — needed at runtime by SQLAlchemy
from typing import Any

from sqlalchemy import DateTime, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    tagline: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), server_default=text("'active'"))
    domain: Mapped[str | None] = mapped_column(String(200))
    repo_path: Mapped[str | None] = mapped_column(String(200))
    vercel_project: Mapped[str | None] = mapped_column(String(200))
    render_services: Mapped[list[Any]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    tech_stack: Mapped[list[Any]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )
