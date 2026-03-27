"""Tests for portfolio order API routes.

Covers: preview risk rejection (422), submit happy path, list/get orders,
and cancel endpoint.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.api.routes.portfolio.orders import router
from backend.services.execution.risk_gate import RiskViolation

ORDER_MGR_PATH = "backend.api.routes.portfolio.orders._order_manager"


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = 1
    user.email = "test@axiomfolio.com"
    user.role = "admin"
    return user


@pytest.fixture
def app(mock_user):
    from backend.api.dependencies import get_current_user
    from backend.database import get_db

    test_app = FastAPI()
    test_app.include_router(router)

    mock_db = MagicMock()
    test_app.dependency_overrides[get_db] = lambda: mock_db
    test_app.dependency_overrides[get_current_user] = lambda: mock_user

    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestPreviewRoute:
    @patch(ORDER_MGR_PATH)
    def test_preview_returns_422_on_risk_violation(self, mock_mgr, client):
        mock_mgr.preview = AsyncMock(
            side_effect=RiskViolation("Order value $200,000 exceeds $100,000 maximum")
        )
        resp = client.post("/portfolio/orders/preview", json={
            "symbol": "AAPL",
            "side": "buy",
            "order_type": "market",
            "quantity": 1000,
        })
        assert resp.status_code == 422
        assert "exceeds" in resp.json()["detail"]

    @patch(ORDER_MGR_PATH)
    def test_preview_returns_200_on_success(self, mock_mgr, client):
        mock_mgr.preview = AsyncMock(return_value={
            "order_id": 1,
            "status": "preview",
            "preview": {"estimated_commission": 1.0},
            "warnings": [],
        })
        resp = client.post("/portfolio/orders/preview", json={
            "symbol": "AAPL",
            "side": "buy",
            "order_type": "limit",
            "quantity": 10,
            "limit_price": 150.0,
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["order_id"] == 1


class TestSubmitRoute:
    @patch(ORDER_MGR_PATH)
    def test_submit_returns_200(self, mock_mgr, client):
        mock_mgr.submit = AsyncMock(return_value={
            "order_id": 1,
            "status": "submitted",
            "broker_order_id": "12345",
            "error": None,
        })
        resp = client.post("/portfolio/orders/submit", json={"order_id": 1})
        assert resp.status_code == 200

    @patch(ORDER_MGR_PATH)
    def test_submit_returns_403_on_forbidden(self, mock_mgr, client):
        mock_mgr.submit = AsyncMock(return_value={"error": "Forbidden"})
        resp = client.post("/portfolio/orders/submit", json={"order_id": 1})
        assert resp.status_code == 403


class TestListRoute:
    @patch(ORDER_MGR_PATH)
    def test_list_returns_orders(self, mock_mgr, client):
        mock_mgr.list_orders.return_value = [
            {"id": 1, "symbol": "AAPL", "status": "preview"},
        ]
        resp = client.get("/portfolio/orders")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1


class TestGetRoute:
    @patch(ORDER_MGR_PATH)
    def test_get_returns_404_when_missing(self, mock_mgr, client):
        mock_mgr.get_order.return_value = None
        resp = client.get("/portfolio/orders/999")
        assert resp.status_code == 404


class TestCancelRoute:
    @patch(ORDER_MGR_PATH)
    def test_cancel_returns_200(self, mock_mgr, client):
        mock_mgr.cancel = AsyncMock(return_value={
            "order_id": 1,
            "status": "cancelled",
        })
        resp = client.delete("/portfolio/orders/1")
        assert resp.status_code == 200

    @patch(ORDER_MGR_PATH)
    def test_cancel_returns_400_on_invalid_state(self, mock_mgr, client):
        mock_mgr.cancel = AsyncMock(return_value={
            "error": "Cannot cancel order in 'preview' state"
        })
        resp = client.delete("/portfolio/orders/1")
        assert resp.status_code == 400
