"""
Financial Instruments 
===================================

Master data for all tradeable instruments (stocks, options, futures, etc.).
Provides symbol mapping and instrument metadata.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    DECIMAL,
    Enum as SQLEnum,
    Index,
    JSON,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from . import Base

# =============================================================================
# ENUMS
# =============================================================================


class InstrumentType(enum.Enum):
    STOCK = "stock"  # Common stock
    ETF = "etf"  # Exchange-traded fund
    OPTION = "option"  # Options contract
    FUTURE = "future"  # Futures contract
    BOND = "bond"  # Bond
    FOREX = "forex"  # Foreign exchange
    CRYPTO = "crypto"  # Cryptocurrency
    INDEX = "index"  # Market index
    MUTUAL_FUND = "mutual_fund"  # Mutual fund


class Exchange(enum.Enum):
    NYSE = "nyse"  # New York Stock Exchange
    NASDAQ = "nasdaq"  # NASDAQ
    AMEX = "amex"  # American Stock Exchange
    CBOE = "cboe"  # Chicago Board Options Exchange
    CME = "cme"  # Chicago Mercantile Exchange
    ICE = "ice"  # Intercontinental Exchange
    OTC = "otc"  # Over-the-counter


class OptionStyle(enum.Enum):
    AMERICAN = "american"  # Can exercise anytime
    EUROPEAN = "european"  # Can only exercise at expiration


# =============================================================================
# INSTRUMENT MODELS
# =============================================================================


class Instrument(Base):
    """
    Master instrument definition.
    Central repository for all tradeable securities.
    """

    __tablename__ = "instruments"

    # Primary identification
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(100), unique=True, nullable=False, index=True)

    # Basic information
    name = Column(String(200))  # Company/fund name
    instrument_type = Column(SQLEnum(InstrumentType), nullable=False, index=True)
    exchange = Column(SQLEnum(Exchange), index=True)
    currency = Column(String(3), default="USD")

    # Trading information
    is_tradeable = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    tick_size = Column(DECIMAL(10, 6))  # Minimum price increment
    lot_size = Column(Integer, default=1)  # Minimum trading quantity

    # Market data
    sector = Column(String(50))  # Market sector
    industry = Column(String(100))  # Industry classification
    market_cap = Column(DECIMAL(20, 2))  # Market capitalization

    # Options-specific fields
    underlying_symbol = Column(String(20))  # For options/futures
    option_type = Column(String(4))  # "CALL", "PUT"
    strike_price = Column(DECIMAL(15, 4))  # Strike price
    expiration_date = Column(DateTime)  # Expiration date
    option_style = Column(SQLEnum(OptionStyle))  # American/European
    multiplier = Column(Integer, default=1)  # Contract multiplier

    # Corporate information
    cusip = Column(String(9))  # CUSIP identifier
    isin = Column(String(12))  # ISIN identifier
    figi = Column(String(12))  # Bloomberg FIGI

    # Metadata
    description = Column(Text)  # Full description
    additional_data = Column(JSON)  # Flexible additional data

    # Data source tracking
    data_source = Column(String(50))  # Where data came from
    last_updated = Column(DateTime)  # When data was last updated

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    positions = relationship("Position", back_populates="instrument")
    price_data = relationship("PriceData", back_populates="instrument")

    # Indexes
    __table_args__ = (
        Index("idx_instruments_type", "instrument_type"),
        Index("idx_instruments_underlying", "underlying_symbol"),
        Index("idx_instruments_expiration", "expiration_date"),
        Index("idx_instruments_sector", "sector"),
    )

    @property
    def is_option(self) -> bool:
        """Check if this is an options instrument."""
        return self.instrument_type == InstrumentType.OPTION

    @property
    def is_equity(self) -> bool:
        """Check if this is an equity instrument."""
        return self.instrument_type in [InstrumentType.STOCK, InstrumentType.ETF]

    @property
    def display_name(self) -> str:
        """Human-readable display name."""
        if self.name:
            return f"{self.symbol} - {self.name}"
        return self.symbol

    @property
    def option_display_symbol(self) -> str:
        """Options-formatted symbol."""
        if not self.is_option:
            return self.symbol

        exp_str = (
            self.expiration_date.strftime("%y%m%d") if self.expiration_date else "XX"
        )
        strike_str = f"{self.strike_price:.0f}" if self.strike_price else "0"
        return f"{self.underlying_symbol}_{exp_str}_{self.option_type[0]}{strike_str}"


class InstrumentAlias(Base):
    """
    Alternative symbols/identifiers for instruments.
    Handles broker-specific symbol variations.
    """

    __tablename__ = "instrument_aliases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instrument_id = Column(
        Integer, ForeignKey("instruments.id"), nullable=False, index=True
    )

    # Alias information
    alias_symbol = Column(String(50), nullable=False, index=True)
    alias_type = Column(String(20), nullable=False)  # "broker", "bloomberg", "reuters"
    source = Column(String(50))  # Which broker/system uses this alias

    # Metadata
    is_primary = Column(Boolean, default=False)  # Primary symbol for this source
    notes = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    instrument = relationship("Instrument")

    # Indexes
    __table_args__ = (
        Index("idx_aliases_symbol", "alias_symbol"),
        Index("idx_aliases_source", "source"),
    )
