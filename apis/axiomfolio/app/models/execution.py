"""Execution analytics models."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from . import Base


class ExecutionMetrics(Base):
    """Track execution quality metrics per order."""

    __tablename__ = "execution_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # Order details
    symbol: Mapped[str] = mapped_column(String(20))
    broker: Mapped[str] = mapped_column(String(20))  # ibkr, schwab, tastytrade
    side: Mapped[str] = mapped_column(String(10))  # buy, sell

    # Pricing
    expected_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    fill_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    slippage_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    slippage_dollars: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)

    # Timing
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    time_to_fill_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Quality metrics
    fill_rate: Mapped[float | None] = mapped_column(Float, nullable=True)  # % of order filled
    partial_fills: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
