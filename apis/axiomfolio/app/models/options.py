#!/usr/bin/env python3
"""
Generic Options Model for Multi-Brokerage Support
Core options data models supporting all brokerages: IBKR, TastyTrade, Schwab, etc.
"""

import enum

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models import Base


class OptionType(enum.Enum):
    """Option contract types."""

    CALL = "CALL"
    PUT = "PUT"


class Option(Base):
    """
    Option contract/position tracking from any brokerage data source.

    Maps to options exercise/assignment data from all brokerages.
    Completely generic - supports IBKR, TastyTrade, Schwab, etc.

    Generic Options Fields (adaptable to any brokerage):
    - symbol, underlyingSymbol, strike, expiry, putCall, multiplier
    - exercisedQuantity, assignedQuantity, quantity, position
    - markPrice, underlyingPrice, unrealizedPnl, realizedPnl
    - exerciseDate, exercisePrice, assignmentDate, commissions
    - currency, fxRateToBase, accountId, conid
    """

    __tablename__ = "options"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Account Information
    account_id = Column(Integer, ForeignKey("broker_accounts.id"), nullable=False, index=True)
    account_alias = Column(String(100), nullable=True)

    # Options Contract Details (Generic brokerage fields)
    symbol = Column(String(50), nullable=False, index=True)  # Full option symbol
    underlying_symbol = Column(String(50), nullable=True)  # Underlying stock symbol
    contract_id = Column(String(50), nullable=True, index=True)  # Brokerage contract ID
    strike_price = Column(Float, nullable=False)  # Strike price
    expiry_date = Column(Date, nullable=False)  # Expiration date
    option_type = Column(String(10), nullable=False)  # PUT/CALL
    multiplier = Column(Float, nullable=False, default=100)  # Contract multiplier

    # Position Information
    exercised_quantity = Column(Integer, nullable=True)  # Exercised quantity
    assigned_quantity = Column(Integer, nullable=True)  # Assigned quantity
    open_quantity = Column(Integer, nullable=False, default=0)  # Current open position

    # Pricing Information
    current_price = Column(Numeric(12, 4), nullable=True)  # Current option price
    underlying_price = Column(Numeric(12, 4), nullable=True)  # Current underlying price

    # Greeks (snapshot at last sync)
    delta = Column(Numeric(10, 6), nullable=True)
    gamma = Column(Numeric(10, 6), nullable=True)
    theta = Column(Numeric(10, 6), nullable=True)
    vega = Column(Numeric(10, 6), nullable=True)
    implied_volatility = Column(Numeric(10, 4), nullable=True)

    # Exercise/Assignment Details
    exercise_date = Column(Date, nullable=True)  # Exercise date
    exercise_price = Column(Float, nullable=True)  # Exercise price
    assignment_date = Column(Date, nullable=True)  # Assignment date

    # Financial Details
    currency = Column(String(10), nullable=False, default="USD")  # Currency
    fx_rate_to_base = Column(Float, nullable=True)  # FX rate to base currency

    # P&L Information
    unrealized_pnl = Column(Numeric(12, 2), nullable=True)  # Unrealized P&L
    realized_pnl = Column(Numeric(12, 2), nullable=True)  # Realized P&L
    total_cost = Column(Numeric(12, 2), nullable=True)  # Total cost basis
    commission = Column(Numeric(12, 2), nullable=True)  # Commissions paid

    # Data Source & Metadata
    data_source = Column(String(20), nullable=False, default="BROKERAGE_API")

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_updated = Column(DateTime, default=func.now())

    # Relationships
    user = relationship("User", back_populates="options")
    broker_account = relationship("BrokerAccount", back_populates="options")

    # Dedupe safety: one row per account + contract tuple
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "underlying_symbol",
            "strike_price",
            "expiry_date",
            "option_type",
            name="uq_options_contract_per_account",
        ),
        Index(
            "idx_options_contract",
            "underlying_symbol",
            "strike_price",
            "expiry_date",
            "option_type",
        ),
    )

    def __repr__(self):
        return f"<Option({self.underlying_symbol} {self.option_type} ${self.strike_price} {self.expiry_date})>"

    @property
    def days_to_expiry(self) -> int:
        """Calculate days until expiration."""
        if self.expiry_date:
            from datetime import date

            return (self.expiry_date - date.today()).days
        return 0

    @property
    def is_expired(self) -> bool:
        """Check if option has expired."""
        return self.days_to_expiry <= 0

    @property
    def intrinsic_value(self) -> float:
        """Calculate intrinsic value."""
        if not self.underlying_price or not self.strike_price:
            return 0.0

        if self.option_type == "CALL":
            return max(0, float(self.underlying_price) - self.strike_price)
        else:  # PUT
            return max(0, self.strike_price - float(self.underlying_price))

    @property
    def time_value(self) -> float:
        """Calculate time value (extrinsic value)."""
        if not self.current_price:
            return 0.0
        return max(0, float(self.current_price) - self.intrinsic_value)

    @property
    def notional_value(self) -> float:
        """Calculate notional value of the position."""
        if self.current_price and self.open_quantity:
            return float(self.current_price) * self.open_quantity * self.multiplier
        return 0.0


# Note: class renamed from OptionPosition → Option and table from option_positions → options
