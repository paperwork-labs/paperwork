"""
Transaction Data Models for Local Persistence
Enhanced for IBKR FlexQuery Cash Transactions section (45 fields)
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Text,
    ForeignKey,
    Index,
    Date,
    Enum,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
from backend.models import Base


class TransactionType(enum.Enum):
    """Enhanced transaction types from FlexQuery."""

    # Trading
    BUY = "BUY"
    SELL = "SELL"

    # Dividends & Distributions
    DIVIDEND = "DIVIDEND"
    PAYMENT_IN_LIEU = "PAYMENT_IN_LIEU"
    DISTRIBUTION = "DISTRIBUTION"

    # Interest & Fees
    BROKER_INTEREST_PAID = "BROKER_INTEREST_PAID"
    BROKER_INTEREST_RECEIVED = "BROKER_INTEREST_RECEIVED"
    COMMISSION = "COMMISSION"
    OTHER_FEE = "OTHER_FEE"

    # Deposits & Withdrawals
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"

    # Corporate Actions
    SPLIT = "SPLIT"
    SPIN_OFF = "SPIN_OFF"
    MERGER = "MERGER"

    # Tax
    WITHHOLDING_TAX = "WITHHOLDING_TAX"
    TAX_REFUND = "TAX_REFUND"

    # Other
    TRANSFER = "TRANSFER"
    OTHER = "OTHER"


class SyncDirection(enum.Enum):
    """Direction of transaction sync runs."""

    INCREMENTAL = "incremental"
    FULL = "full"


class Transaction(Base):
    """
    Enhanced Transaction model for IBKR FlexQuery Cash Transactions.

    Maps all 45 fields from FlexQuery Cash Transactions section:
    - Basic transaction info (symbol, type, amount, dates)
    - Settlement and clearing details
    - Tax and withholding information
    - Corporate action details
    - Multi-currency support
    - Trade reference information
    """

    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)

    # Account Information (FlexQuery: accountId, acctAlias)
    account_id = Column(
        Integer, ForeignKey("broker_accounts.id"), nullable=False, index=True
    )
    account_alias = Column(String(100), nullable=True)

    # Transaction Identification (FlexQuery: transactionID, tradeID, orderID, execID)
    external_id = Column(
        String(100), nullable=True, index=True
    )  # FlexQuery: transactionID
    trade_id = Column(String(50), nullable=True)  # FlexQuery: tradeID
    order_id = Column(String(50), nullable=True)  # FlexQuery: orderID
    execution_id = Column(String(50), nullable=True)  # FlexQuery: execID

    # Instrument Information (FlexQuery: symbol, description, conid, securityID, etc.)
    symbol = Column(String(50), nullable=False, index=True)  # FlexQuery: symbol
    description = Column(Text, nullable=True)  # FlexQuery: description
    conid = Column(
        String(50), nullable=True, index=True
    )  # FlexQuery: conid (IBKR contract ID)
    security_id = Column(String(50), nullable=True)  # FlexQuery: securityID
    cusip = Column(String(20), nullable=True)  # FlexQuery: cusip
    isin = Column(String(20), nullable=True)  # FlexQuery: isin
    listing_exchange = Column(String(20), nullable=True)  # FlexQuery: listingExchange

    # Options/Derivatives (FlexQuery: underlyingConid, underlyingSymbol, multiplier, strike, expiry, putCall)
    underlying_conid = Column(String(50), nullable=True)  # FlexQuery: underlyingConid
    underlying_symbol = Column(String(50), nullable=True)  # FlexQuery: underlyingSymbol
    multiplier = Column(Float, nullable=True)  # FlexQuery: multiplier
    strike_price = Column(Float, nullable=True)  # FlexQuery: strike
    expiry_date = Column(Date, nullable=True)  # FlexQuery: expiry
    option_type = Column(String(10), nullable=True)  # FlexQuery: putCall (PUT/CALL)

    # Transaction Details (FlexQuery: type, quantity, tradePrice, amount, etc.)
    transaction_type = Column(Enum(TransactionType), nullable=False)  # FlexQuery: type
    action = Column(String(10), nullable=True)  # FlexQuery: action (BOT/SLD)
    quantity = Column(Float, nullable=True)  # FlexQuery: quantity
    trade_price = Column(Float, nullable=True)  # FlexQuery: tradePrice
    amount = Column(Float, nullable=False)  # FlexQuery: amount
    proceeds = Column(Float, nullable=True)  # FlexQuery: proceeds

    # Costs and Fees (FlexQuery: commission, brokerageCommission, clearingCommission, etc.)
    commission = Column(Float, nullable=True)  # FlexQuery: commission
    brokerage_commission = Column(
        Float, nullable=True
    )  # FlexQuery: brokerageCommission
    clearing_commission = Column(Float, nullable=True)  # FlexQuery: clearingCommission
    third_party_commission = Column(
        Float, nullable=True
    )  # FlexQuery: thirdPartyCommission
    other_fees = Column(Float, nullable=True)  # FlexQuery: otherFees
    net_amount = Column(Float, nullable=False)  # FlexQuery: netCash

    # Currency and FX (FlexQuery: currency, fxRateToBase)
    currency = Column(String(10), nullable=False, default="USD")  # FlexQuery: currency
    fx_rate_to_base = Column(Float, nullable=True)  # FlexQuery: fxRateToBase

    # Classification (FlexQuery: assetCategory, subCategory)
    asset_category = Column(
        String(20), nullable=True
    )  # FlexQuery: assetCategory (STK, OPT, etc.)
    sub_category = Column(String(20), nullable=True)  # FlexQuery: subCategory

    # Dates (FlexQuery: dateTime, tradeDate, settleDateTarget, settleDate)
    transaction_date = Column(
        DateTime, nullable=False, index=True
    )  # FlexQuery: dateTime
    trade_date = Column(Date, nullable=True)  # FlexQuery: tradeDate
    settlement_date_target = Column(Date, nullable=True)  # FlexQuery: settleDateTarget
    settlement_date = Column(Date, nullable=True)  # FlexQuery: settleDate

    # Tax Information (FlexQuery: taxes, taxableAmount, taxableAmountInBase)
    taxes = Column(Float, nullable=True)  # FlexQuery: taxes
    taxable_amount = Column(Float, nullable=True)  # FlexQuery: taxableAmount
    taxable_amount_base = Column(Float, nullable=True)  # FlexQuery: taxableAmountInBase

    # Corporate Actions (FlexQuery: corporateActionFlag, corporateActionId)
    corporate_action_flag = Column(
        String(10), nullable=True
    )  # FlexQuery: corporateActionFlag
    corporate_action_id = Column(
        String(50), nullable=True
    )  # FlexQuery: corporateActionId

    # Data Source and Metadata
    source = Column(String(50), nullable=False, default="FLEXQUERY")
    synced_at = Column(DateTime, default=func.now(), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    broker_account = relationship("BrokerAccount", back_populates="transactions")

    # Indexes for fast queries
    __table_args__ = (
        # Dedupe safety: prefer external_id; fallback execution_id per account
        UniqueConstraint(
            "account_id", "external_id", name="uq_transactions_account_external_id"
        ),
        UniqueConstraint(
            "account_id", "execution_id", name="uq_transactions_account_execution_id"
        ),
        Index("idx_transactions_symbol", "symbol"),
        Index("idx_transaction_date", "transaction_date"),
        Index("idx_external_id", "external_id"),
        Index("idx_account_symbol_date", "account_id", "symbol", "transaction_date"),
    )


class Dividend(Base):
    """Local storage for dividend payment data."""

    __tablename__ = "dividends"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("broker_accounts.id"), nullable=False)

    # Dividend identification
    external_id = Column(String(100))  # IBKR dividend ID

    # Dividend details
    symbol = Column(String(20), nullable=False)
    ex_date = Column(DateTime, nullable=False)
    pay_date = Column(DateTime)
    dividend_per_share = Column(Float, nullable=False)
    shares_held = Column(Float, nullable=False)
    total_dividend = Column(Float, nullable=False)

    # Tax information
    tax_withheld = Column(Float, default=0)
    net_dividend = Column(Float, nullable=False)

    # Metadata
    currency = Column(String(10), default="USD")
    frequency = Column(String(20), default="quarterly")  # quarterly, monthly, annual
    dividend_type = Column(
        String(20), default="ordinary"
    )  # ordinary, special, return_of_capital

    # Data source tracking
    source = Column(String(50), default="ibkr")
    synced_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    broker_account = relationship("BrokerAccount")

    # Indexes for fast queries
    __table_args__ = (
        Index("idx_dividends_symbol", "symbol"),  # Made unique
        Index("idx_ex_date", "ex_date"),
        Index("idx_pay_date", "pay_date"),
        Index("idx_account_symbol_exdate", "account_id", "symbol", "ex_date"),
    )


class TransactionSyncStatus(Base):
    """Track sync status for transaction data."""

    __tablename__ = "transaction_sync_status"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("broker_accounts.id"), nullable=False)

    # Sync tracking
    last_sync_date = Column(DateTime)
    last_successful_sync = Column(DateTime)
    sync_status = Column(
        String(20), default="pending"
    )  # pending, in_progress, completed, failed

    # Data ranges
    earliest_transaction_date = Column(DateTime)
    latest_transaction_date = Column(DateTime)
    total_transactions = Column(Integer, default=0)
    total_dividends = Column(Integer, default=0)

    # Error tracking
    last_error = Column(Text)
    error_count = Column(Integer, default=0)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    broker_account = relationship("BrokerAccount")

    # Indexes
    __table_args__ = (
        Index("idx_account_status", "account_id", "sync_status"),
        Index("idx_last_sync", "last_sync_date"),
    )
