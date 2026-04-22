"""
Account Management
================================

Broker account tracking and integration.
Handles broker account tracking; examples in docs use placeholders, not real IDs.
"""

from sqlalchemy import (
    JSON,
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    Text,
    ForeignKey,
    DECIMAL,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

from . import Base

# =============================================================================
# ENUMS
# =============================================================================


class BrokerType(enum.Enum):
    IBKR = "ibkr"
    TASTYTRADE = "tastytrade"
    SCHWAB = "schwab"
    FIDELITY = "fidelity"
    ROBINHOOD = "robinhood"
    # E*TRADE is OAuth 1.0a in sandbox. ``etrade`` / ``ETRADE`` in Postgres
    # ``brokertype`` — see migration 0060.
    ETRADE = "etrade"
    # Live Tradier: OAuth slug ``tradier``; ``brokertype`` value (migration 0061).
    TRADIER = "tradier"
    # Sandbox Tradier: OAuth slug ``tradier_sandbox``; must align with
    # ``BrokerOAuthConnection.broker`` so sync picks the matching token
    # (``TRADIER_SANDBOX`` in ``brokertype`` from migration 0062).
    TRADIER_SANDBOX = "tradier_sandbox"
    # Allow tests to persist unknown brokers without schema errors
    UNKNOWN_BROKER = "unknown_broker"


class AccountType(enum.Enum):
    TAXABLE = "taxable"  # Regular brokerage account
    IRA = "ira"  # Traditional IRA
    ROTH_IRA = "roth_ira"  # Roth IRA
    HSA = "hsa"  # Health Savings Account
    TRUST = "trust"  # Trust account
    BUSINESS = "business"  # Business account


class AccountStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    CLOSED = "closed"
    SUSPENDED = "suspended"


class SyncStatus(enum.Enum):
    NEVER_SYNCED = "never_synced"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    ERROR = "error"


# =============================================================================
# ACCOUNT MODELS
# =============================================================================


class BrokerAccount(Base):
    """
    Broker account information and sync status.
    Links user to their actual broker accounts.
    """

    __tablename__ = "broker_accounts"

    # Primary identification
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Broker details
    broker = Column(SQLEnum(BrokerType), nullable=False, index=True)
    account_number = Column(String(50), nullable=False, index=True)  # e.g., "U19491234"
    account_name = Column(String(100))  # Human-readable name
    account_type = Column(SQLEnum(AccountType), nullable=False)
    auto_discovered = Column(Boolean, nullable=False, default=False)

    # Status
    status = Column(
        SQLEnum(AccountStatus), default=AccountStatus.ACTIVE, nullable=False
    )
    is_primary = Column(Boolean, default=False)  # Primary account for this broker
    is_enabled = Column(Boolean, default=True)  # Enabled for sync/trading

    # Connection details
    api_credentials_stored = Column(Boolean, default=False)
    last_connection_test = Column(DateTime)
    connection_status = Column(String(50))  # "connected", "failed", "untested"

    # Sync information
    sync_status = Column(SQLEnum(SyncStatus), default=SyncStatus.NEVER_SYNCED)
    last_sync_attempt = Column(DateTime)
    last_successful_sync = Column(DateTime)
    next_sync_scheduled = Column(DateTime)
    sync_error_message = Column(Text)

    # Account metadata
    currency = Column(String(3), default="USD")  # Base currency
    margin_enabled = Column(Boolean, default=False)
    options_enabled = Column(Boolean, default=False)
    futures_enabled = Column(Boolean, default=False)

    # Financial summary (cached from last sync)
    total_value = Column(DECIMAL(15, 2))  # Total account value
    cash_balance = Column(DECIMAL(15, 2))  # Available cash
    buying_power = Column(DECIMAL(15, 2))  # Available buying power
    day_pnl = Column(DECIMAL(15, 2))  # Today's P&L
    total_pnl = Column(DECIMAL(15, 2))  # Total unrealized P&L

    # Data retention settings
    import_transactions_since = Column(
        DateTime
    )  # Only import transactions after this date
    keep_historical_data_days = Column(Integer, default=365 * 3)  # 3 years default

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship(
        "User", back_populates="broker_accounts"
    )  # Fixed to match User.broker_accounts
    credentials = relationship(
        "AccountCredentials",
        back_populates="account",
        uselist=False,
        cascade="all, delete-orphan",
    )
    syncs = relationship(
        "AccountSync", back_populates="account", cascade="all, delete-orphan"
    )
    positions = relationship(
        "Position", back_populates="account", cascade="all, delete-orphan"
    )
    transactions = relationship(
        "Transaction", back_populates="broker_account", cascade="all, delete-orphan"
    )
    tax_lots = relationship(
        "TaxLot",
        foreign_keys="TaxLot.account_id",
        primaryjoin="BrokerAccount.id == TaxLot.account_id",
    )

    # NEW: FlexQuery Enhanced Relationships
    margin_interest = relationship(
        "MarginInterest", back_populates="broker_account", cascade="all, delete-orphan"
    )
    transfers = relationship(
        "Transfer", back_populates="broker_account", cascade="all, delete-orphan"
    )
    account_balances = relationship(
        "AccountBalance", back_populates="broker_account", cascade="all, delete-orphan"
    )
    options = relationship(
        "Option", back_populates="broker_account", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("idx_accounts_user_broker", "user_id", "broker"),
        Index("idx_accounts_number", "account_number"),
        Index("idx_accounts_sync_status", "sync_status"),
    )

    @property
    def display_name(self) -> str:
        """Human-friendly account display name."""
        if self.account_name:
            return f"{self.account_name} ({self.account_number})"
        return f"{self.broker.value.upper()} {self.account_type.value.title()} ({self.account_number})"

    @property
    def is_tax_advantaged(self) -> bool:
        """Check if this is a tax-advantaged account."""
        return self.account_type in [
            AccountType.IRA,
            AccountType.ROTH_IRA,
            AccountType.HSA,
        ]

    @property
    def tax_treatment(self) -> str:
        """Get tax treatment for tax lot calculations."""
        if self.account_type == AccountType.TAXABLE:
            return "taxable"
        elif self.account_type in [AccountType.IRA, AccountType.HSA]:
            return "tax_deferred"
        elif self.account_type == AccountType.ROTH_IRA:
            return "tax_free"
        return "unknown"

    def can_sync(self) -> bool:
        """Check if account is eligible for sync."""
        return (
            self.status == AccountStatus.ACTIVE
            and self.is_enabled
            and self.sync_status != SyncStatus.RUNNING
        )

    def update_sync_status(self, status: SyncStatus, error_message: str = None):
        """Update sync status with timestamps."""
        self.sync_status = status
        self.last_sync_attempt = datetime.now()

        if status == SyncStatus.SUCCESS:
            self.last_successful_sync = datetime.now()
            self.sync_error_message = None
        elif error_message:
            self.sync_error_message = error_message


class AccountCredentials(Base):
    """
    Encrypted broker credentials for API access.
    Stored separately for security.
    """

    __tablename__ = "account_credentials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(
        Integer, ForeignKey("broker_accounts.id"), nullable=False, unique=True
    )

    # Encrypted credentials (implementation specific)
    encrypted_credentials = Column(Text)  # JSON blob with broker-specific fields
    credential_hash = Column(String(255))  # For validation
    # Provider and metadata (non-secret)
    provider = Column(SQLEnum(BrokerType), nullable=True)
    credential_type = Column(
        String(32), nullable=True
    )  # oauth|basic|api_key|ibkr_flex|tws
    username_hint = Column(String(255))  # masked username/email if applicable
    last_refreshed_at = Column(DateTime)
    refresh_token_expires_at = Column(DateTime)
    last_error = Column(Text)
    rotation_count = Column(Integer)

    # Metadata
    last_updated = Column(DateTime, default=func.now())
    expires_at = Column(DateTime)  # For tokens that expire

    # Relationships
    account = relationship("BrokerAccount")


class AccountSync(Base):
    """
    Sync history and statistics for accounts.
    """

    __tablename__ = "account_syncs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(
        Integer, ForeignKey("broker_accounts.id"), nullable=False, index=True
    )

    # Sync details
    sync_type = Column(
        String(50), nullable=False
    )  # "full", "incremental", "positions_only"
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime)
    duration_seconds = Column(Integer)

    # Results
    status = Column(SQLEnum(SyncStatus), nullable=False)
    error_message = Column(Text)

    # Data counts
    positions_synced = Column(Integer, default=0)
    transactions_synced = Column(Integer, default=0)
    new_tax_lots_created = Column(Integer, default=0)

    # Sync metadata
    data_range_start = Column(DateTime)  # Date range synced
    data_range_end = Column(DateTime)
    sync_trigger = Column(String(50))  # "manual", "scheduled", "api_call"

    # G22 — Sync completeness validation (no-silent-success).
    # See backend/services/portfolio/ibkr/sync_validator.CompletenessReport.
    # Server-side defaults match an empty/clean report so legacy rows from
    # before migration 0053 stay valid.
    warnings = Column(JSON, nullable=False, server_default="[]")
    expected_sections = Column(JSON, nullable=False, server_default="[]")
    received_sections = Column(JSON, nullable=False, server_default="[]")
    missing_sections = Column(JSON, nullable=False, server_default="[]")
    section_row_counts = Column(JSON, nullable=False, server_default="{}")

    # Relationships
    account = relationship("BrokerAccount")

    # Indexes
    __table_args__ = (Index("idx_syncs_account_date", "account_id", "started_at"),)
