"""Tests for OrderManager and RiskGate order lifecycle.

Covers: MAX_ORDER_VALUE blocking, preview + submit happy path,
and RiskViolation propagation.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.order import OrderStatus
from app.services.execution.broker_base import OrderRequest
from app.services.execution.order_manager import OrderManager
from app.services.execution.risk_gate import RiskGate, RiskViolation


def _make_mock_db(snapshot_price=None):
    """Build a mock Session for price-snapshot queries.

    Mocks: db.query(MarketSnapshot.current_price).filter(...).order_by(...).first()
    """
    snap_chain = MagicMock()
    if snapshot_price is not None:
        snap_chain.filter.return_value.order_by.return_value.first.return_value = (snapshot_price,)
    else:
        snap_chain.filter.return_value.order_by.return_value.first.return_value = None

    db = MagicMock()
    db.query.return_value = snap_chain

    return db


class TestRiskGate:
    """Risk gate enforcement in RiskGate.check()."""

    def setup_method(self):
        self.gate = RiskGate()

    def test_max_order_value_blocks(self):
        db = _make_mock_db()
        req = OrderRequest.from_user_input(
            symbol="AAPL", side="buy", order_type="market", quantity=1000
        )
        with pytest.raises(RiskViolation, match="exceeds"):
            self.gate.check(req, price_estimate=200.0, db=db)

    def test_under_max_order_value_passes(self):
        db = _make_mock_db()
        req = OrderRequest.from_user_input(
            symbol="AAPL", side="buy", order_type="market", quantity=10
        )
        warnings = self.gate.check(req, price_estimate=150.0, db=db)
        assert isinstance(warnings, list)

    def test_below_max_order_value_returns_warnings_list(self):
        db = _make_mock_db()
        req = OrderRequest.from_user_input(
            symbol="AAPL", side="buy", order_type="market", quantity=1
        )
        warnings = self.gate.check(req, price_estimate=0, db=db)
        assert isinstance(warnings, list)


class TestPriceEstimation:
    """RiskGate.estimate_price() fallback logic."""

    def setup_method(self):
        self.gate = RiskGate()

    def test_uses_limit_price_first(self):
        db = MagicMock()
        assert self.gate.estimate_price(db, "AAPL", 150.0, 140.0) == 150.0

    def test_falls_back_to_stop_price(self):
        db = MagicMock()
        assert self.gate.estimate_price(db, "AAPL", None, 140.0) == 140.0

    def test_falls_back_to_snapshot(self):
        db = _make_mock_db(snapshot_price=175.50)
        assert self.gate.estimate_price(db, "AAPL", None, None) == 175.50

    def test_raises_when_no_price_available(self):
        """Conservative fail-safe: reject order if price cannot be determined."""
        db = _make_mock_db(snapshot_price=None)
        with pytest.raises(RiskViolation, match="No price available"):
            self.gate.estimate_price(db, "AAPL", None, None)

    def test_raises_when_price_parse_fails(self):
        """Conservative fail-safe: reject order if price cannot be parsed."""
        snap_chain = MagicMock()
        snap_chain.filter.return_value.order_by.return_value.first.return_value = ("invalid_price",)
        db = MagicMock()
        db.query.return_value = snap_chain
        with pytest.raises(RiskViolation, match="Cannot parse price"):
            self.gate.estimate_price(db, "AAPL", None, None)


class TestOrderManagerPreview:
    """OrderManager.preview() integration."""

    @pytest.fixture
    def manager(self):
        return OrderManager()

    @pytest.mark.asyncio
    async def test_preview_blocks_on_risk_violation(self, manager):
        """High quantity should trigger RiskViolation from RiskGate."""
        db = _make_mock_db(snapshot_price=200.0)
        req = OrderRequest.from_user_input(
            symbol="AAPL", side="buy", order_type="market", quantity=1000
        )

        with pytest.raises(RiskViolation):
            await manager.preview(db=db, req=req, user_id=1)

    @pytest.mark.asyncio
    async def test_preview_passes_with_small_order(self, manager):
        """Small order should pass risk checks and create preview."""
        db = _make_mock_db(snapshot_price=150.0)
        req = OrderRequest.from_user_input(
            symbol="AAPL", side="buy", order_type="limit", quantity=5, limit_price=150.0
        )

        # Mock broker preview
        with patch("app.services.execution.order_manager.broker_router") as mock_router:
            mock_executor = MagicMock()
            mock_executor.preview_order = AsyncMock(
                return_value=MagicMock(
                    ok=True,
                    estimated_commission=1.0,
                    estimated_margin_impact=500.0,
                    estimated_equity_with_loan=50000.0,
                    raw={"test": True},
                )
            )
            mock_router.get.return_value = mock_executor

            # Mock Order creation
            with patch("app.services.execution.order_manager.Order") as MockOrder:
                mock_order = MagicMock()
                mock_order.id = 1
                mock_order.status = OrderStatus.PREVIEW.value
                MockOrder.return_value = mock_order
                db.add = MagicMock()
                db.commit = MagicMock()
                db.refresh = MagicMock()

                result = await manager.preview(db=db, req=req, user_id=1)

                assert result["order_id"] == 1
                assert result["status"] == OrderStatus.PREVIEW.value


class TestOrderManagerSubmit:
    """OrderManager.submit() behavior.

    These tests exercise the live submit path. D137 flipped
    ``SHADOW_TRADING_MODE`` default-on, so we explicitly turn it off here via
    ``monkeypatch`` — otherwise ``OrderManager.submit`` short-circuits into
    ``ShadowOrderRecorder`` before any of these branches run.
    """

    @pytest.fixture
    def manager(self):
        return OrderManager()

    @pytest.fixture(autouse=True)
    def _disable_shadow_mode(self, monkeypatch):
        from app.config import settings as app_settings

        monkeypatch.setattr(app_settings, "SHADOW_TRADING_MODE", False, raising=False)

    @pytest.mark.asyncio
    async def test_submit_rejects_non_preview_order(self, manager):
        """OrderManager.submit should reject orders not in PREVIEW status."""
        db = MagicMock()
        mock_order = MagicMock()
        mock_order.status = OrderStatus.SUBMITTED.value
        db.query.return_value.filter.return_value.first.return_value = mock_order

        result = await manager.submit(db=db, order_id=1, user_id=1)
        assert "error" in result
        assert "cannot submit" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_submit_rejects_missing_order(self, manager):
        """Non-existent order should return error."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        result = await manager.submit(db=db, order_id=999, user_id=1)
        assert result["error"] == "Order not found"
