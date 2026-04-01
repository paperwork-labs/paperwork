"""
Market Data Models (Core)
=========================

Minimal, production-focused models for price history and indicator snapshots.
"""

from sqlalchemy import (
    BigInteger,
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
    volume = Column(BigInteger)

    # Calculated fields
    true_range = Column(Float)

    # Data quality and source
    data_source = Column(String(50))
    interval = Column(String(10))  # '1d', '1h', '5m'
    is_adjusted = Column(Boolean, default=True)
    is_synthetic_ohlc = Column(Boolean, default=False)
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
    symbol = Column(String(20), nullable=False, index=True)
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
    macd_histogram = Column(Float)
    adx = Column(Float)
    plus_di = Column(Float)
    minus_di = Column(Float)
    bollinger_upper = Column(Float)
    bollinger_lower = Column(Float)
    bollinger_width = Column(Float)
    keltner_upper = Column(Float)
    keltner_lower = Column(Float)
    ttm_squeeze_on = Column(Boolean)
    ttm_momentum = Column(Float)
    high_52w = Column(Float)
    low_52w = Column(Float)
    stoch_rsi = Column(Float)
    volume_avg_20d = Column(Float)

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

    # Stage analysis (Oliver Kell / Weinstein refined, SMA150 anchor)
    stage_label = Column(String(10))  # 1A, 1B, 2A, 2B, 2C, 3A, 3B, 4A, 4B, 4C
    stage_4h = Column(String(10), nullable=True)  # 4H timeframe stage (spec labels)
    stage_confirmed = Column(Boolean, nullable=True)  # True if daily and 4H agree
    stage_label_5d_ago = Column(String(10))
    current_stage_days = Column(Integer)
    previous_stage_label = Column(String(10))
    previous_stage_days = Column(Integer)
    stage_slope_pct = Column(Float)
    stage_dist_pct = Column(Float)

    # Stage Analysis fields
    ext_pct = Column(Float)  # (Close - SMA150) / SMA150 * 100
    sma150_slope = Column(Float)  # (SMA150_today - SMA150_20d_ago) / SMA150_20d_ago * 100
    sma50_slope = Column(Float)  # (SMA50_today - SMA50_10d_ago) / SMA50_10d_ago * 100
    ema10_dist_pct = Column(Float)  # (Close - EMA10) / EMA10 * 100
    ema10_dist_n = Column(Float)  # ema10_dist_pct / atrp_14 (ATR-normalized)
    vol_ratio = Column(Float)  # volume / volume_avg_20d
    scan_tier = Column(String(20))  # Breakout Elite/Standard, Early Base, Speculative, Breakdown Elite/Standard
    action_label = Column(String(10))  # BUY, HOLD, WATCH, REDUCE, SHORT, AVOID
    regime_state = Column(String(10))  # R1, R2, R3, R4, R5 (denormalized from MarketRegime)

    # Corporate events
    next_earnings = Column(DateTime)
    last_earnings = Column(DateTime)

    # Fundamentals (best-effort)
    pe_ttm = Column(Float)
    peg_ttm = Column(Float)
    roe = Column(Float)
    eps_ttm = Column(Float)
    revenue_ttm = Column(Float)
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
        Index(
            "idx_symbol_analysis_type_ts",
            "symbol",
            "analysis_type",
            "analysis_timestamp",
        ),
        Index("idx_symbol_expiry", "symbol", "expiry_timestamp"),
        Index("idx_analysis_timestamp", "analysis_timestamp"),
    )


class MarketSnapshotHistory(Base):
    """Immutable daily snapshots for strategy backtests and analytics.

    Table name: market_snapshot_history
    """

    __tablename__ = "market_snapshot_history"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
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
    macd_histogram = Column(Float)
    adx = Column(Float)
    plus_di = Column(Float)
    minus_di = Column(Float)
    bollinger_upper = Column(Float)
    bollinger_lower = Column(Float)
    bollinger_width = Column(Float)
    keltner_upper = Column(Float)
    keltner_lower = Column(Float)
    ttm_squeeze_on = Column(Boolean)
    ttm_momentum = Column(Float)
    high_52w = Column(Float)
    low_52w = Column(Float)
    stoch_rsi = Column(Float)
    volume_avg_20d = Column(Float)

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
    stage_label = Column(String(10))  # 1A, 1B, 2A, 2B, 2C, 3A, 3B, 4A, 4B, 4C
    stage_4h = Column(String(10), nullable=True)
    stage_confirmed = Column(Boolean, nullable=True)
    stage_label_5d_ago = Column(String(10))
    current_stage_days = Column(Integer)
    previous_stage_label = Column(String(10))
    previous_stage_days = Column(Integer)

    # Stage Analysis fields
    ext_pct = Column(Float)
    sma150_slope = Column(Float)
    sma50_slope = Column(Float)
    ema10_dist_pct = Column(Float)
    ema10_dist_n = Column(Float)
    vol_ratio = Column(Float)
    scan_tier = Column(String(20))
    action_label = Column(String(10))
    regime_state = Column(String(10))

    last_earnings = Column(DateTime)
    next_earnings = Column(DateTime)
    pe_ttm = Column(Float)
    peg_ttm = Column(Float)
    roe = Column(Float)
    eps_ttm = Column(Float)
    revenue_ttm = Column(Float)
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

    __table_args__ = (
        UniqueConstraint(
            "symbol", "analysis_type", "as_of_date", name="uq_symbol_type_asof"
        ),
        Index("idx_hist_symbol_date", "symbol", "as_of_date"),
    )


class MarketRegime(Base):
    """Daily market regime state computed from 6 macro inputs.

    The Regime Engine is the outermost gate — all downstream modules
    (stage classification, scan overlay, position sizing, exit cascade)
    inherit the current Regime state. See Stage_Analysis.docx Section 10.

    Table name: market_regime
    """

    __tablename__ = "market_regime"

    id = Column(Integer, primary_key=True, index=True)
    as_of_date = Column(DateTime, nullable=False, unique=True, index=True)

    # 6 daily inputs
    vix_spot = Column(Float)
    vix3m_vix_ratio = Column(Float)  # VIX3M / VIX
    vvix_vix_ratio = Column(Float)  # VVIX / VIX
    nh_nl = Column(Integer)  # New 52w highs minus new 52w lows (S&P 500)
    pct_above_200d = Column(Float)  # % of S&P 500 above 200D MA
    pct_above_50d = Column(Float)  # % of S&P 500 above 50D MA

    # Individual scores (1–5 each)
    score_vix = Column(Float)
    score_vix3m_vix = Column(Float)
    score_vvix_vix = Column(Float)
    score_nh_nl = Column(Float)
    score_above_200d = Column(Float)
    score_above_50d = Column(Float)

    # Composite and regime
    composite_score = Column(Float)  # Average of 6 scores, rounded to 0.5
    regime_state = Column(String(10), nullable=False)  # R1, R2, R3, R4, R5

    # Portfolio rules derived from regime
    cash_floor_pct = Column(Float)  # Minimum cash %
    max_equity_exposure_pct = Column(Float)  # Maximum equity %
    regime_multiplier = Column(Float)  # Position sizing multiplier

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_regime_date", "as_of_date"),
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
    result_meta = Column(JSON)  # structured result payload (e.g., intelligence briefs)
    error = Column(Text)  # error message/traceback if any
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_jobrun_task_time", "task_name", "started_at"),
        Index("idx_jobrun_status_time", "status", "started_at"),
    )


class CronSchedule(Base):
    """Persistent schedule definitions — single source of truth for cron jobs.

    UI CRUD operates on this table; a Render API sync layer mirrors
    enabled rows to Render cron-job services in production.
    """

    __tablename__ = "cron_schedule"

    id = Column(String(100), primary_key=True)
    display_name = Column(String(200), nullable=False)
    group = Column(String(50), nullable=False)
    task = Column(String(300), nullable=False)
    description = Column(Text)
    cron = Column(String(100), nullable=False)
    timezone = Column(String(50), default="UTC", nullable=False)
    args_json = Column(JSON, default=list)
    kwargs_json = Column(JSON, default=dict)
    enabled = Column(Boolean, default=True, nullable=False)

    timeout_s = Column(Integer, default=3600)
    singleflight = Column(Boolean, default=True)

    render_service_id = Column(String(100))
    render_synced_at = Column(DateTime(timezone=True))
    render_sync_error = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(String(200))


class CronScheduleAudit(Base):
    """Immutable audit trail for schedule mutations."""

    __tablename__ = "cron_schedule_audit"

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(String(100), nullable=False, index=True)
    action = Column(String(30), nullable=False)  # created | updated | paused | resumed | deleted
    actor = Column(String(200), nullable=False)
    changes = Column(JSON)  # {field: {old, new}} for updates; full snapshot for create/delete
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_audit_schedule_time", "schedule_id", "timestamp"),
    )

