from sqlalchemy import (
    JSON,
    Boolean,
    Column,
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
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from . import Base


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("broker_accounts.id"), nullable=False)
    # position_id = Column(Integer, ForeignKey("positions.id"))  # TODO: Add when Position model is created

    # Trade details
    symbol = Column(
        String(50), nullable=False, index=True
    )  # Increased from 20 to 50 for option symbols
    side = Column(String(10), nullable=False)  # BUY, SELL
    quantity = Column(Numeric(15, 4), nullable=False)
    price = Column(Numeric(10, 4), nullable=False)
    total_value = Column(Numeric(15, 2))
    commission = Column(Numeric(10, 2), default=0)
    fees = Column(Numeric(10, 2), default=0)

    # Order details
    order_type = Column(String(20), default="MARKET")  # MARKET, LIMIT, STOP, etc.
    time_in_force = Column(String(10), default="DAY")  # DAY, GTC, IOC, FOK
    order_id = Column(String(50))  # Broker order ID
    execution_id = Column(String(50))  # Broker execution ID

    # Timestamps
    order_time = Column(DateTime(timezone=True))
    execution_time = Column(DateTime(timezone=True))
    settlement_date = Column(DateTime(timezone=True))

    # Strategy information
    strategy_name = Column(String(50))
    signal_id = Column(Integer, ForeignKey("trade_signals.id"))
    entry_signal = Column(String(50))  # ATR_ENTRY, BREAKOUT, etc.
    exit_signal = Column(String(50))  # ATR_TARGET, STOP_LOSS, etc.

    # Risk management
    risk_amount = Column(Numeric(10, 2))
    position_size_pct = Column(Float)
    atr_at_entry = Column(Float)
    stop_loss_price = Column(Numeric(10, 4))
    target_price = Column(Numeric(10, 4))

    # P&L tracking
    realized_pnl = Column(Numeric(15, 2))
    pnl_pct = Column(Float)

    # Status and flags
    status = Column(String(20), default="FILLED")  # PENDING, FILLED, CANCELLED, REJECTED
    is_opening = Column(Boolean, default=True)  # True for opening, False for closing
    is_paper_trade = Column(Boolean, default=True)

    # Additional data
    notes = Column(Text)
    trade_metadata = Column(JSON)  # Store additional trade-specific data

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    broker_account = relationship("BrokerAccount")
    signal = relationship("TradeSignal", back_populates="trades")
    # Note: position relationship will be added when Position model supports trades

    __table_args__ = (
        UniqueConstraint("account_id", "execution_id", name="uq_trades_account_execution"),
        Index("idx_trades_account_symbol_time", "account_id", "symbol", "execution_time"),
    )


class TradeSignal(Base):
    __tablename__ = "trade_signals"

    id = Column(Integer, primary_key=True, index=True)

    # Signal details
    symbol = Column(String(20), nullable=False, index=True)
    signal_type = Column(String(50), nullable=False)  # ENTRY, EXIT, SCALE_OUT
    strategy_name = Column(String(50), nullable=False)
    signal_strength = Column(Float)  # 0.0 to 1.0

    # Price and timing
    trigger_price = Column(Numeric(10, 4))
    recommended_price = Column(Numeric(10, 4))
    stop_loss = Column(Numeric(10, 4))
    target_price = Column(Numeric(10, 4))

    # ATR Matrix specific
    atr_distance = Column(Float)
    atr_value = Column(Float)
    ma_alignment = Column(Boolean)
    price_position_20d = Column(Float)
    risk_reward_ratio = Column(Float)

    # Technical conditions at signal
    rsi = Column(Float)
    macd = Column(Float)
    adx = Column(Float)
    volume_ratio = Column(Float)

    # Signal validity
    is_valid = Column(Boolean, default=True)
    expires_at = Column(DateTime(timezone=True))

    # Processing status
    is_processed = Column(Boolean, default=False)
    is_executed = Column(Boolean, default=False)
    execution_price = Column(Numeric(10, 4))

    # Additional data
    conditions_met = Column(JSON)  # Store all conditions that triggered signal
    market_conditions = Column(JSON)  # Store market context
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    trades = relationship("Trade", back_populates="signal")
