#!/usr/bin/env python3
"""
Enhanced Account Balance Model
Maps to brokerage account information sections from any data source.
Completely broker-agnostic - supports all brokerages (IBKR, TastyTrade, etc.)
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Enum,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from backend.models import Base


class AccountBalanceType(enum.Enum):
    """Types of account balance snapshots."""

    REALTIME = "REALTIME"  # Real-time API data
    DAILY_SNAPSHOT = "DAILY_SNAPSHOT"  # Daily account snapshot
    MONTHLY_STATEMENT = "MONTHLY_STATEMENT"  # Monthly statement data
    QUARTERLY_REPORT = "QUARTERLY_REPORT"  # Quarterly report


class AccountBalance(Base):
    """
    Enhanced Account Balance and Margin Information from any brokerage.

    Comprehensive account balance tracking including:
    - Cash balances and available funds
    - Margin requirements and usage
    - Portfolio values and equity
    - Buying power calculations
    - Multi-currency support

    Generic Account Information Fields (adaptable to any brokerage):
    - accountId, acctAlias, accountType, customerType
    - accountNumber, baseCurrency, accountCode
    - totalCashValue, settledCash, availableFunds, netLiquidation
    - buyingPower, grossPositionValue, marginReq, initMarginReq
    - maintenanceMarginReq, availableFundsC, availableFundsS
    - buyingPowerC, buyingPowerS, leverageS, lookAheadNextChange
    - cushion, lookAheadAvailableFunds, lookAheadExcessLiquidity
    - lookAheadInitMarginReq, lookAheadMaintMarginReq
    - pnl, unrealizedPnl, realizedPnl, exchangeRate
    - equity, previousDayEquity, initMarginReq, maintenanceMarginReq
    - totalCashBalance, settledCash, cashBalance, marginBalance
    - sma, regTEquity, accruedCash, accruedDividend
    """

    __tablename__ = "account_balances"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    broker_account_id = Column(
        Integer, ForeignKey("broker_accounts.id"), nullable=False
    )

    # Core balance info
    balance_date = Column(DateTime, nullable=False, default=func.now())
    balance_type = Column(
        Enum(AccountBalanceType),
        nullable=False,
        default=AccountBalanceType.DAILY_SNAPSHOT,
    )
    base_currency = Column(String(10), nullable=False, default="USD")

    # Cash Balances
    total_cash_value = Column(Float, nullable=True)  # Total cash across all currencies
    settled_cash = Column(Float, nullable=True)  # Settled cash available
    available_funds = Column(Float, nullable=True)  # Available funds for trading
    cash_balance = Column(Float, nullable=True)  # Current cash balance

    # Portfolio Values
    net_liquidation = Column(Float, nullable=True)  # Total account value
    gross_position_value = Column(Float, nullable=True)  # Total position value
    equity = Column(Float, nullable=True)  # Account equity
    previous_day_equity = Column(Float, nullable=True)  # Previous day equity

    # Margin Information
    buying_power = Column(Float, nullable=True)  # Available buying power
    initial_margin_req = Column(Float, nullable=True)  # Initial margin requirement
    maintenance_margin_req = Column(
        Float, nullable=True
    )  # Maintenance margin requirement
    reg_t_equity = Column(Float, nullable=True)  # Regulation T equity
    sma = Column(Float, nullable=True)  # Special Memorandum Account

    # P&L Information
    unrealized_pnl = Column(Float, nullable=True)  # Unrealized P&L
    realized_pnl = Column(Float, nullable=True)  # Realized P&L
    daily_pnl = Column(Float, nullable=True)  # Daily P&L

    # Advanced Margin (for sophisticated brokerages)
    cushion = Column(Float, nullable=True)  # Margin cushion percentage
    leverage = Column(Float, nullable=True)  # Account leverage ratio
    lookahead_next_change = Column(Float, nullable=True)  # Next margin change
    lookahead_available_funds = Column(Float, nullable=True)  # Future available funds
    lookahead_excess_liquidity = Column(Float, nullable=True)  # Future excess liquidity
    lookahead_init_margin = Column(Float, nullable=True)  # Future initial margin
    lookahead_maint_margin = Column(Float, nullable=True)  # Future maintenance margin

    # Dividend & Interest Accruals
    accrued_cash = Column(Float, nullable=True)  # Accrued cash
    accrued_dividend = Column(Float, nullable=True)  # Accrued dividends
    accrued_interest = Column(Float, nullable=True)  # Accrued interest

    # Multi-Currency Support
    exchange_rate = Column(Float, nullable=True)  # Exchange rate to base currency

    # Data Source & Metadata
    data_source = Column(String(20), nullable=False, default="API_SNAPSHOT")
    account_alias = Column(String(100), nullable=True)  # Account nickname/alias
    customer_type = Column(String(50), nullable=True)  # Customer classification
    account_code = Column(String(50), nullable=True)  # Brokerage-specific code

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="account_balances")
    broker_account = relationship("BrokerAccount", back_populates="account_balances")

    def __repr__(self):
        """String representation for debugging purposes."""
        equity_str = f"{self.equity:.2f}" if self.equity is not None else "0.00"
        return (
            f"<AccountBalance(account={self.broker_account_id}, equity=${equity_str}, "
            f"date={self.balance_date})>"
        )

    @property
    def margin_utilization_pct(self) -> float:
        """Calculate margin utilization percentage."""
        if (
            self.net_liquidation
            and self.initial_margin_req
            and self.net_liquidation > 0
        ):
            return (self.initial_margin_req / self.net_liquidation) * 100
        return 0.0

    @property
    def cash_percentage(self) -> float:
        """Calculate cash as percentage of total equity."""
        if self.net_liquidation and self.cash_balance and self.net_liquidation > 0:
            return (self.cash_balance / self.net_liquidation) * 100
        return 0.0

    @property
    def available_buying_power_ratio(self) -> float:
        """Calculate available buying power as ratio of equity."""
        if self.equity and self.buying_power and self.equity > 0:
            return self.buying_power / self.equity
        return 0.0
