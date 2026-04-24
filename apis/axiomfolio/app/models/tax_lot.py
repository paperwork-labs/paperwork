#!/usr/bin/env python3
"""
Generic Tax Lot Model for Multi-Brokerage Support
Supports all brokerages: IBKR, TastyTrade, Schwab, etc.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    event,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text

from app.models import Base


class TaxLotMethod(enum.Enum):
    """Tax lot accounting methods supported by brokerages"""

    FIFO = "fifo"  # First In, First Out (most common)
    LIFO = "lifo"  # Last In, First Out
    AVERAGE_COST = "average_cost"  # Average cost method
    SPECIFIC_ID = "specific_id"  # Specific identification
    # Advanced tax optimization methods
    MAXIMIZE_LONG_TERM_GAIN = "mltg"  # Tax optimizer: maximize long-term gains
    MAXIMIZE_LONG_TERM_LOSS = "mltl"  # Tax optimizer: maximize long-term losses
    MAXIMIZE_SHORT_TERM_GAIN = "mstg"  # Tax optimizer: maximize short-term gains
    MAXIMIZE_SHORT_TERM_LOSS = "mstl"  # Tax optimizer: maximize short-term losses


class TaxLotSource(enum.Enum):
    """Data sources for tax lot information"""

    OFFICIAL_STATEMENT = "official_statement"  # Official brokerage statement (preferred)
    REALTIME_API = "realtime_api"  # Real-time API data
    MANUAL_ENTRY = "manual_entry"  # Manual user entry
    CALCULATED = "calculated"  # Calculated from trades
    # Read-only aggregator (e.g. Plaid Investments). Aggregators typically
    # return holdings/quantities/institution_value but NOT per-lot cost
    # basis, so tax_lots with source=AGGREGATOR have ``cost_per_share`` and
    # ``cost_basis`` set to NULL and must NEVER render as "$0.00" in UI
    # (see ``.cursor/rules/no-silent-fallback.mdc``).
    AGGREGATOR = "aggregator"


class TaxLot(Base):
    """
    Tax lot model aligned with multi-brokerage official data structure.
    Stores both official brokerage tax lots and real-time position data.

    Completely generic - works with any brokerage data source.
    """

    __tablename__ = "tax_lots"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    account_id = Column(
        Integer, ForeignKey("broker_accounts.id"), nullable=False, index=True
    )  # Broker account foreign key

    symbol = Column(String(64), nullable=False, index=True)  # Stock/Option symbol
    contract_id = Column(String(50), nullable=True)  # Brokerage contract ID (if available)

    # Tax lot details from brokerage statements
    quantity = Column(Float, nullable=False)  # Number of shares/contracts
    cost_per_share = Column(Float, nullable=True)  # Cost basis per share
    cost_basis = Column(Float, nullable=True)  # Total cost basis
    acquisition_date = Column(Date, nullable=True, index=True)  # When purchased

    # Trade Details (for lot reconstruction)
    trade_id = Column(String(50), nullable=True, index=True)  # Trade identifier
    execution_id = Column(String(50), nullable=True)  # Execution identifier
    order_id = Column(String(50), nullable=True)  # Order identifier
    exchange = Column(String(20), nullable=True)  # Exchange name
    asset_category = Column(String(20), nullable=True)  # Asset type (STK, OPT, etc.)

    # Current valuation
    current_price = Column(Float, nullable=True)  # Current market price
    market_value = Column(Float, nullable=True)  # Current market value
    unrealized_pnl = Column(Float, nullable=True)  # Unrealized P&L
    unrealized_pnl_pct = Column(Float, nullable=True)  # Unrealized P&L percentage

    # Currency & Fees
    currency = Column(String(10), nullable=False, default="USD")  # Currency
    commission = Column(Float, nullable=True)  # Commission paid
    fees = Column(Float, nullable=True)  # Other fees
    fx_rate = Column(Float, nullable=True)  # FX rate to base currency

    # Tax lot identification
    lot_id = Column(String(100), nullable=True, unique=True)  # Unique lot identifier

    # Brokerage metadata
    settlement_date = Column(Date, nullable=True)  # Settlement date
    holding_period = Column(Integer, nullable=True)  # Days held

    source = Column(SQLEnum(TaxLotSource), nullable=False, default=TaxLotSource.OFFICIAL_STATEMENT)

    execution_id = Column(String(50), nullable=True)  # Brokerage execution ID

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_price_update = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="tax_lots")

    def __repr__(self):
        cps = self.cost_per_share if self.cost_per_share is not None else 0
        return f"<TaxLot({self.symbol}: {self.quantity} @ ${cps:.2f})>"

    @property
    def is_official_brokerage_data(self) -> bool:
        """Check if this is official brokerage tax lot data."""
        return self.source == TaxLotSource.OFFICIAL_STATEMENT

    @property
    def holding_period_days(self) -> int:
        """Calculate holding period in days."""
        if self.acquisition_date:
            return (datetime.now().date() - self.acquisition_date).days
        return 0

    @property
    def is_long_term(self) -> bool:
        """Check if this is a long-term holding (>365 days)."""
        return self.holding_period_days > 365

    @property
    def gain_loss_available(self) -> bool:
        """True when gain/loss can be computed meaningfully.

        Aggregator-sourced lots (e.g. Plaid) do not expose per-lot cost
        basis, so ``cost_per_share`` may be ``None``. Callers must gate on
        this flag before displaying a numeric value — rendering ``$0.00``
        for "unknown" is a silent fallback bug (see
        ``.cursor/rules/no-silent-fallback.mdc``). The frontend should
        render ``—`` with an explanatory tooltip instead.
        """
        return (
            self.current_price is not None
            and self.cost_per_share is not None
            and self.quantity is not None
        )

    @property
    def gain_loss(self) -> float:
        """Realized gain/loss if sold at current price.

        Returns ``0.0`` when inputs are missing; callers MUST check
        :attr:`gain_loss_available` first to distinguish "break-even" from
        "unknown because the aggregator didn't report cost basis".
        """
        if not self.gain_loss_available:
            return 0.0
        return (self.current_price - self.cost_per_share) * self.quantity

    @property
    def gain_loss_pct(self) -> float:
        """Gain/loss percentage, or 0.0 when inputs are missing.

        See :attr:`gain_loss_available` for how to distinguish this from
        a true zero return.
        """
        if not self.gain_loss_available:
            return 0.0
        if self.cost_basis and self.cost_basis != 0:
            return (self.gain_loss / self.cost_basis) * 100
        return 0.0


# Auto-populate user_id from account linkage to satisfy tests that don't pass user_id
@event.listens_for(TaxLot, "before_insert")
def _taxlot_set_user_id_before_insert(mapper, connection, target: TaxLot):
    if target.user_id is None and target.account_id is not None:
        result = connection.execute(
            text("SELECT user_id FROM broker_accounts WHERE id = :id"),
            {"id": target.account_id},
        )
        row = result.first()
        if row and row[0] is not None:
            target.user_id = row[0]
