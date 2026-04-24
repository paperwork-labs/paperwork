"""Portfolio ``/portfolio/orders`` list route: query parameters and wiring."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.portfolio.orders import router
from backend.models.user import UserRole

ORDER_MGR_PATH = "backend.api.routes.portfolio.orders._order_manager"


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = 1
    user.email = "test@axiomfolio.com"
    user.role = UserRole.OWNER
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


class TestListOrdersRoute:
    @patch(ORDER_MGR_PATH)
    def test_list_passes_source_all_by_default(self, mock_mgr, client):
        mock_mgr.list_orders.return_value = []
        resp = client.get("/portfolio/orders")
        assert resp.status_code == 200
        mock_mgr.list_orders.assert_called_once()
        assert mock_mgr.list_orders.call_args.kwargs["list_source"] == "all"

    @patch(ORDER_MGR_PATH)
    def test_list_passes_source_app(self, mock_mgr, client):
        mock_mgr.list_orders.return_value = []
        resp = client.get("/portfolio/orders?source=app")
        assert resp.status_code == 200
        assert mock_mgr.list_orders.call_args.kwargs["list_source"] == "app"

    @patch(ORDER_MGR_PATH)
    def test_list_passes_source_broker(self, mock_mgr, client):
        mock_mgr.list_orders.return_value = []
        resp = client.get("/portfolio/orders?source=broker")
        assert resp.status_code == 200
        assert mock_mgr.list_orders.call_args.kwargs["list_source"] == "broker"

    @patch(ORDER_MGR_PATH)
    def test_list_invalid_source_defaults_to_all(self, mock_mgr, client):
        mock_mgr.list_orders.return_value = []
        resp = client.get("/portfolio/orders?source=nope")
        assert resp.status_code == 200
        assert mock_mgr.list_orders.call_args.kwargs["list_source"] == "all"

    @patch(ORDER_MGR_PATH)
    def test_list_passes_limit_and_offset(self, mock_mgr, client):
        mock_mgr.list_orders.return_value = []
        resp = client.get("/portfolio/orders?limit=25&offset=10")
        assert resp.status_code == 200
        kw = mock_mgr.list_orders.call_args.kwargs
        assert kw["limit"] == 25
        assert kw["offset"] == 10

    @patch(ORDER_MGR_PATH)
    def test_list_passes_account_id(self, mock_mgr, client):
        mock_mgr.list_orders.return_value = []
        resp = client.get("/portfolio/orders?account_id=42")
        assert resp.status_code == 200
        assert mock_mgr.list_orders.call_args.kwargs.get("account_id") == 42
