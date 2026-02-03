"""
Market Data Models (Core)
=========================

Minimal, production-focused models for price history and indicator snapshots.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Boolean,
    JSON,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from sqlalchemy import Text

from . import Base


class PriceData(Base):
    """Historical and real-time price data (daily/intraday slices)."""

    __tablename__ = "price_data"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), index=True, nullable=False)
    instrument_id = Column(
        Integer, ForeignKey("instruments.id"), nullable=True, index=True
    )
    date = Column(DateTime, index=True, nullable=False)

    # OHLCV data
    open_price = Column(Float)
    high_price = Column(Float)
    low_price = Column(Float)
    close_price = Column(Float, nullable=False)
    adjusted_close = Column(Float)
    volume = Column(Integer)

    # Calculated fields
    true_range = Column(Float)

    # Data quality and source
    data_source = Column(String(50))
    interval = Column(String(10))  # '1d', '1h', '5m'
    is_adjusted = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    instrument = relationship("Instrument", back_populates="price_data")

    __table_args__ = (
        UniqueConstraint("symbol", "date", "interval", name="uq_symbol_date_interval"),
        Index("idx_symbol_date", "symbol", "date"),
        Index("idx_date_range", "date"),
        Index("idx_symbol_interval_date", "symbol", "interval", "date"),
    )


class MarketSnapshot(Base):
    """Cache for computed indicators/analysis to support scanners and alerts.

    Table name: market_snapshot
    """

    __tablename__ = "market_snapshot"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(10), nullable=False, index=True)
    # Display name (e.g., company name)
    name = Column(String(200))
    analysis_type = Column(
        String(50), nullable=False
    )  # 'technical_snapshot', 'atr_matrix', etc.
    analysis_timestamp = Column(DateTime(timezone=True), server_default=func.now())
    # The market data "as-of" timestamp this snapshot was computed from (latest 1d bar).
    # This is the correct dimension for snapshot coverage by date (not analysis_timestamp).
    as_of_timestamp = Column(DateTime(timezone=True), nullable=True)
    expiry_timestamp = Column(DateTime(timezone=True), nullable=False)

    # Minimal technical snapshot
    current_price = Column(Float)
    market_cap = Column(Float)
    sector = Column(String(100))
    industry = Column(String(100))
    sub_industry = Column(String(100))

    # Core indicators we commonly query
    atr_value = Column(Float)
    atr_percent = Column(Float)
    atr_distance = Column(Float)
    rsi = Column(Float)
    # Canonical consolidated MAs / ATRs
    sma_5 = Column(Float)
    sma_10 = Column(Float)
    sma_14 = Column(Float)
    sma_21 = Column(Float)
    sma_50 = Column(Float)
    sma_100 = Column(Float)
    sma_150 = Column(Float)
    sma_200 = Column(Float)
    ema_10 = Column(Float)
    macd = Column(Float)
    macd_signal = Column(Float)

    # Canonical consolidated ATR windows
    atr_14 = Column(Float)
    atr_30 = Column(Float)
    atrp_14 = Column(Float)  # ATR/Price (%) for atr_14
    atrp_30 = Column(Float)  # ATR/Price (%) for atr_30

    # Price position in trading ranges (0..100)
    range_pos_20d = Column(Float)
    range_pos_50d = Column(Float)
    range_pos_52w = Column(Float)

    # ATR-multiple distances to key MAs (positive = above MA)
    atrx_sma_21 = Column(Float)
    atrx_sma_50 = Column(Float)
    atrx_sma_100 = Column(Float)
    atrx_sma_150 = Column(Float)

    # Relative strength vs benchmark (Mansfield RS %, vs SPY)
    rs_mansfield_pct = Column(Float)

    # Performance windows
    perf_1d = Column(Float)
    perf_3d = Column(Float)
    perf_5d = Column(Float)
    perf_20d = Column(Float)
    perf_60d = Column(Float)
    perf_120d = Column(Float)
    perf_252d = Column(Float)
    perf_mtd = Column(Float)
    perf_qtd = Column(Float)
    perf_ytd = Column(Float)

    # Pine Script metrics (from TradingView indicator)
    # EMA distances (percent) and ATR distances (in ATR multiples)
    ema_8 = Column(Float)
    ema_21 = Column(Float)
    ema_200 = Column(Float)
    pct_dist_ema8 = Column(Float)
    pct_dist_ema21 = Column(Float)
    pct_dist_ema200 = Column(Float)
    atr_dist_ema8 = Column(Float)
    atr_dist_ema21 = Column(Float)
    atr_dist_ema200 = Column(Float)

    # MA bucket (leading/lagging/neutral)
    ma_bucket = Column(String(16))

    # TD Sequential
    td_buy_setup = Column(Integer)
    td_sell_setup = Column(Integer)
    td_buy_complete = Column(Boolean)
    td_sell_complete = Column(Boolean)
    td_buy_countdown = Column(Integer)
    td_sell_countdown = Column(Integer)
    td_perfect_buy = Column(Boolean)
    td_perfect_sell = Column(Boolean)

    # Gaps (counts)
    gaps_unfilled_up = Column(Integer)
    gaps_unfilled_down = Column(Integer)

    # Trend lines
    trend_up_count = Column(Integer)
    trend_down_count = Column(Integer)

    # Stage analysis (Weinstein)
    stage_label = Column(String(10))  # e.g., '1', '2A', '2B', '2C', '3', '4'
    stage_label_5d_ago = Column(String(10))
    stage_slope_pct = Column(Float)
    stage_dist_pct = Column(Float)

    # Corporate events
    next_earnings = Column(DateTime)
    last_earnings = Column(DateTime)

    # Fundamentals (best-effort)
    pe_ttm = Column(Float)
    peg_ttm = Column(Float)
    roe = Column(Float)
    eps_growth_yoy = Column(Float)
    eps_growth_qoq = Column(Float)
    revenue_growth_yoy = Column(Float)
    revenue_growth_qoq = Column(Float)
    dividend_yield = Column(Float)
    beta = Column(Float)
    analyst_rating = Column(String(50))

    # Raw snapshot for extensibility
    raw_analysis = Column(JSON)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    is_valid = Column(Boolean, default=True)

    __table_args__ = (
        Index("idx_symbol_analysis_type", "symbol", "analysis_type"),
        Index("idx_symbol_expiry", "symbol", "expiry_timestamp"),
        Index("idx_analysis_timestamp", "analysis_timestamp"),
    )


class MarketSnapshotHistory(Base):
    """Immutable daily snapshots for strategy backtests and analytics.

    Table name: market_snapshot_history
    """

    __tablename__ = "market_snapshot_history"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(10), nullable=False, index=True)
    analysis_type = Column(String(50), nullable=False)
    as_of_date = Column(DateTime, nullable=False, index=True)
    analysis_timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # A few indexed headline fields for quick filters; details in payload
    current_price = Column(Float)
    rsi = Column(Float)
    atr_value = Column(Float)
    sma_50 = Column(Float)
    macd = Column(Float)
    macd_signal = Column(Float)

    # Wide snapshot fields (flat, queryable history table).
    name = Column(String(200))
    market_cap = Column(Float)
    sector = Column(String(100))
    industry = Column(String(100))
    sub_industry = Column(String(100))

    sma_5 = Column(Float)
    sma_10 = Column(Float)
    sma_14 = Column(Float)
    sma_21 = Column(Float)
    sma_100 = Column(Float)
    sma_150 = Column(Float)
    sma_200 = Column(Float)
    ema_10 = Column(Float)
    ema_8 = Column(Float)
    ema_21 = Column(Float)
    ema_200 = Column(Float)

    atr_14 = Column(Float)
    atr_30 = Column(Float)
    atrp_14 = Column(Float)
    atrp_30 = Column(Float)
    atr_distance = Column(Float)
    atr_percent = Column(Float)

    range_pos_20d = Column(Float)
    range_pos_50d = Column(Float)
    range_pos_52w = Column(Float)
    atrx_sma_21 = Column(Float)
    atrx_sma_50 = Column(Float)
    atrx_sma_100 = Column(Float)
    atrx_sma_150 = Column(Float)

    rs_mansfield_pct = Column(Float)
    stage_label = Column(String(10))
    stage_label_5d_ago = Column(String(10))
    last_earnings = Column(DateTime)
    next_earnings = Column(DateTime)
    pe_ttm = Column(Float)
    peg_ttm = Column(Float)
    roe = Column(Float)
    eps_growth_yoy = Column(Float)
    eps_growth_qoq = Column(Float)
    revenue_growth_yoy = Column(Float)
    revenue_growth_qoq = Column(Float)
    dividend_yield = Column(Float)
    beta = Column(Float)
    analyst_rating = Column(String(50))
    stage_slope_pct = Column(Float)
    stage_dist_pct = Column(Float)

    perf_1d = Column(Float)
    perf_3d = Column(Float)
    perf_5d = Column(Float)
    perf_20d = Column(Float)
    perf_60d = Column(Float)
    perf_120d = Column(Float)
    perf_252d = Column(Float)
    perf_mtd = Column(Float)
    perf_qtd = Column(Float)
    perf_ytd = Column(Float)

    pct_dist_ema8 = Column(Float)
    pct_dist_ema21 = Column(Float)
    pct_dist_ema200 = Column(Float)
    atr_dist_ema8 = Column(Float)
    atr_dist_ema21 = Column(Float)
    atr_dist_ema200 = Column(Float)
    ma_bucket = Column(String(16))

    td_buy_setup = Column(Integer)
    td_sell_setup = Column(Integer)
    td_buy_complete = Column(Boolean)
    td_sell_complete = Column(Boolean)
    td_buy_countdown = Column(Integer)
    td_sell_countdown = Column(Integer)
    td_perfect_buy = Column(Boolean)
    td_perfect_sell = Column(Boolean)
    gaps_unfilled_up = Column(Integer)
    gaps_unfilled_down = Column(Integer)
    trend_up_count = Column(Integer)
    trend_down_count = Column(Integer)

    next_earnings = Column(DateTime)

    __table_args__ = (
        UniqueConstraint(
            "symbol", "analysis_type", "as_of_date", name="uq_symbol_type_asof"
        ),
        Index("idx_hist_symbol_date", "symbol", "as_of_date"),
    )


class JobRun(Base):
    """Persistent job run registry for task observability and auditing.

    Table name: job_run
    """

    __tablename__ = "job_run"

    id = Column(Integer, primary_key=True, index=True)
    task_name = Column(String(100), nullable=False, index=True)
    params = Column(JSON)  # parameters provided to the task
    status = Column(String(20), nullable=False, index=True)  # running|ok|error|cancelled
    counters = Column(JSON)  # arbitrary counters (e.g., processed, errors)
    error = Column(Text)  # error message/traceback if any
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_jobrun_task_time", "task_name", "started_at"),
        Index("idx_jobrun_status_time", "status", "started_at"),
    )

