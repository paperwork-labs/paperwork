"""
Portfolio Positions
=================================

Current portfolio positions across all accounts and brokers.
Real-time position tracking with P&L calculations.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    DECIMAL,
    Enum as SQLEnum,
    Index,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy import event
from sqlalchemy.sql import text
from sqlalchemy.sql import func
from datetime import datetime
import enum
from decimal import Decimal

from . import Base

# =============================================================================
# ENUMS
# =============================================================================


class PositionType(enum.Enum):
    LONG = "long"  # Long equity position
    SHORT = "short"  # Short equity position
    OPTION_LONG = "option_long"  # Long options
    OPTION_SHORT = "option_short"  # Short options
    FUTURE_LONG = "future_long"  # Long futures
    FUTURE_SHORT = "future_short"  # Short futures


class PositionStatus(enum.Enum):
    OPEN = "open"  # Active position
    CLOSED = "closed"  # Position closed out
    EXPIRED = "expired"  # Options/futures expired


class Sleeve(str, enum.Enum):
    """Management-style tag for a position.

    ``active``     — short-dated / swing / actively managed. Trade card uses
                     short-term exit ladders and regime gates.
    ``conviction`` — multi-year hold. Trade card uses peak signal + tax-aware
                     exit framing; health auditor is more tolerant of
                     drawdowns measured in months, not days.
    """

    ACTIVE = "active"
    CONVICTION = "conviction"


# =============================================================================
# POSITION MODELS
# =============================================================================


class Position(Base):
    """
    Current portfolio position in a security.
    Represents what you currently own/owe.
    """

    __tablename__ = "positions"

    # Primary identification
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    account_id = Column(
        Integer, ForeignKey("broker_accounts.id"), nullable=False, index=True
    )

    # Security identification
    symbol = Column(String(20), nullable=False, index=True)
    instrument_id = Column(
        Integer, ForeignKey("instruments.id"), nullable=True, index=True
    )  # Proper FK to instruments
    instrument_type = Column(String(20), default="STOCK")  # STOCK, OPTION, FUTURE, etc.

    # Position details
    position_type = Column(SQLEnum(PositionType), nullable=True)
    quantity = Column(DECIMAL(15, 6), nullable=False)  # Shares/contracts held
    status = Column(
        SQLEnum(PositionStatus), default=PositionStatus.OPEN, nullable=False
    )

    # Cost basis (aggregate from tax lots)
    average_cost = Column(DECIMAL(15, 4), nullable=True)  # Average cost per share
    total_cost_basis = Column(DECIMAL(15, 2), nullable=True)  # Total cost basis

    # Current market values
    current_price = Column(DECIMAL(15, 4))  # Latest market price
    market_value = Column(DECIMAL(15, 2))  # current_price * quantity

    # P&L calculations
    unrealized_pnl = Column(DECIMAL(15, 2))  # market_value - total_cost_basis
    unrealized_pnl_pct = Column(
        DECIMAL(8, 4)
    )  # unrealized_pnl / total_cost_basis * 100
    day_pnl = Column(DECIMAL(15, 2))  # Today's P&L change
    day_pnl_pct = Column(DECIMAL(8, 4))  # Today's % change

    # Note: Options-specific fields removed. Equity-only Position model.

    # Risk metrics
    position_size_pct = Column(DECIMAL(6, 3))  # % of portfolio
    sector = Column(String(50))  # Market sector
    currency = Column(String(3), default="USD")
    beta = Column(DECIMAL(6, 3))  # Beta vs market

    # Portfolio Management Features
    margin_priority = Column(
        Integer, default=5
    )  # Priority for margin calls (1 = sell first, 10 = sell last)
    custom_category = Column(String(100))  # Custom categorization
    notes = Column(Text)  # Position notes

    # Additional metadata
    industry = Column(String(100))  # Industry classification
    market_cap = Column(DECIMAL(20, 2))  # Market capitalization

    # Sleeve tag (see Sleeve enum). Nullable with default "active" so legacy
    # rows stay queryable without a one-shot backfill. Sleeve is set manually
    # by the user via PATCH /positions/{id}/sleeve; never flipped automatically.
    sleeve = Column(String(32), nullable=True, default=Sleeve.ACTIVE.value)

    # Last update info
    price_updated_at = Column(DateTime)  # When price was last updated
    position_updated_at = Column(DateTime)  # When position was last changed
    # Set when a long has covered at least 1R (unrealized P&L % >= initial_risk %); never auto-cleared
    runner_since = Column(DateTime, nullable=True)

    # Data source
    last_sync_id = Column(Integer, ForeignKey("account_syncs.id"))
    broker_position_id = Column(String(100))  # Broker's internal position ID
    
    # Strategy attribution (for positions opened by strategy signals)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True, index=True)
    entry_signal_id = Column(Integer, ForeignKey("signals.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="positions")
    account = relationship("BrokerAccount", back_populates="positions")
    instrument = relationship(
        "Instrument", back_populates="positions"
    )  # Fixed: proper FK relationship

    # Indexes for performance
    __table_args__ = (
        Index("idx_positions_user_account", "user_id", "account_id"),
        Index("idx_positions_symbol", "symbol"),
        Index("idx_positions_status", "status"),
        Index("idx_positions_type", "position_type"),
        Index("idx_positions_updated_at", "updated_at"),
        Index("idx_positions_user_sleeve", "user_id", "sleeve"),
    )

    @property
    def is_option(self) -> bool:
        """Equity-only model: always False."""
        return False

    @property
    def is_long(self) -> bool:
        """Check if this is a long position."""
        return self.position_type in [
            PositionType.LONG,
            PositionType.OPTION_LONG,
            PositionType.FUTURE_LONG,
        ]

    @property
    def is_short(self) -> bool:
        """Check if this is a short position."""
        return self.position_type in [
            PositionType.SHORT,
            PositionType.OPTION_SHORT,
            PositionType.FUTURE_SHORT,
        ]

    @property
    def display_symbol(self) -> str:
        """Human-readable symbol (equities)."""
        return self.symbol

    def update_market_data(self, price: float, day_change: float = None):
        """Update position with latest market data."""
        self.current_price = Decimal(str(price))
        self.market_value = self.quantity * self.current_price

        # Calculate unrealized P&L
        if self.is_long:
            self.unrealized_pnl = self.market_value - self.total_cost_basis
        else:  # Short position
            self.unrealized_pnl = self.total_cost_basis - self.market_value

        # Calculate percentage
        if self.total_cost_basis > 0:
            self.unrealized_pnl_pct = (
                self.unrealized_pnl / self.total_cost_basis
            ) * 100

        # Day P&L if provided
        if day_change is not None:
            self.day_pnl = self.quantity * Decimal(str(day_change))
            if self.market_value > 0:
                self.day_pnl_pct = (
                    self.day_pnl / (self.market_value - self.day_pnl)
                ) * 100

        self.price_updated_at = datetime.now()

    def calculate_position_size_pct(self, total_portfolio_value: float):
        """Calculate position size as percentage of total portfolio."""
        if total_portfolio_value > 0 and self.market_value:
            self.position_size_pct = (
                abs(float(self.market_value)) / total_portfolio_value
            ) * 100


class PositionHistory(Base):
    """
    Historical position snapshots for performance tracking.
    Captures position state at specific points in time.
    """

    __tablename__ = "position_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    position_id = Column(
        Integer, ForeignKey("positions.id"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Snapshot date
    snapshot_date = Column(DateTime, nullable=False, index=True)
    snapshot_type = Column(String(20), default="daily")  # daily, weekly, monthly

    # Position data at snapshot time
    quantity = Column(DECIMAL(15, 6), nullable=False)
    price = Column(DECIMAL(15, 4), nullable=False)
    market_value = Column(DECIMAL(15, 2), nullable=False)
    unrealized_pnl = Column(DECIMAL(15, 2))
    total_cost_basis = Column(DECIMAL(15, 2), nullable=False)

    # Performance metrics
    day_return = Column(DECIMAL(8, 4))  # 1-day return %
    week_return = Column(DECIMAL(8, 4))  # 1-week return %
    month_return = Column(DECIMAL(8, 4))  # 1-month return %
    inception_return = Column(DECIMAL(8, 4))  # Return since first purchase

    # Risk metrics
    volatility = Column(DECIMAL(8, 4))  # Historical volatility
    max_drawdown = Column(DECIMAL(8, 4))  # Maximum drawdown from peak

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    position = relationship("Position")
    user = relationship("User")

    # Indexes
    __table_args__ = (
        Index("idx_position_history_position_date", "position_id", "snapshot_date"),
        Index("idx_position_history_user_date", "user_id", "snapshot_date"),
    )


# Auto-populate user_id from account linkage to satisfy tests that don't pass user_id
@event.listens_for(Position, "before_insert")
def _position_set_user_id_before_insert(mapper, connection, target: Position):
    if target.user_id is None and target.account_id is not None:
        result = connection.execute(
            text("SELECT user_id FROM broker_accounts WHERE id = :id"),
            {"id": target.account_id},
        )
        row = result.first()
        if row and row[0] is not None:
            target.user_id = row[0]
