"""External auxiliary signals (Finviz, Zacks, etc.) — not primary strategy inputs."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from . import Base


class ExternalSignal(Base):
    __tablename__ = "external_signals"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "source",
            "signal_date",
            "signal_type",
            name="uq_external_signals_sym_src_day_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, doc="finviz | zacks")
    signal_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    signal_type: Mapped[str] = mapped_column(
        String(64), nullable=False, doc="e.g. analyst_upgrade, zacks_rank_1"
    )
    value: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 8), nullable=True, doc="Nullable for categorical flags"
    )
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
