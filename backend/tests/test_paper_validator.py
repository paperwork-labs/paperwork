"""Comprehensive unit tests for PaperValidator service.

Tests: start_validation, check_validation, promote_to_live,
reset_validation, and _calculate_metrics.
"""

import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from backend.services.strategy.paper_validator import (
    PaperValidator,
    ValidationConfig,
    ValidationResult,
    ValidationStatus,
)
from backend.models.order import OrderStatus
from backend.models.strategy import ExecutionMode, StrategyStatus


def _make_mock_db():
    """Create a mock database session."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.all.return_value = []
    return db


def _make_mock_strategy(
    strategy_id: int = 1,
    user_id: int = 1,
    execution_mode: ExecutionMode = ExecutionMode.PAPER,
    status: StrategyStatus = StrategyStatus.DRAFT,
    audit_metadata: dict = None,
    is_validated: bool = False,
):
    """Create a mock Strategy object."""
    strategy = MagicMock()
    strategy.id = strategy_id
    strategy.user_id = user_id
    strategy.execution_mode = execution_mode
    strategy.status = status
    strategy.audit_metadata = audit_metadata
    strategy.is_validated = is_validated
    strategy.validation_errors = None
    strategy.validation_warnings = None
    return strategy


def _make_mock_order(
    order_id: int = 1,
    strategy_id: int = 1,
    user_id: int = 1,
    slippage_dollars: float = None,
    decision_price: float = 100.0,
    quantity: float = 10.0,
    filled_avg_price: float = 100.0,
    filled_quantity: float = 10.0,
):
    """Create a mock Order object."""
    order = MagicMock()
    order.id = order_id
    order.strategy_id = strategy_id
    order.user_id = user_id
    order.status = OrderStatus.FILLED.value
    order.broker_type = "paper"
    order.slippage_dollars = slippage_dollars
    order.decision_price = decision_price
    order.quantity = quantity
    order.filled_avg_price = filled_avg_price
    order.filled_quantity = filled_quantity
    # Set realized_pnl from slippage_dollars (negative slippage = positive P&L)
    order.realized_pnl = -slippage_dollars if slippage_dollars is not None else None
    # Set cost_basis for loss percentage calculation (per-share cost)
    order.cost_basis = decision_price if slippage_dollars is not None and slippage_dollars > 0 else None
    return order


class TestStartValidation:
    """Tests for PaperValidator.start_validation()."""

    def test_start_validation_success(self):
        """Successfully starts validation for a valid strategy."""
        db = _make_mock_db()
        strategy = _make_mock_strategy()
        db.query.return_value.filter.return_value.first.return_value = strategy

        validator = PaperValidator(db)
        result = validator.start_validation(strategy_id=1, user_id=1)

        assert result["status"] == "started"
        assert result["strategy_id"] == 1
        assert "min_duration_days" in result["validation_config"]
        assert "min_trades" in result["validation_config"]
        assert strategy.execution_mode == ExecutionMode.PAPER
        assert strategy.status == StrategyStatus.ACTIVE
        assert strategy.is_validated is False
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(strategy)

    def test_start_validation_stores_metadata(self):
        """Stores validation metadata with start_time and config."""
        db = _make_mock_db()
        strategy = _make_mock_strategy(audit_metadata=None)
        db.query.return_value.filter.return_value.first.return_value = strategy

        config = ValidationConfig(min_duration_days=14, min_trades=10)
        validator = PaperValidator(db, config=config)
        
        with patch(
            "backend.services.strategy.paper_validator.datetime"
        ) as mock_datetime:
            mock_now = datetime(2026, 3, 28, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now
            mock_datetime.fromisoformat = datetime.fromisoformat
            
            validator.start_validation(strategy_id=1, user_id=1)

        assert "paper_validation" in strategy.audit_metadata
        validation_data = strategy.audit_metadata["paper_validation"]
        assert "started_at" in validation_data
        assert validation_data["config"]["min_duration_days"] == 14
        assert validation_data["config"]["min_trades"] == 10

    def test_start_validation_strategy_not_found(self):
        """Returns error when strategy not found."""
        db = _make_mock_db()
        db.query.return_value.filter.return_value.first.return_value = None

        validator = PaperValidator(db)
        result = validator.start_validation(strategy_id=999, user_id=1)

        assert "error" in result
        assert result["error"] == "Strategy not found"
        db.commit.assert_not_called()

    def test_start_validation_already_live(self):
        """Returns error when strategy is already in live mode."""
        db = _make_mock_db()
        strategy = _make_mock_strategy(execution_mode=ExecutionMode.LIVE)
        db.query.return_value.filter.return_value.first.return_value = strategy

        validator = PaperValidator(db)
        result = validator.start_validation(strategy_id=1, user_id=1)

        assert "error" in result
        assert "already in live mode" in result["error"]
        db.commit.assert_not_called()

    def test_start_validation_preserves_existing_metadata(self):
        """Preserves existing audit_metadata when adding validation data."""
        db = _make_mock_db()
        existing_metadata = {"other_data": "should_persist"}
        strategy = _make_mock_strategy(audit_metadata=existing_metadata)
        db.query.return_value.filter.return_value.first.return_value = strategy

        validator = PaperValidator(db)
        validator.start_validation(strategy_id=1, user_id=1)

        assert strategy.audit_metadata["other_data"] == "should_persist"
        assert "paper_validation" in strategy.audit_metadata


class TestCheckValidation:
    """Tests for PaperValidator.check_validation()."""

    def test_check_validation_not_started(self):
        """Returns NOT_STARTED when validation not started."""
        db = _make_mock_db()
        strategy = _make_mock_strategy(audit_metadata={})
        db.query.return_value.filter.return_value.first.return_value = strategy

        validator = PaperValidator(db)
        result = validator.check_validation(strategy_id=1, user_id=1)

        assert result.status == ValidationStatus.NOT_STARTED
        assert result.can_go_live is False
        assert "not started" in result.message.lower()

    def test_check_validation_strategy_not_found(self):
        """Returns NOT_STARTED when strategy not found."""
        db = _make_mock_db()
        db.query.return_value.filter.return_value.first.return_value = None

        validator = PaperValidator(db)
        result = validator.check_validation(strategy_id=999, user_id=1)

        assert result.status == ValidationStatus.NOT_STARTED
        assert result.can_go_live is False
        assert "not found" in result.message.lower()

    def test_check_validation_in_progress_min_duration_not_met(self):
        """Returns IN_PROGRESS when min_duration_days not met."""
        db = _make_mock_db()
        started_at = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        strategy = _make_mock_strategy(
            audit_metadata={
                "paper_validation": {
                    "started_at": started_at,
                    "config": {"min_duration_days": 7, "min_trades": 5},
                }
            }
        )
        db.query.return_value.filter.return_value.first.return_value = strategy
        db.query.return_value.filter.return_value.all.return_value = []

        config = ValidationConfig(min_duration_days=7, min_trades=5)
        validator = PaperValidator(db, config=config)
        result = validator.check_validation(strategy_id=1, user_id=1)

        assert result.status == ValidationStatus.IN_PROGRESS
        assert result.can_go_live is False
        assert "remaining" in result.message.lower()

    def test_check_validation_in_progress_min_trades_not_met(self):
        """Returns IN_PROGRESS when min_trades not met."""
        db = _make_mock_db()
        started_at = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        strategy = _make_mock_strategy(
            audit_metadata={
                "paper_validation": {
                    "started_at": started_at,
                    "config": {"min_duration_days": 7, "min_trades": 5},
                }
            }
        )
        
        orders = [_make_mock_order(slippage_dollars=-5.0) for _ in range(2)]
        
        db.query.return_value.filter.return_value.first.return_value = strategy
        db.query.return_value.filter.return_value.all.return_value = orders

        config = ValidationConfig(
            min_duration_days=7, min_trades=5, min_win_rate_pct=40.0
        )
        validator = PaperValidator(db, config=config)
        result = validator.check_validation(strategy_id=1, user_id=1)

        assert result.status == ValidationStatus.IN_PROGRESS
        assert result.can_go_live is False
        assert "more trade" in result.message.lower()

    def test_check_validation_passed_all_thresholds_met(self):
        """Returns PASSED when all thresholds met."""
        db = _make_mock_db()
        started_at = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        strategy = _make_mock_strategy(
            audit_metadata={
                "paper_validation": {
                    "started_at": started_at,
                    "config": {"min_duration_days": 7, "min_trades": 5},
                }
            }
        )
        
        winning_orders = [
            _make_mock_order(order_id=i, slippage_dollars=-10.0)
            for i in range(4)
        ]
        losing_orders = [
            _make_mock_order(order_id=5, slippage_dollars=5.0)
        ]
        all_orders = winning_orders + losing_orders
        
        db.query.return_value.filter.return_value.first.return_value = strategy
        db.query.return_value.filter.return_value.all.return_value = all_orders

        config = ValidationConfig(
            min_duration_days=7,
            min_trades=5,
            min_win_rate_pct=40.0,
            max_drawdown_pct=20.0,
            min_profit_factor=1.0,
        )
        validator = PaperValidator(db, config=config)
        result = validator.check_validation(strategy_id=1, user_id=1)

        assert result.status == ValidationStatus.PASSED
        assert result.can_go_live is True
        assert result.trades_count == 5
        assert result.win_rate_pct == 80.0

    def test_check_validation_failed_win_rate_below_threshold(self):
        """Returns FAILED when win_rate below threshold."""
        db = _make_mock_db()
        started_at = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        strategy = _make_mock_strategy(
            audit_metadata={
                "paper_validation": {
                    "started_at": started_at,
                    "config": {"min_duration_days": 7, "min_trades": 5},
                }
            }
        )
        
        winning_orders = [_make_mock_order(order_id=1, slippage_dollars=-5.0)]
        losing_orders = [
            _make_mock_order(order_id=i, slippage_dollars=5.0) for i in range(2, 6)
        ]
        all_orders = winning_orders + losing_orders
        
        db.query.return_value.filter.return_value.first.return_value = strategy
        db.query.return_value.filter.return_value.all.return_value = all_orders

        config = ValidationConfig(
            min_duration_days=7,
            min_trades=5,
            min_win_rate_pct=40.0,
            max_drawdown_pct=50.0,
            min_profit_factor=0.5,
            max_avg_loss_pct=10.0,
        )
        validator = PaperValidator(db, config=config)
        result = validator.check_validation(strategy_id=1, user_id=1)

        assert result.status == ValidationStatus.FAILED
        assert result.can_go_live is False
        assert result.win_rate_pct == 20.0
        assert "min_win_rate" in result.message

    def test_check_validation_failed_max_drawdown_exceeded(self):
        """Returns FAILED when max_drawdown exceeded."""
        db = _make_mock_db()
        started_at = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        strategy = _make_mock_strategy(
            audit_metadata={
                "paper_validation": {
                    "started_at": started_at,
                    "config": {"min_duration_days": 7, "min_trades": 5},
                }
            }
        )
        
        orders = [_make_mock_order(order_id=i, slippage_dollars=-5.0) for i in range(5)]
        
        db.query.return_value.filter.return_value.first.return_value = strategy
        db.query.return_value.filter.return_value.all.return_value = orders

        config = ValidationConfig(
            min_duration_days=7,
            min_trades=5,
            min_win_rate_pct=40.0,
            max_drawdown_pct=-1.0,
        )
        validator = PaperValidator(db, config=config)
        result = validator.check_validation(strategy_id=1, user_id=1)

        assert result.status == ValidationStatus.FAILED
        assert result.can_go_live is False
        assert "max_drawdown" in result.message


class TestPromoteToLive:
    """Tests for PaperValidator.promote_to_live()."""

    def test_promote_to_live_success(self):
        """Promotes strategy when validation passed."""
        db = _make_mock_db()
        started_at = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        strategy = _make_mock_strategy(
            audit_metadata={
                "paper_validation": {
                    "started_at": started_at,
                    "config": {"min_duration_days": 7, "min_trades": 5},
                }
            }
        )
        
        orders = [_make_mock_order(order_id=i, slippage_dollars=-5.0) for i in range(6)]
        
        db.query.return_value.filter.return_value.first.return_value = strategy
        db.query.return_value.filter.return_value.all.return_value = orders

        config = ValidationConfig(
            min_duration_days=7, min_trades=5, min_win_rate_pct=40.0
        )
        validator = PaperValidator(db, config=config)
        result = validator.promote_to_live(strategy_id=1, user_id=1)

        assert result["status"] == "promoted"
        assert result["execution_mode"] == "live"
        assert strategy.execution_mode == ExecutionMode.LIVE
        assert strategy.is_validated is True
        db.commit.assert_called()

    def test_promote_to_live_rejects_when_not_passed(self):
        """Rejects promotion when validation not passed."""
        db = _make_mock_db()
        started_at = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        strategy = _make_mock_strategy(
            audit_metadata={
                "paper_validation": {
                    "started_at": started_at,
                    "config": {"min_duration_days": 7, "min_trades": 5},
                }
            }
        )
        
        db.query.return_value.filter.return_value.first.return_value = strategy
        db.query.return_value.filter.return_value.all.return_value = []

        config = ValidationConfig(min_duration_days=7, min_trades=5)
        validator = PaperValidator(db, config=config)
        result = validator.promote_to_live(strategy_id=1, user_id=1)

        assert "error" in result
        assert "Cannot promote" in result["error"]
        assert strategy.execution_mode != ExecutionMode.LIVE

    def test_promote_to_live_rejects_when_not_started(self):
        """Rejects promotion when validation not started."""
        db = _make_mock_db()
        strategy = _make_mock_strategy(audit_metadata={})
        db.query.return_value.filter.return_value.first.return_value = strategy

        validator = PaperValidator(db)
        result = validator.promote_to_live(strategy_id=1, user_id=1)

        assert "error" in result
        assert "Cannot promote" in result["error"]
        assert "not started" in result["error"].lower()

    def test_promote_to_live_records_completion_metadata(self):
        """Records promotion metadata with final metrics."""
        db = _make_mock_db()
        started_at = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        strategy = _make_mock_strategy(
            audit_metadata={
                "paper_validation": {
                    "started_at": started_at,
                    "config": {"min_duration_days": 7, "min_trades": 5},
                }
            }
        )
        
        orders = [_make_mock_order(order_id=i, slippage_dollars=-5.0) for i in range(6)]
        
        db.query.return_value.filter.return_value.first.return_value = strategy
        db.query.return_value.filter.return_value.all.return_value = orders

        config = ValidationConfig(
            min_duration_days=7, min_trades=5, min_win_rate_pct=40.0
        )
        validator = PaperValidator(db, config=config)
        validator.promote_to_live(strategy_id=1, user_id=1)

        validation_data = strategy.audit_metadata["paper_validation"]
        assert "completed_at" in validation_data
        assert validation_data["promoted_to_live"] is True
        assert "final_metrics" in validation_data


class TestResetValidation:
    """Tests for PaperValidator.reset_validation()."""

    def test_reset_validation_clears_metadata(self):
        """Clears validation metadata."""
        db = _make_mock_db()
        strategy = _make_mock_strategy(
            audit_metadata={
                "paper_validation": {
                    "started_at": "2026-03-01T00:00:00+00:00",
                    "config": {},
                },
                "other_data": "should_persist",
            }
        )
        db.query.return_value.filter.return_value.first.return_value = strategy

        validator = PaperValidator(db)
        result = validator.reset_validation(strategy_id=1, user_id=1)

        assert result["status"] == "reset"
        assert "paper_validation" not in strategy.audit_metadata
        assert strategy.audit_metadata["other_data"] == "should_persist"
        assert strategy.execution_mode == ExecutionMode.PAPER
        assert strategy.is_validated is False
        db.commit.assert_called_once()

    def test_reset_validation_allows_restart(self):
        """Allows re-starting validation after reset."""
        db = _make_mock_db()
        strategy = _make_mock_strategy(
            audit_metadata={
                "paper_validation": {
                    "started_at": "2026-03-01T00:00:00+00:00",
                }
            }
        )
        db.query.return_value.filter.return_value.first.return_value = strategy

        validator = PaperValidator(db)
        
        reset_result = validator.reset_validation(strategy_id=1, user_id=1)
        assert reset_result["status"] == "reset"
        
        start_result = validator.start_validation(strategy_id=1, user_id=1)
        assert start_result["status"] == "started"
        assert "paper_validation" in strategy.audit_metadata

    def test_reset_validation_strategy_not_found(self):
        """Returns error when strategy not found."""
        db = _make_mock_db()
        db.query.return_value.filter.return_value.first.return_value = None

        validator = PaperValidator(db)
        result = validator.reset_validation(strategy_id=999, user_id=1)

        assert "error" in result
        assert result["error"] == "Strategy not found"


class TestCalculateMetrics:
    """Tests for PaperValidator._calculate_metrics()."""

    def test_calculate_metrics_correct_win_rate(self):
        """Computes correct win_rate."""
        db = _make_mock_db()
        validator = PaperValidator(db)
        
        winning_orders = [
            _make_mock_order(order_id=i, slippage_dollars=-10.0) for i in range(3)
        ]
        losing_orders = [
            _make_mock_order(order_id=4, slippage_dollars=5.0),
            _make_mock_order(order_id=5, slippage_dollars=5.0),
        ]
        all_orders = winning_orders + losing_orders

        metrics = validator._calculate_metrics(all_orders)

        assert metrics["win_rate_pct"] == 60.0
        assert metrics["trades_count"] == 5

    def test_calculate_metrics_correct_profit_factor(self):
        """Computes correct profit_factor."""
        db = _make_mock_db()
        validator = PaperValidator(db)
        
        winning_orders = [
            _make_mock_order(order_id=1, slippage_dollars=-30.0),
            _make_mock_order(order_id=2, slippage_dollars=-20.0),
        ]
        losing_orders = [
            _make_mock_order(order_id=3, slippage_dollars=10.0),
        ]
        all_orders = winning_orders + losing_orders

        metrics = validator._calculate_metrics(all_orders)

        assert metrics["profit_factor"] == 5.0
        assert metrics["win_rate_pct"] == pytest.approx(66.67, rel=0.01)

    def test_calculate_metrics_empty_order_list(self):
        """Handles empty order list."""
        db = _make_mock_db()
        validator = PaperValidator(db)

        metrics = validator._calculate_metrics([])

        assert metrics["trades_count"] == 0
        assert metrics["win_rate_pct"] == 0.0
        assert metrics["profit_factor"] == 0.0
        assert metrics["total_return_pct"] == 0.0
        assert metrics["max_drawdown_pct"] == 0.0
        assert metrics["avg_loss_pct"] == 0.0

    def test_calculate_metrics_orders_with_no_pnl_data(self):
        """Handles orders with no P&L data (None slippage)."""
        db = _make_mock_db()
        validator = PaperValidator(db)
        
        orders = [
            _make_mock_order(order_id=1, slippage_dollars=None),
            _make_mock_order(order_id=2, slippage_dollars=None),
        ]

        metrics = validator._calculate_metrics(orders)

        assert metrics["trades_count"] == 0
        assert metrics["win_rate_pct"] == 0.0

    def test_calculate_metrics_all_winning_trades(self):
        """Handles all winning trades (profit_factor is high)."""
        db = _make_mock_db()
        validator = PaperValidator(db)
        
        orders = [
            _make_mock_order(order_id=i, slippage_dollars=-10.0) for i in range(5)
        ]

        metrics = validator._calculate_metrics(orders)

        assert metrics["win_rate_pct"] == 100.0
        assert metrics["profit_factor"] == 999.0

    def test_calculate_metrics_all_losing_trades(self):
        """Handles all losing trades."""
        db = _make_mock_db()
        validator = PaperValidator(db)
        
        orders = [
            _make_mock_order(order_id=i, slippage_dollars=10.0) for i in range(5)
        ]

        metrics = validator._calculate_metrics(orders)

        assert metrics["win_rate_pct"] == 0.0
        assert metrics["profit_factor"] == 0.0
        assert metrics["avg_loss_pct"] > 0

    def test_calculate_metrics_avg_loss_pct_calculation(self):
        """Computes correct avg_loss_pct."""
        db = _make_mock_db()
        validator = PaperValidator(db)
        
        orders = [
            _make_mock_order(
                order_id=1,
                slippage_dollars=10.0,
                decision_price=100.0,
                quantity=10.0,
            ),
            _make_mock_order(
                order_id=2,
                slippage_dollars=20.0,
                decision_price=100.0,
                quantity=10.0,
            ),
        ]

        metrics = validator._calculate_metrics(orders)

        assert metrics["avg_loss_pct"] == 1.5


class TestValidationConfig:
    """Tests for ValidationConfig defaults and customization."""

    def test_default_config_values(self):
        """Verifies default configuration values."""
        config = ValidationConfig()

        assert config.min_duration_days == 7
        assert config.min_trades == 5
        assert config.max_drawdown_pct == 15.0
        assert config.min_win_rate_pct == 40.0
        assert config.min_profit_factor == 1.0
        assert config.max_avg_loss_pct == 5.0

    def test_custom_config_values(self):
        """Custom config values are respected."""
        config = ValidationConfig(
            min_duration_days=14,
            min_trades=10,
            max_drawdown_pct=10.0,
            min_win_rate_pct=50.0,
            min_profit_factor=1.5,
            max_avg_loss_pct=3.0,
        )

        assert config.min_duration_days == 14
        assert config.min_trades == 10
        assert config.max_drawdown_pct == 10.0
        assert config.min_win_rate_pct == 50.0
        assert config.min_profit_factor == 1.5
        assert config.max_avg_loss_pct == 3.0


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_validation_result_construction(self):
        """ValidationResult can be constructed with all fields."""
        result = ValidationResult(
            status=ValidationStatus.PASSED,
            days_elapsed=10,
            trades_count=15,
            win_rate_pct=65.0,
            total_return_pct=5.5,
            max_drawdown_pct=8.0,
            profit_factor=2.5,
            avg_loss_pct=1.5,
            checks=[{"name": "min_trades", "passed": True}],
            can_go_live=True,
            message="Validation passed.",
        )

        assert result.status == ValidationStatus.PASSED
        assert result.days_elapsed == 10
        assert result.trades_count == 15
        assert result.win_rate_pct == 65.0
        assert result.can_go_live is True


class TestRunChecks:
    """Tests for PaperValidator._run_checks()."""

    def test_run_checks_all_pass(self):
        """All checks pass with good metrics."""
        db = _make_mock_db()
        config = ValidationConfig(
            min_duration_days=7,
            min_trades=5,
            min_win_rate_pct=40.0,
            max_drawdown_pct=15.0,
            min_profit_factor=1.0,
            max_avg_loss_pct=5.0,
        )
        validator = PaperValidator(db, config=config)

        metrics = {
            "trades_count": 10,
            "win_rate_pct": 60.0,
            "max_drawdown_pct": 5.0,
            "profit_factor": 2.0,
            "avg_loss_pct": 2.0,
        }

        checks = validator._run_checks(days_elapsed=10, metrics=metrics)

        assert len(checks) == 6
        assert all(c["passed"] for c in checks)

    def test_run_checks_duration_fails(self):
        """Duration check fails when days_elapsed < min_duration_days."""
        db = _make_mock_db()
        config = ValidationConfig(min_duration_days=7)
        validator = PaperValidator(db, config=config)

        metrics = {
            "trades_count": 10,
            "win_rate_pct": 60.0,
            "max_drawdown_pct": 5.0,
            "profit_factor": 2.0,
            "avg_loss_pct": 2.0,
        }

        checks = validator._run_checks(days_elapsed=3, metrics=metrics)
        duration_check = next(c for c in checks if c["name"] == "min_duration")

        assert duration_check["passed"] is False
        assert duration_check["actual"] == 3
        assert duration_check["required"] == 7

    def test_run_checks_win_rate_fails(self):
        """Win rate check fails when below threshold."""
        db = _make_mock_db()
        config = ValidationConfig(min_win_rate_pct=40.0)
        validator = PaperValidator(db, config=config)

        metrics = {
            "trades_count": 10,
            "win_rate_pct": 30.0,
            "max_drawdown_pct": 5.0,
            "profit_factor": 2.0,
            "avg_loss_pct": 2.0,
        }

        checks = validator._run_checks(days_elapsed=10, metrics=metrics)
        win_rate_check = next(c for c in checks if c["name"] == "min_win_rate")

        assert win_rate_check["passed"] is False
        assert win_rate_check["actual"] == 30.0
        assert win_rate_check["required"] == 40.0

    def test_run_checks_drawdown_fails(self):
        """Drawdown check fails when above threshold."""
        db = _make_mock_db()
        config = ValidationConfig(max_drawdown_pct=15.0)
        validator = PaperValidator(db, config=config)

        metrics = {
            "trades_count": 10,
            "win_rate_pct": 60.0,
            "max_drawdown_pct": 20.0,
            "profit_factor": 2.0,
            "avg_loss_pct": 2.0,
        }

        checks = validator._run_checks(days_elapsed=10, metrics=metrics)
        drawdown_check = next(c for c in checks if c["name"] == "max_drawdown")

        assert drawdown_check["passed"] is False
        assert drawdown_check["actual"] == 20.0
        assert drawdown_check["required"] == 15.0
