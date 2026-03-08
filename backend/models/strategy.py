"""
Strategy Execution Models
=======================================

Preserves existing sophisticated strategy execution capabilities while adding
multi-user support and enhanced performance tracking.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    Text,
    ForeignKey,
    UniqueConstraint,
    Index,
    CheckConstraint,
    TIMESTAMP,
    Enum as SQLEnum,
    JSON,
    DECIMAL,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from . import Base

# Import Signal so it is in the mapper registry when Strategy configures relationship("Signal", ...)
from backend.models.signals import Signal  # noqa: F401

# =============================================================================
# ENUMS
# =============================================================================


class StrategyType(enum.Enum):
    ATR_MATRIX = "atr_matrix"
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    OPTIONS_FLOW = "options_flow"
    EARNINGS_PLAY = "earnings_play"
    CUSTOM = "custom"


class StrategyStatus(enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    ARCHIVED = "archived"


class RunStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionMode(enum.Enum):
    PAPER = "paper"  # Paper trading
    LIVE = "live"  # Live trading
    BACKTEST = "backtest"  # Historical backtesting


# =============================================================================
# STRATEGY DEFINITIONS
# =============================================================================


class Strategy(Base):
    """Strategy definitions and configurations."""

    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Basic Information
    name = Column(String(100), nullable=False)
    description = Column(Text)
    strategy_type = Column(SQLEnum(StrategyType), nullable=False)

    # Execution Settings
    status = Column(SQLEnum(StrategyStatus), default=StrategyStatus.DRAFT)
    execution_mode = Column(SQLEnum(ExecutionMode), default=ExecutionMode.PAPER)
    auto_execute = Column(Boolean, default=False)

    # Universe & Filtering
    universe_filter = Column(JSON)  # Screening criteria
    min_market_cap = Column(DECIMAL(20, 2))
    max_market_cap = Column(DECIMAL(20, 2))
    allowed_sectors = Column(JSON)  # Array of sector names
    excluded_symbols = Column(JSON)  # Array of symbols to exclude

    # Position Management
    max_positions = Column(Integer, default=10)
    position_size_pct = Column(
        DECIMAL(5, 2), default=2.0
    )  # % of portfolio per position
    max_position_value = Column(DECIMAL(15, 2))  # Max $ value per position

    # Risk Management
    max_risk_per_trade = Column(DECIMAL(5, 2), default=2.0)  # % of portfolio
    max_portfolio_risk = Column(DECIMAL(5, 2), default=20.0)  # Total portfolio risk
    stop_loss_pct = Column(DECIMAL(5, 2), default=8.0)
    take_profit_pct = Column(DECIMAL(5, 2), default=20.0)
    max_holding_days = Column(Integer, default=30)

    # Strategy Parameters (JSON for flexibility)
    parameters = Column(JSON, nullable=False, default=lambda: {})

    # Performance Targets
    target_annual_return = Column(DECIMAL(6, 2), default=15.0)  # %
    max_drawdown_pct = Column(DECIMAL(5, 2), default=10.0)
    min_win_rate = Column(DECIMAL(5, 2), default=60.0)  # %
    min_risk_reward_ratio = Column(DECIMAL(4, 2), default=2.0)

    # Scheduling
    run_frequency = Column(
        String(50), default="daily"
    )  # daily, weekly, intraday, on_demand
    run_time = Column(String(10))  # HH:MM format
    timezone = Column(String(50), default="UTC")

    # Last Execution
    last_run_at = Column(TIMESTAMP(timezone=True))
    next_run_at = Column(TIMESTAMP(timezone=True))
    last_run_status = Column(SQLEnum(RunStatus))

    # Performance Summary (updated by background jobs)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    win_rate_pct = Column(DECIMAL(5, 2), default=0)
    total_return_pct = Column(DECIMAL(8, 4), default=0)
    max_drawdown_experienced = Column(DECIMAL(5, 2), default=0)
    sharpe_ratio = Column(DECIMAL(6, 4))

    # Configuration Validation
    is_validated = Column(Boolean, default=False)
    validation_errors = Column(JSON)
    validation_warnings = Column(JSON)

    # Audit
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Execution Audit Trail
    started_audit = Column(TIMESTAMP(timezone=True))  # When strategy execution started
    completed_audit = Column(
        TIMESTAMP(timezone=True)
    )  # When strategy execution completed
    last_health_check = Column(
        TIMESTAMP(timezone=True)
    )  # Last strategy health evaluation

    # User/System Tracking
    created_by_user_id = Column(Integer, ForeignKey("users.id"))  # Strategy creator
    modified_by_user_id = Column(Integer, ForeignKey("users.id"))  # Last modifier
    execution_node = Column(String(50))  # Which server runs this strategy

    # Audit Context
    audit_metadata = Column(JSON)  # Execution context, errors, performance
    version = Column(Integer, default=1)  # Strategy version for updates

    # Relationships - Fixed to specify exact foreign keys
    user = relationship("User", back_populates="strategies", foreign_keys=[user_id])
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    modified_by = relationship("User", foreign_keys=[modified_by_user_id])
    strategy_runs = relationship(
        "StrategyRun", back_populates="strategy", cascade="all, delete-orphan"
    )
    signals = relationship(
        "Signal", back_populates="strategy", cascade="all, delete-orphan"
    )
    executions = relationship(
        "StrategyExecution", back_populates="strategy", cascade="all, delete-orphan"
    )  # Fixed: Added missing relationship

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_strategy_name"),
        Index("idx_user_status", "user_id", "status"),
        Index("idx_strategy_type", "strategy_type"),
        Index("idx_next_run", "next_run_at", "status"),
        CheckConstraint(
            "position_size_pct > 0 AND position_size_pct <= 100",
            name="ck_position_size_valid",
        ),
        CheckConstraint("max_positions > 0", name="ck_max_positions_positive"),
    )


class StrategyRun(Base):
    """Results of strategy executions."""

    __tablename__ = "strategy_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False)

    # Execution Details
    run_date = Column(TIMESTAMP(timezone=True), nullable=False)
    status = Column(SQLEnum(RunStatus), nullable=False)
    execution_mode = Column(SQLEnum(ExecutionMode), nullable=False)

    # Scanning Results
    universe_size = Column(Integer, default=0)  # Number of stocks scanned
    candidates_found = Column(Integer, default=0)  # Stocks meeting criteria
    signals_generated = Column(Integer, default=0)  # Signals created
    positions_opened = Column(Integer, default=0)  # New positions
    positions_closed = Column(Integer, default=0)  # Closed positions

    # Performance Results
    total_pnl = Column(DECIMAL(15, 2), default=0)
    realized_pnl = Column(DECIMAL(15, 2), default=0)
    unrealized_pnl = Column(DECIMAL(15, 2), default=0)

    # Execution Metrics
    execution_time_ms = Column(Integer)
    data_quality_score = Column(DECIMAL(3, 2))
    api_calls_made = Column(Integer, default=0)
    api_errors = Column(Integer, default=0)

    # Market Context
    market_conditions = Column(JSON)  # VIX, market direction, etc.
    spy_price = Column(DECIMAL(10, 2))
    vix_level = Column(DECIMAL(6, 2))
    market_trend = Column(String(20))  # bullish, bearish, sideways

    # Results Summary
    top_opportunities = Column(JSON)  # Top signals/opportunities found
    risk_alerts = Column(JSON)  # Risk warnings generated
    execution_notes = Column(Text)  # Notes about execution

    # Error Handling
    errors_encountered = Column(JSON)
    warnings_generated = Column(JSON)
    error_message = Column(Text)

    # Audit
    started_at = Column(TIMESTAMP(timezone=True), nullable=False)
    completed_at = Column(TIMESTAMP(timezone=True))

    # Relationships
    strategy = relationship("Strategy", back_populates="strategy_runs")
    signals = relationship(
        "Signal", back_populates="strategy_run", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_strategy_run_date", "strategy_id", "run_date"),
        Index("idx_strategy_run_status_date", "status", "run_date"),  # Made unique
        Index("idx_execution_mode", "execution_mode"),
    )


# =============================================================================
# STRATEGY PERFORMANCE TRACKING
# =============================================================================


class StrategyPerformance(Base):
    """Detailed performance tracking for strategies."""

    __tablename__ = "strategy_performance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False)

    # Time Period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    period_type = Column(String(20), nullable=False)  # daily, weekly, monthly, yearly

    # Trading Statistics
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    avg_trade_duration_days = Column(DECIMAL(8, 2))

    # Return Metrics
    total_return = Column(DECIMAL(15, 2), default=0)
    total_return_pct = Column(DECIMAL(8, 4), default=0)
    annualized_return_pct = Column(DECIMAL(8, 4))
    excess_return_pct = Column(DECIMAL(8, 4))  # vs benchmark

    # Risk Metrics
    volatility_pct = Column(DECIMAL(8, 4))
    max_drawdown_pct = Column(DECIMAL(5, 2))
    sharpe_ratio = Column(DECIMAL(6, 4))
    sortino_ratio = Column(DECIMAL(6, 4))
    beta = Column(DECIMAL(6, 4))

    # Trade Analysis
    win_rate_pct = Column(DECIMAL(5, 2))
    avg_winning_trade_pct = Column(DECIMAL(8, 4))
    avg_losing_trade_pct = Column(DECIMAL(8, 4))
    largest_winner_pct = Column(DECIMAL(8, 4))
    largest_loser_pct = Column(DECIMAL(8, 4))
    profit_factor = Column(DECIMAL(6, 2))  # Gross profit / Gross loss

    # Position Metrics
    avg_position_size_pct = Column(DECIMAL(5, 2))
    max_positions_held = Column(Integer)
    avg_positions_held = Column(DECIMAL(5, 2))
    position_turnover_rate = Column(DECIMAL(6, 2))

    # Execution Quality
    avg_slippage_bps = Column(DECIMAL(6, 2))  # Basis points
    fill_rate_pct = Column(DECIMAL(5, 2))
    avg_time_to_fill_seconds = Column(DECIMAL(8, 2))

    # Benchmark Comparison
    benchmark_symbol = Column(String(10), default="SPY")
    benchmark_return_pct = Column(DECIMAL(8, 4))
    alpha = Column(DECIMAL(8, 4))
    tracking_error = Column(DECIMAL(8, 4))
    information_ratio = Column(DECIMAL(6, 4))

    # Audit
    calculated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "strategy_id", "period_start", "period_type", name="uq_strategy_period"
        ),
        Index("idx_strategy_period", "strategy_id", "period_type"),
        Index("idx_period_dates", "period_start", "period_end"),
    )


# =============================================================================
# BACKTESTING
# =============================================================================


class BacktestRun(Base):
    """Backtesting run results and metrics."""

    __tablename__ = "backtest_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Backtest Configuration
    name = Column(String(200), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    initial_capital = Column(DECIMAL(15, 2), nullable=False)

    # Data Configuration
    data_frequency = Column(String(20), default="daily")  # daily, hourly, etc.
    data_provider = Column(String(50), default="yfinance")
    survivorship_bias_free = Column(Boolean, default=False)

    # Execution Settings
    commission_per_trade = Column(DECIMAL(8, 2), default=1.0)
    slippage_bps = Column(DECIMAL(6, 2), default=5.0)  # Basis points
    market_impact_model = Column(String(50), default="linear")

    # Results Summary
    status = Column(SQLEnum(RunStatus), nullable=False)
    final_portfolio_value = Column(DECIMAL(15, 2))
    total_return_pct = Column(DECIMAL(8, 4))
    annualized_return_pct = Column(DECIMAL(8, 4))
    max_drawdown_pct = Column(DECIMAL(5, 2))
    sharpe_ratio = Column(DECIMAL(6, 4))
    total_trades = Column(Integer, default=0)
    win_rate_pct = Column(DECIMAL(5, 2))

    # Execution Details
    trades_executed = Column(Integer, default=0)
    signals_generated = Column(Integer, default=0)
    execution_time_seconds = Column(DECIMAL(10, 2))
    memory_usage_mb = Column(DECIMAL(10, 2))

    # Detailed Results (JSON)
    daily_returns = Column(JSON)  # Array of daily returns
    portfolio_values = Column(JSON)  # Array of portfolio values over time
    trade_history = Column(JSON)  # Detailed trade records
    performance_metrics = Column(JSON)  # All calculated metrics

    # Error Handling
    error_message = Column(Text)
    warnings = Column(JSON)

    # Audit
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    started_at = Column(TIMESTAMP(timezone=True))
    completed_at = Column(TIMESTAMP(timezone=True))

    __table_args__ = (
        Index("idx_strategy_backtest", "strategy_id", "created_at"),
        Index("idx_backtest_status_date", "status", "created_at"),  # Made unique
    )


# =============================================================================
# STRATEGY INTEGRATION LAYER (merged from strategy_integration.py)
# =============================================================================


class StrategyServiceType(enum.Enum):
    ATR_OPTIONS = "atr_options_strategy"
    DCA_STRATEGY = "dca_strategy"
    MOMENTUM = "momentum_strategy"
    PAIRS_TRADING = "pairs_trading"
    COVERED_CALL = "covered_call"
    IRON_CONDOR = "iron_condor"


class StrategyService(Base):
    """Registry of available strategy services."""

    __tablename__ = "strategy_services"

    id = Column(Integer, primary_key=True, autoincrement=True)
    service_type = Column(String(50), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    description = Column(Text)

    # Service Configuration
    service_module = Column(String(200), nullable=False)
    service_class = Column(String(100), nullable=False)

    # UI Configuration for StrategiesManager.tsx
    category = Column(String(20), nullable=False)
    complexity = Column(String(20), nullable=False)
    min_capital = Column(DECIMAL(15, 2), nullable=False)
    expected_return_annual = Column(String(50))
    max_drawdown = Column(String(20))
    time_horizon = Column(String(50))

    # Supported Parameters (JSON schema for UI generation)
    supported_parameters = Column(JSON)
    default_parameters = Column(JSON)

    # Availability
    is_available = Column(Boolean, default=True)
    requires_approval = Column(Boolean, default=False)

    # Performance Tracking
    success_rate = Column(DECIMAL(5, 2))
    avg_return = Column(DECIMAL(8, 4))

    # Audit
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class StrategyExecution(Base):
    """Execution parameters for strategy instances."""

    __tablename__ = "strategy_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Execution Configuration
    brokerage = Column(String(20), nullable=False)
    account_number = Column(String(50))

    # Capital Management
    allocated_capital = Column(DECIMAL(15, 2), nullable=False)
    current_capital = Column(DECIMAL(15, 2), nullable=False)
    profit_target_pct = Column(DECIMAL(5, 2), default=20.0)
    stop_loss_pct = Column(DECIMAL(5, 2), default=10.0)
    reinvest_profit_pct = Column(DECIMAL(5, 2), default=80.0)

    # Automation Settings
    is_automated = Column(Boolean, default=True)
    max_positions = Column(Integer, default=10)
    position_size_pct = Column(DECIMAL(5, 2), default=5.0)

    # Performance Tracking
    total_pnl = Column(DECIMAL(15, 2), default=0)
    total_pnl_pct = Column(DECIMAL(8, 4), default=0)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)

    # Execution State
    last_execution = Column(DateTime)
    next_execution = Column(DateTime)
    execution_frequency = Column(String(20), default="daily")

    # Strategy-Specific Parameters (JSON for flexibility)
    strategy_parameters = Column(JSON)

    # Audit
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    strategy = relationship("Strategy", back_populates="executions")
    user = relationship(
        "User", back_populates="strategy_executions"
    )  # Fixed: Use back_populates instead of backref


# Predefined strategy service definitions
STRATEGY_SERVICE_DEFINITIONS = [
    {
        "service_type": "atr_options_strategy",
        "display_name": "ATR Matrix Options",
        "description": "Automated options trading using ATR Matrix signals.",
        "service_module": "backend.services.atr_options_strategy",
        "service_class": "ATROptionsStrategy",
        "category": "options",
        "complexity": "advanced",
        "min_capital": 10000,
        "expected_return_annual": "15-25% monthly",
        "max_drawdown": "8-12%",
        "time_horizon": "1-45 days",
        "is_available": True,
    },
    {
        "service_type": "dca_strategy",
        "display_name": "DCA Strategy Suite",
        "description": "Multiple renowned DCA strategies with real market data analysis.",
        "service_module": "backend.services.dca_strategy",
        "service_class": "DCAStrategyService",
        "category": "stocks",
        "complexity": "intermediate",
        "min_capital": 5000,
        "expected_return_annual": "12-18%",
        "max_drawdown": "5-8%",
        "time_horizon": "3-30 days",
        "is_available": True,
    },
]
