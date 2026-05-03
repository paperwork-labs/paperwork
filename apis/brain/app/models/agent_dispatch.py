"""SQLAlchemy model for the agent_dispatches table.

Tracks every Task subagent dispatch with T-Shirt size (derived from
model_used), estimated/actual cost, and outcome. Feeds the Studio
/admin/cost dashboard and cost calibration loop.

medallion: ops
"""

from __future__ import annotations

import uuid
from datetime import (
    datetime,  # noqa: TC003 -- SQLAlchemy resolves Mapped[datetime] at mapper compile time
)

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

ALLOWED_MODELS = frozenset(
    {
        "composer-1.5",
        "composer-2-fast",
        "gpt-5.5-medium",
        "claude-4.6-sonnet-medium-thinking",
        "claude-4.5-opus-high-thinking",
        "claude-4.6-opus-high-thinking",
        "claude-opus-4-7-thinking-xhigh",
        "gpt-5.3-codex",
    }
)

CHEAP_MODELS = frozenset(
    {
        "composer-1.5",
        "composer-2-fast",
        "gpt-5.5-medium",
        "claude-4.6-sonnet-medium-thinking",
    }
)

MODEL_TO_SIZE: dict[str, str] = {
    "composer-1.5": "XS",
    "composer-2-fast": "S",
    "gpt-5.5-medium": "M",
    "claude-4.6-sonnet-medium-thinking": "L",
}

SIZE_COST_CENTS: dict[str, int] = {
    "XS": 10,
    "S": 40,
    "M": 100,
    "L": 300,
    "XL": 0,
}


class AgentDispatch(Base):
    """One row per Task subagent dispatch — T-Shirt sized, cost-tracked."""

    __tablename__ = "agent_dispatches"

    __table_args__ = (
        CheckConstraint(
            "t_shirt_size IN ('XS','S','M','L','XL')",
            name="ck_agent_dispatches_t_shirt_size",
        ),
        CheckConstraint(
            "model_used IN ("
            "'composer-1.5',"
            "'composer-2-fast',"
            "'gpt-5.5-medium',"
            "'claude-4.6-sonnet-medium-thinking',"
            "'claude-4.5-opus-high-thinking',"
            "'claude-4.6-opus-high-thinking',"
            "'claude-opus-4-7-thinking-xhigh',"
            "'gpt-5.3-codex'"
            ")",
            name="ck_agent_dispatches_model_used",
        ),
        CheckConstraint(
            "outcome IN ('pending','success','failed','blocked','cancelled')",
            name="ck_agent_dispatches_outcome",
        ),
        CheckConstraint(
            "(dispatched_by != 'subagent') OR (model_used NOT LIKE '%opus%')",
            name="ck_agent_dispatches_no_opus_as_subagent",
        ),
        Index(
            "idx_agent_dispatches_workstream_dispatched_at",
            "workstream_id",
            "dispatched_at",
        ),
        Index("idx_agent_dispatches_t_shirt_size", "t_shirt_size"),
        Index("idx_agent_dispatches_outcome", "outcome"),
        Index("idx_agent_dispatches_dispatched_at", "dispatched_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="paperwork-labs",
    )
    workstream_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    t_shirt_size: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str] = mapped_column(Text, nullable=False)
    subagent_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    branch: Mapped[str | None] = mapped_column(Text, nullable=True)
    pr_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pr_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    estimated_cost_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_cost_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    dispatched_by: Mapped[str] = mapped_column(Text, nullable=False)
