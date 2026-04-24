"""Historical import run tracking for IBKR XML/CSV backfills."""

from __future__ import annotations

import enum

from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.sql import func

from . import Base


class HistoricalImportSource(str, enum.Enum):
    FLEX_XML = "flex_xml"
    CSV = "csv"


class HistoricalImportStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class HistoricalImportRun(Base):
    __tablename__ = "historical_import_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("broker_accounts.id", ondelete="CASCADE"), nullable=False, index=True)

    source = Column(
        SQLEnum(
            HistoricalImportSource,
            name="historicalimportsource",
            create_type=False,
        ),
        nullable=False,
    )
    status = Column(
        SQLEnum(
            HistoricalImportStatus,
            name="historicalimportstatus",
            create_type=False,
        ),
        nullable=False,
        default=HistoricalImportStatus.QUEUED,
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    date_from = Column(Date, nullable=True)
    date_to = Column(Date, nullable=True)
    chunk_count = Column(Integer, nullable=False, default=0)

    records_total = Column(Integer, nullable=False, default=0)
    records_written = Column(Integer, nullable=False, default=0)
    records_skipped = Column(Integer, nullable=False, default=0)
    records_errors = Column(Integer, nullable=False, default=0)

    import_metadata = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_historical_import_runs_user_account", "user_id", "account_id"),
    )
