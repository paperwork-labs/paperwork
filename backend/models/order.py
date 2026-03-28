"""
Order Model for Trade Execution
===============================

Persistent order records for buy/sell execution flows and preview/whatIf responses.
"""

import enum
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    JSON,
    Index,
    ForeignKey,
)
from sqlalchemy.sql import func

from . import Base


class OrderSide(enum.Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(enum.Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(enum.Enum):
    PREVIEW = "preview"
    PENDING_APPROVAL = "pending_approval"
    PENDING_SUBMIT = "pending_submit"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    ERROR = "error"


class OrderSource(enum.Enum):
    MANUAL = "manual"
    STRATEGY = "strategy"
    REBALANCE = "rebalance"


class BrokerType(enum.Enum):
    IBKR = "ibkr"
    ALPACA = "alpaca"
    TASTYTRADE = "tastytrade"
    SCHWAB = "schwab"


class Order(Base):
    """Order model for trade execution and preview/whatIf responses."""

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)
    order_type = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="preview", index=True)
    quantity = Column(Float, nullable=False)
    limit_price = Column(Float, nullable=True)
    stop_price = Column(Float, nullable=True)
    filled_quantity = Column(Float, default=0)
    filled_avg_price = Column(Float, nullable=True)
    account_id = Column(String(100), nullable=True)
    broker_order_id = Column(String(100), nullable=True, index=True)

    # Lineage: which strategy / signal / position triggered this order
    strategy_id = Column(Integer, ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True, index=True)
    signal_id = Column(Integer, ForeignKey("signals.id", ondelete="SET NULL"), nullable=True, index=True)
    position_id = Column(Integer, ForeignKey("positions.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    source = Column(String(20), nullable=False, default="manual")
    broker_type = Column(String(20), nullable=False, default="ibkr")

    # whatIfOrder preview fields
    estimated_commission = Column(Float, nullable=True)
    estimated_margin_impact = Column(Float, nullable=True)
    estimated_equity_with_loan = Column(Float, nullable=True)
    preview_data = Column(JSON, nullable=True)

    # Execution quality analytics
    decision_price = Column(Float, nullable=True)  # Price when order was created/signaled
    slippage_pct = Column(Float, nullable=True)  # (fill_price - decision_price) / decision_price * 100
    slippage_dollars = Column(Float, nullable=True)  # Total slippage in dollars
    fill_latency_ms = Column(Integer, nullable=True)  # Time from submit to fill in milliseconds
    vwap_at_fill = Column(Float, nullable=True)  # VWAP at fill time for comparison
    spread_at_order = Column(Float, nullable=True)  # Bid-ask spread when order placed

    error_message = Column(String(500), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    filled_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_by = Column(String(200), nullable=True)

    __table_args__ = (
        Index("idx_orders_symbol_status", "symbol", "status"),
        Index("idx_orders_status_created_at", "status", "created_at"),
        Index("idx_orders_strategy_id", "strategy_id"),
        Index("idx_orders_user_id", "user_id"),
    )
