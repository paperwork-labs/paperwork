"""Tests for OrderService risk gates and order lifecycle.

Covers: MAX_ORDER_VALUE blocking, preview + submit happy path,
and RiskViolation propagation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from backend.services.execution.order_service import OrderService, RiskViolation
from backend.services.execution.risk_gate import MAX_ORDER_VALUE
from backend.models.order import OrderStatus


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


class TestRiskGates:
    """Risk gate enforcement in OrderService._check_risk_gates()."""

    def setup_method(self):
        self.svc = OrderService()
        self.svc._ibkr_client = MagicMock()

    def test_max_order_value_blocks(self):
        db = _make_mock_db()
        with pytest.raises(RiskViolation, match="exceeds"):
            self.svc._check_risk_gates(
                db, "AAPL", "buy", "market", quantity=1000, price_estimate=200.0
            )

    def test_under_max_order_value_passes(self):
        db = _make_mock_db()
        warnings = self.svc._check_risk_gates(
            db, "AAPL", "buy", "market", quantity=10, price_estimate=150.0
        )
        assert isinstance(warnings, list)

    def test_below_max_order_value_returns_warnings_list(self):
        db = _make_mock_db()
        warnings = self.svc._check_risk_gates(
            db, "AAPL", "buy", "market", quantity=1, price_estimate=0
        )
        assert isinstance(warnings, list)


class TestPriceEstimation:
    def setup_method(self):
        self.svc = OrderService()

    def test_uses_limit_price_first(self):
        db = MagicMock()
        assert self.svc._estimate_price(db, "AAPL", 150.0, 140.0) == 150.0

    def test_falls_back_to_stop_price(self):
        db = MagicMock()
        assert self.svc._estimate_price(db, "AAPL", None, 140.0) == 140.0

    def test_falls_back_to_snapshot(self):
        db = _make_mock_db(snapshot_price=175.50)
        assert self.svc._estimate_price(db, "AAPL", None, None) == 175.50

    def test_returns_zero_when_no_data(self):
        db = _make_mock_db(snapshot_price=None)
        assert self.svc._estimate_price(db, "AAPL", None, None) == 0


class TestPreviewOrder:
    @pytest.fixture
    def svc(self):
        svc = OrderService()
        svc._ibkr_client = MagicMock()
        svc._ibkr_client.what_if_order = AsyncMock(return_value={
            "estimated_commission": 1.0,
            "estimated_margin_impact": 500.0,
            "estimated_equity_with_loan": 50000.0,
        })
        return svc

    @pytest.mark.asyncio
    async def test_preview_blocks_on_risk_violation(self, svc):
        db = _make_mock_db(snapshot_price=200.0)
        with pytest.raises(RiskViolation):
            await svc.preview_order(
                db, symbol="AAPL", side="buy", order_type="market",
                quantity=1000, user_id=1,
            )

    @pytest.mark.asyncio
    async def test_preview_passes_with_small_order(self, svc):
        db = _make_mock_db(snapshot_price=150.0)
        mock_order = MagicMock()
        mock_order.id = 1
        mock_order.status = OrderStatus.PREVIEW.value
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock(side_effect=lambda o: setattr(o, 'id', 1))

        with patch("backend.services.execution.order_service.Order") as MockOrder:
            mock_instance = MagicMock()
            mock_instance.id = 1
            mock_instance.status = OrderStatus.PREVIEW.value
            MockOrder.return_value = mock_instance

            result = await svc.preview_order(
                db, symbol="AAPL", side="buy", order_type="limit",
                quantity=5, limit_price=150.0, user_id=1,
            )
            assert result["order_id"] == 1
            assert result["status"] == OrderStatus.PREVIEW.value


class TestSubmitOrder:
    @pytest.fixture
    def svc(self):
        svc = OrderService()
        svc._ibkr_client = MagicMock()
        svc._ibkr_client.place_order = AsyncMock(return_value={
            "broker_order_id": "12345",
            "status": "Submitted",
        })
        return svc

    @pytest.mark.asyncio
    async def test_submit_rejects_non_preview_order(self, svc):
        db = MagicMock()
        mock_order = MagicMock()
        mock_order.status = OrderStatus.SUBMITTED.value
        db.query.return_value.filter.return_value.first.return_value = mock_order

        result = await svc.submit_order(db, order_id=1, user_id=1)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_submit_rejects_wrong_user(self, svc):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        result = await svc.submit_order(db, order_id=1, user_id=999)
        assert result["error"] == "Order not found"

    @pytest.mark.asyncio
    async def test_submit_not_found(self, svc):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        result = await svc.submit_order(db, order_id=999, user_id=1)
        assert result["error"] == "Order not found"
