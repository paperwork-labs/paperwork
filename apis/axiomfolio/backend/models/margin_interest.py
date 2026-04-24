#!/usr/bin/env python3
"""
Generic Margin Interest Model for Multi-Brokerage Support
Maps to brokerage interest accrual sections from any data source.
Supports all brokerages: IBKR, TastyTrade, Schwab, etc.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Date,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.models import Base


class MarginInterest(Base):
    """
    Generic Margin Interest tracking from any brokerage interest accruals section.

    Comprehensive interest tracking including:
    - Margin interest charges and credits
    - Cash interest earnings
    - Interest rate changes over time
    - Multi-currency interest calculations

    Generic Interest Accrual Fields (adaptable to any brokerage):
    - accountId, acctAlias, fromDate, toDate
    - startingBalance, interestAccrued, accrualReversal, endingBalance
    - interestRate, currency, fxRateToBase
    """

    __tablename__ = "margin_interest"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    broker_account_id = Column(
        Integer, ForeignKey("broker_accounts.id"), nullable=False
    )

    # Account Information
    account_alias = Column(String(100), nullable=True)  # Account nickname/alias

    # Interest Period
    from_date = Column(Date, nullable=False, index=True)  # Interest period start
    to_date = Column(Date, nullable=False, index=True)  # Interest period end

    # Interest Calculations
    starting_balance = Column(Float, nullable=True)  # Starting balance for period
    interest_accrued = Column(Float, nullable=False)  # Interest accrued in period
    accrual_reversal = Column(Float, nullable=True)  # Any accrual reversals
    ending_balance = Column(Float, nullable=True)  # Ending balance for period

    # Interest Rate Information
    interest_rate = Column(Float, nullable=True)  # Interest rate (annual rate)
    daily_rate = Column(Float, nullable=True)  # Daily interest rate

    # Currency Information
    currency = Column(String(10), nullable=False, default="USD")  # Currency
    fx_rate_to_base = Column(Float, nullable=True)  # FX rate to base currency

    # Interest Type Classification
    interest_type = Column(String(50), nullable=True)  # MARGIN_DEBIT, CASH_CREDIT, etc.
    description = Column(String(200), nullable=True)  # Interest description

    # Data Source & Metadata
    data_source = Column(String(20), nullable=False, default="BROKERAGE_API")

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="margin_interest")
    broker_account = relationship("BrokerAccount", back_populates="margin_interest")

    def __repr__(self):
        return f"<MarginInterest(account={self.broker_account_id}, period={self.from_date} to {self.to_date}, interest=${self.interest_accrued:.2f})>"

    @property
    def period_days(self) -> int:
        """Calculate number of days in the interest period."""
        if self.from_date and self.to_date:
            return (self.to_date - self.from_date).days
        return 0

    @property
    def daily_interest(self) -> float:
        """Calculate average daily interest for the period."""
        if self.period_days > 0:
            return self.interest_accrued / self.period_days
        return 0.0

    @property
    def effective_annual_rate(self) -> float:
        """Calculate effective annual interest rate based on balance."""
        if (
            self.starting_balance
            and self.starting_balance != 0
            and self.period_days > 0
        ):
            daily_rate = (
                self.interest_accrued / self.starting_balance / self.period_days
            )
            return (1 + daily_rate) ** 365 - 1
        return 0.0

    @property
    def is_margin_charge(self) -> bool:
        """Check if this is a margin interest charge (positive interest)."""
        return self.interest_accrued > 0

    @property
    def is_cash_credit(self) -> bool:
        """Check if this is a cash interest credit (negative interest)."""
        return self.interest_accrued < 0
