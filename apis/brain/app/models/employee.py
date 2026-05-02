"""Unified employee model — canonical source of truth for all personas.

Brain DB owns this. Two file types are generated from it:
- .cursor/rules/<slug>.mdc (Cursor IDE needs physical files)
- apis/brain/app/personas/specs/<slug>.yaml (Brain cold-start)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, Numeric, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Employee(Base):
    __tablename__ = "employees"

    slug: Mapped[str] = mapped_column(Text, primary_key=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)  # ai_persona | human | system
    role_title: Mapped[str] = mapped_column(Text, nullable=False)
    team: Mapped[str] = mapped_column(Text, nullable=False)

    # Personality — set during naming ceremony
    display_name: Mapped[str | None] = mapped_column(Text)
    tagline: Mapped[str | None] = mapped_column(Text)
    avatar_emoji: Mapped[str | None] = mapped_column(Text)
    voice_signature: Mapped[str | None] = mapped_column(Text)
    named_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    named_by_self: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))

    # Org graph
    reports_to: Mapped[str | None] = mapped_column(Text)  # slug of manager
    manages: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="'[]'::jsonb")

    # Brain runtime config
    description: Mapped[str] = mapped_column(Text, nullable=False)
    default_model: Mapped[str] = mapped_column(Text, nullable=False)
    escalation_model: Mapped[str | None] = mapped_column(Text)
    escalate_if: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="'[]'::jsonb")
    requires_tools: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    daily_cost_ceiling_usd: Mapped[float | None] = mapped_column(Numeric(10, 2))
    owner_channel: Mapped[str | None] = mapped_column(Text)
    mode: Mapped[str | None] = mapped_column(Text)
    tone_prefix: Mapped[str | None] = mapped_column(Text)
    proactive_cadence: Mapped[str | None] = mapped_column(Text)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer)
    requests_per_minute: Mapped[int | None] = mapped_column(Integer)

    # Cursor IDE config
    cursor_description: Mapped[str | None] = mapped_column(Text)
    cursor_globs: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="'[]'::jsonb")
    cursor_always_apply: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))

    # Ownership
    owned_rules: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="'[]'::jsonb")
    owned_runbooks: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="'[]'::jsonb")
    owned_workflows: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="'[]'::jsonb")
    owned_skills: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="'[]'::jsonb")

    # Body markdown for .mdc generation
    body_markdown: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, server_default="'{}'::jsonb"
    )
