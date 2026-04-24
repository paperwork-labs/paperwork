"""Add strategy_backtests table.

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "strategy_backtests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("strategy_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        # Configuration
        sa.Column(
            "status",
            sa.Enum("pending", "running", "completed", "failed", "cancelled", name="backteststatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("start_date", sa.DateTime(), nullable=False),
        sa.Column("end_date", sa.DateTime(), nullable=False),
        sa.Column("initial_capital", sa.DECIMAL(15, 2), server_default="100000"),
        sa.Column("slippage_bps", sa.DECIMAL(5, 2), server_default="5.0"),
        sa.Column("commission_per_trade", sa.DECIMAL(10, 4), server_default="1.0"),
        sa.Column("triggered_by", sa.String(50), server_default="manual"),
        sa.Column("strategy_snapshot", postgresql.JSON(astext_type=sa.Text())),
        # Core Metrics
        sa.Column("final_capital", sa.DECIMAL(15, 2)),
        sa.Column("total_return_pct", sa.DECIMAL(10, 4)),
        sa.Column("max_drawdown_pct", sa.DECIMAL(10, 4)),
        sa.Column("sharpe_ratio", sa.DECIMAL(8, 4)),
        sa.Column("sortino_ratio", sa.DECIMAL(8, 4)),
        sa.Column("calmar_ratio", sa.DECIMAL(8, 4)),
        # Trade Statistics
        sa.Column("total_trades", sa.Integer()),
        sa.Column("winning_trades", sa.Integer()),
        sa.Column("losing_trades", sa.Integer()),
        sa.Column("win_rate", sa.DECIMAL(6, 4)),
        sa.Column("profit_factor", sa.DECIMAL(10, 4)),
        sa.Column("avg_trade_pnl", sa.DECIMAL(15, 2)),
        sa.Column("avg_win", sa.DECIMAL(15, 2)),
        sa.Column("avg_loss", sa.DECIMAL(15, 2)),
        sa.Column("max_win", sa.DECIMAL(15, 2)),
        sa.Column("max_loss", sa.DECIMAL(15, 2)),
        sa.Column("avg_holding_days", sa.DECIMAL(8, 2)),
        # Risk Metrics
        sa.Column("volatility_annual", sa.DECIMAL(10, 4)),
        sa.Column("beta", sa.DECIMAL(8, 4)),
        sa.Column("alpha", sa.DECIMAL(8, 4)),
        sa.Column("var_95", sa.DECIMAL(10, 4)),
        sa.Column("cvar_95", sa.DECIMAL(10, 4)),
        # Time-based Analysis
        sa.Column("best_month_pct", sa.DECIMAL(10, 4)),
        sa.Column("worst_month_pct", sa.DECIMAL(10, 4)),
        sa.Column("best_year_pct", sa.DECIMAL(10, 4)),
        sa.Column("worst_year_pct", sa.DECIMAL(10, 4)),
        sa.Column("positive_months", sa.Integer()),
        sa.Column("negative_months", sa.Integer()),
        # Raw Data
        sa.Column("equity_curve", postgresql.JSON(astext_type=sa.Text())),
        sa.Column("trades_json", postgresql.JSON(astext_type=sa.Text())),
        sa.Column("monthly_returns", postgresql.JSON(astext_type=sa.Text())),
        sa.Column("daily_returns", postgresql.JSON(astext_type=sa.Text())),
        # Validation
        sa.Column("passed_veto_gates", sa.Boolean(), server_default="true"),
        sa.Column("veto_reasons", postgresql.JSON(astext_type=sa.Text())),
        sa.Column("confidence_score", sa.DECIMAL(5, 2)),
        # Execution
        sa.Column("error_message", sa.Text()),
        sa.Column("execution_time_ms", sa.Integer()),
        sa.Column("symbols_tested", sa.Integer()),
        sa.Column("bars_processed", sa.Integer()),
        # Audit
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime()),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )

    # Indexes
    op.create_index("idx_backtest_strategy", "strategy_backtests", ["strategy_id"])
    op.create_index("idx_backtest_status", "strategy_backtests", ["status"])
    op.create_index("idx_backtest_created", "strategy_backtests", ["created_at"])
    op.create_index("idx_backtest_sharpe", "strategy_backtests", ["sharpe_ratio"])


def downgrade() -> None:
    op.drop_index("idx_backtest_sharpe", table_name="strategy_backtests")
    op.drop_index("idx_backtest_created", table_name="strategy_backtests")
    op.drop_index("idx_backtest_status", table_name="strategy_backtests")
    op.drop_index("idx_backtest_strategy", table_name="strategy_backtests")
    op.drop_table("strategy_backtests")
    op.execute("DROP TYPE IF EXISTS backteststatus")
