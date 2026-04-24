from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models import Base

# Import enums from their proper locations to avoid DRY violations


# =============================================================================
# PORTFOLIO-SPECIFIC MODELS
# =============================================================================

# Account model removed - replaced by broker-agnostic BrokerAccount model


class PortfolioHistory(Base):
    """Daily portfolio value snapshots for drawdown tracking."""

    __tablename__ = "portfolio_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("broker_accounts.id"), nullable=True, index=True
    )
    as_of_date: Mapped[date] = mapped_column(Date, index=True)

    # Value metrics
    total_value: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    cash_value: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    positions_value: Mapped[Decimal] = mapped_column(Numeric(18, 2))

    # Drawdown metrics (computed)
    peak_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    drawdown_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    drawdown_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "account_id",
            "as_of_date",
            name="uix_portfolio_history_user_account_date",
        ),
    )


class Category(Base):
    """Custom categorization system for positions."""

    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    color = Column(String(10))  # Hex color code
    parent_category_id = Column(Integer, ForeignKey("categories.id"))

    # Category type
    category_type = Column(String(50), default="custom")  # custom, sector, strategy, etc.

    # Target allocation (percentage)
    target_allocation_pct = Column(Float)
    min_allocation_pct = Column(Float)
    max_allocation_pct = Column(Float)

    # Rebalancing settings
    rebalance_threshold_pct = Column(Float, default=5.0)  # Trigger rebalancing at 5% deviation
    auto_rebalance = Column(Boolean, default=False)

    display_order = Column(Integer, default=0, server_default="0")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    parent_category = relationship("Category", remote_side=[id])
    position_assignments = relationship("PositionCategory", back_populates="category")

    __table_args__ = (
        UniqueConstraint("user_id", "name", "category_type", name="uq_category_user_name_type"),
    )


class PositionCategory(Base):
    """Many-to-many relationship between positions and categories."""

    __tablename__ = "position_categories"

    id = Column(Integer, primary_key=True)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    allocation_pct = Column(
        Float, default=100.0
    )  # Percentage of position assigned to this category
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    position = relationship("Position")
    category = relationship("Category", back_populates="position_assignments")

    # Unique constraint
    __table_args__ = (Index("idx_position_category", "position_id", "category_id", unique=True),)


class PortfolioSnapshot(Base):
    """Daily portfolio snapshots for historical analysis."""

    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("broker_accounts.id"), nullable=False)
    snapshot_date = Column(DateTime, nullable=False)

    # Portfolio metrics
    total_value = Column(Float, nullable=False)
    total_cash = Column(Float, nullable=False)
    total_equity_value = Column(Float, nullable=False)
    unrealized_pnl = Column(Float, nullable=False)
    realized_pnl = Column(Float, nullable=True)  # Made nullable - not always available immediately
    day_pnl = Column(Float, nullable=True)  # Made nullable - not always available immediately
    day_pnl_pct = Column(Float, nullable=True)  # Made nullable - not always available immediately

    # Risk metrics
    beta = Column(Float)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)
    volatility = Column(Float)

    # Margin information
    buying_power = Column(Float)
    margin_used = Column(Float)
    margin_available = Column(Float)

    # Snapshot data (JSON)
    positions_snapshot = Column(Text)  # JSON of positions at this time
    sector_allocation = Column(Text)  # JSON of sector breakdown

    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    broker_account = relationship("BrokerAccount")

    # Indexes
    __table_args__ = (
        Index("idx_account_date", "account_id", "snapshot_date"),
        Index("idx_snapshot_date", "snapshot_date"),
    )
