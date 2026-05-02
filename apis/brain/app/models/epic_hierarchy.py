"""Goal → Epic → Sprint → Task hierarchy for project management.

Replaces the old workstreams.json flat-file approach with proper relational
storage. Brain is the single source of truth; Studio reads via admin API.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Goal(Base):
    """Quarterly OKR — founder writes, Brain decomposes into epics."""
    __tablename__ = "goals"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    horizon: Mapped[str] = mapped_column(Text, nullable=False)
    metric: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    owner_employee_slug: Mapped[str | None] = mapped_column(Text)
    written_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    review_cadence_days: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, server_default="'{}'::jsonb")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    epics: Mapped[list[Epic]] = relationship(back_populates="goal", lazy="selectin")


class Epic(Base):
    """Multi-week initiative (was 'Workstream'). WS-XX IDs kept for back-compat."""
    __tablename__ = "epics"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    goal_id: Mapped[str | None] = mapped_column(Text, ForeignKey("goals.id"))
    owner_employee_slug: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    percent_done: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    brief_tag: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    related_plan: Mapped[str | None] = mapped_column(Text)
    blockers: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="'[]'::jsonb")
    last_activity: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, server_default="'{}'::jsonb")

    goal: Mapped[Goal | None] = relationship(back_populates="epics")
    sprints: Mapped[list[Sprint]] = relationship(back_populates="epic", lazy="selectin", order_by="Sprint.ordinal")
    tasks: Mapped[list[Task]] = relationship(back_populates="epic", lazy="noload")


class Sprint(Base):
    """1-2 week batch within an epic (was 'Wave')."""
    __tablename__ = "sprints"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    epic_id: Mapped[str] = mapped_column(Text, ForeignKey("epics.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    goal: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    lead_employee_slug: Mapped[str | None] = mapped_column(Text)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, server_default="'{}'::jsonb")

    epic: Mapped[Epic] = relationship(back_populates="sprints")
    tasks: Mapped[list[Task]] = relationship(back_populates="sprint", lazy="selectin", order_by="Task.ordinal")


class Task(Base):
    """Single PR or work item."""
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    sprint_id: Mapped[str | None] = mapped_column(Text, ForeignKey("sprints.id", ondelete="SET NULL"))
    epic_id: Mapped[str | None] = mapped_column(Text, ForeignKey("epics.id"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    github_pr: Mapped[int | None] = mapped_column(Integer)
    github_pr_url: Mapped[str | None] = mapped_column(Text)
    owner_employee_slug: Mapped[str | None] = mapped_column(Text)
    assignee: Mapped[str | None] = mapped_column(Text)
    brief_tag: Mapped[str | None] = mapped_column(Text)
    ordinal: Mapped[int | None] = mapped_column(Integer)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, server_default="'{}'::jsonb")

    sprint: Mapped[Sprint | None] = relationship(back_populates="tasks")
    epic: Mapped[Epic | None] = relationship(back_populates="tasks")
