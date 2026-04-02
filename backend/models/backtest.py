"""
Strategy Backtest Models.

Stores results of automated and manual backtest runs.
"""
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    DECIMAL,
    Text,
    Boolean,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from . import Base


class BacktestStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StrategyBacktest(Base):
    """
    Results of strategy backtest runs.

    Stores both the configuration used and the resulting metrics.
    """

    __tablename__ = "strategy_backtests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Configuration
    status = Column(
        SQLEnum(BacktestStatus), nullable=False, default=BacktestStatus.PENDING
    )
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    initial_capital = Column(DECIMAL(15, 2), default=100000)
    slippage_bps = Column(DECIMAL(5, 2), default=5.0)
    commission_per_trade = Column(DECIMAL(10, 4), default=1.0)
    triggered_by = Column(String(50), default="manual")  # manual, auto, api

    # Parameters snapshot (strategy config at time of backtest)
    strategy_snapshot = Column(JSON)

    # Core Metrics
    final_capital = Column(DECIMAL(15, 2))
    total_return_pct = Column(DECIMAL(10, 4))
    max_drawdown_pct = Column(DECIMAL(10, 4))
    sharpe_ratio = Column(DECIMAL(8, 4))
    sortino_ratio = Column(DECIMAL(8, 4))
    calmar_ratio = Column(DECIMAL(8, 4))

    # Trade Statistics
    total_trades = Column(Integer)
    winning_trades = Column(Integer)
    losing_trades = Column(Integer)
    win_rate = Column(DECIMAL(6, 4))
    profit_factor = Column(DECIMAL(10, 4))
    avg_trade_pnl = Column(DECIMAL(15, 2))
    avg_win = Column(DECIMAL(15, 2))
    avg_loss = Column(DECIMAL(15, 2))
    max_win = Column(DECIMAL(15, 2))
    max_loss = Column(DECIMAL(15, 2))
    avg_holding_days = Column(DECIMAL(8, 2))

    # Risk Metrics
    volatility_annual = Column(DECIMAL(10, 4))
    beta = Column(DECIMAL(8, 4))
    alpha = Column(DECIMAL(8, 4))
    var_95 = Column(DECIMAL(10, 4))  # Value at Risk 95%
    cvar_95 = Column(DECIMAL(10, 4))  # Conditional VaR

    # Time-based Analysis
    best_month_pct = Column(DECIMAL(10, 4))
    worst_month_pct = Column(DECIMAL(10, 4))
    best_year_pct = Column(DECIMAL(10, 4))
    worst_year_pct = Column(DECIMAL(10, 4))
    positive_months = Column(Integer)
    negative_months = Column(Integer)

    # Raw Data (for charting)
    equity_curve = Column(JSON)  # [{date, equity, drawdown}]
    trades_json = Column(JSON)  # [{symbol, side, qty, price, date, pnl}]
    monthly_returns = Column(JSON)  # [{month, return_pct}]
    daily_returns = Column(JSON)  # [float] for analysis

    # Validation
    passed_veto_gates = Column(Boolean, default=True)
    veto_reasons = Column(JSON)  # If failed any gates
    confidence_score = Column(DECIMAL(5, 2))  # 0-100

    # Execution
    error_message = Column(Text)
    execution_time_ms = Column(Integer)
    symbols_tested = Column(Integer)
    bars_processed = Column(Integer)

    # Audit
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime)

    # Relationships
    strategy = relationship("Strategy", back_populates="backtests")

    __table_args__ = (
        Index("idx_backtest_strategy", "strategy_id"),
        Index("idx_backtest_status", "status"),
        Index("idx_backtest_created", "created_at"),
        Index("idx_backtest_sharpe", "sharpe_ratio"),
    )

    def to_summary(self) -> dict:
        """Return a summary dict for API responses."""
        return {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "status": self.status.value if self.status else None,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "initial_capital": float(self.initial_capital) if self.initial_capital else None,
            "final_capital": float(self.final_capital) if self.final_capital else None,
            "total_return_pct": float(self.total_return_pct) if self.total_return_pct else None,
            "max_drawdown_pct": float(self.max_drawdown_pct) if self.max_drawdown_pct else None,
            "sharpe_ratio": float(self.sharpe_ratio) if self.sharpe_ratio else None,
            "sortino_ratio": float(self.sortino_ratio) if self.sortino_ratio else None,
            "total_trades": self.total_trades,
            "win_rate": float(self.win_rate) if self.win_rate else None,
            "profit_factor": float(self.profit_factor) if self.profit_factor else None,
            "passed_veto_gates": self.passed_veto_gates,
            "confidence_score": float(self.confidence_score) if self.confidence_score else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time_ms": self.execution_time_ms,
        }
