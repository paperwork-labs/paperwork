#!/usr/bin/env python3
"""
Generic Transfer Model for Multi-Brokerage Support
Maps to brokerage transfer sections from any data source.
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
    Enum,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from backend.models import Base


class TransferType(enum.Enum):
    """Types of transfers supported by brokerages."""

    CASH = "CASH"  # Cash transfer
    POSITION = "POSITION"  # Position/stock transfer
    ACATS = "ACATS"  # Automated Customer Account Transfer Service
    DIVIDEND = "DIVIDEND"  # Dividend payment
    INTEREST = "INTEREST"  # Interest payment
    FEE = "FEE"  # Fee payment
    CORPORATE_ACTION = "CORPORATE_ACTION"  # Corporate action
    OPTION_EXERCISE = "OPTION_EXERCISE"  # Option exercise
    OPTION_ASSIGNMENT = "OPTION_ASSIGNMENT"  # Option assignment
    SPLIT = "SPLIT"  # Stock split
    MERGER = "MERGER"  # Merger/acquisition
    SPINOFF = "SPINOFF"  # Spinoff
    OTHER = "OTHER"  # Other transfer type


class Transfer(Base):
    """
    Generic Position and Cash Transfers from any brokerage.

    Comprehensive transfer tracking including:
    - Cash movements and deposits/withdrawals
    - Position transfers between accounts
    - Corporate actions and dividend payments
    - Option exercises and assignments
    - Multi-currency support

    Generic Transfer Fields (adaptable to any brokerage):
    - accountId, acctAlias, model, currency, fxRateToBase
    - symbol, description, conid, securityID, securityIDType
    - quantity, tradePrice, amount, cashAmount, netCash
    - tradeDate, settleDate, transferPrice, deliveryType
    - direction, type, code, clientReference, transactionID
    """

    __tablename__ = "transfers"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    broker_account_id = Column(
        Integer, ForeignKey("broker_accounts.id"), nullable=False
    )

    # Transfer Identity
    transaction_id = Column(String(100), nullable=True, unique=True, index=True)
    client_reference = Column(String(100), nullable=True)

    # Core Transfer Information
    transfer_date = Column(Date, nullable=False, index=True)
    settle_date = Column(Date, nullable=True)
    transfer_type = Column(Enum(TransferType), nullable=False)
    direction = Column(String(10), nullable=True)  # IN/OUT

    # Asset Information
    symbol = Column(String(50), nullable=True, index=True)
    description = Column(String(200), nullable=True)
    contract_id = Column(String(50), nullable=True, index=True)  # Generic contract ID
    security_id = Column(String(50), nullable=True)
    security_id_type = Column(String(20), nullable=True)  # CUSIP, ISIN, etc.

    # Quantity and Pricing
    quantity = Column(Float, nullable=True)
    trade_price = Column(Float, nullable=True)
    transfer_price = Column(Float, nullable=True)

    # Financial Information
    amount = Column(Float, nullable=True)  # Transfer amount
    cash_amount = Column(Float, nullable=True)  # Cash component
    net_cash = Column(Float, nullable=True)  # Net cash impact
    commission = Column(Float, nullable=True)  # Commission/fees

    # Currency Information
    currency = Column(String(10), nullable=False, default="USD")
    fx_rate_to_base = Column(Float, nullable=True)

    # Transfer Details
    delivery_type = Column(String(50), nullable=True)  # Delivery method
    transfer_type_code = Column(String(20), nullable=True)  # Brokerage specific code

    # Account Information
    account_alias = Column(String(100), nullable=True)
    model = Column(String(50), nullable=True)  # Account model/type

    # Additional Details
    notes = Column(String(500), nullable=True)  # Transfer notes
    external_reference = Column(String(100), nullable=True)  # External system reference

    # Data Source & Metadata
    data_source = Column(String(20), nullable=False, default="BROKERAGE_API")

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="transfers")
    broker_account = relationship("BrokerAccount", back_populates="transfers")
    # Note: Instrument relationship removed - contract_id is brokerage-specific and Instrument model uses different PK

    def __repr__(self):
        return f"<Transfer({self.transfer_type.value}: {self.symbol or 'CASH'} {self.amount} on {self.transfer_date})>"

    @property
    def is_cash_transfer(self) -> bool:
        """Check if this is a cash-only transfer."""
        return self.transfer_type == TransferType.CASH or not self.symbol

    @property
    def is_position_transfer(self) -> bool:
        """Check if this involves position movement."""
        return self.transfer_type == TransferType.POSITION and self.symbol is not None

    @property
    def is_corporate_action(self) -> bool:
        """Check if this is a corporate action."""
        return self.transfer_type in [
            TransferType.CORPORATE_ACTION,
            TransferType.DIVIDEND,
            TransferType.SPLIT,
            TransferType.MERGER,
            TransferType.SPINOFF,
        ]

    @property
    def net_impact(self) -> float:
        """Calculate net financial impact."""
        return self.net_cash or self.cash_amount or self.amount or 0.0
