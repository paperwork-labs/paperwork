"""Persistence for workstream dispatcher logs and progress snapshots (Track Z)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WorkstreamDispatchLog(Base):
    __tablename__ = "workstream_dispatch_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workstream_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    dispatched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    github_workflow: Mapped[str] = mapped_column(Text, nullable=False)
    inputs_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    github_run_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WorkstreamProgressSnapshot(Base):
    __tablename__ = "workstream_progress_snapshot"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workstream_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    percent_done: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_status: Mapped[str] = mapped_column(Text, nullable=False)
    merged_pr_count: Mapped[int] = mapped_column(Integer, nullable=False)
    open_pr_count: Mapped[int] = mapped_column(Integer, nullable=False)
    denominator: Mapped[int] = mapped_column(Integer, nullable=False)
    extra_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
