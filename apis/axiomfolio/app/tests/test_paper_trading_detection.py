"""Tests for IBKRClient._is_paper_trading() paper/live detection.

Covers: IBKR_TRADING_MODE config, port-based fallback, and interaction
between the two mechanisms.
"""

from unittest.mock import patch

import pytest

from app.services.clients.ibkr_client import IBKRClient


@pytest.fixture
def fresh_client():
    """Create a fresh (non-singleton) IBKRClient for isolated testing."""
    IBKRClient._instance = None
    client = IBKRClient.__new__(IBKRClient)
    client.host = "127.0.0.1"
    client.port = 7497
    client.client_id = 1
    client.ib = None
    client.connected = False
    yield client
    IBKRClient._instance = None


class TestPaperTradingDetection:
    """Verify _is_paper_trading() returns correct results for all combinations."""

    @pytest.mark.parametrize(
        "mode,expected",
        [
            ("paper", True),
            ("PAPER", True),
            ("Paper", True),
            ("live", False),
            ("LIVE", False),
            ("Live", False),
        ],
    )
    def test_explicit_mode_overrides_port(self, fresh_client, mode, expected):
        with patch("app.services.clients.ibkr_client.settings") as mock_settings:
            mock_settings.IBKR_TRADING_MODE = mode
            mock_settings.IBKR_PORT = 7497
            assert fresh_client._is_paper_trading() is expected

    @pytest.mark.parametrize(
        "port,expected",
        [
            (7497, True),  # TWS Paper
            (4002, True),  # Gateway Paper
            (7496, False),  # TWS Live
            (4001, False),  # Gateway Live
            (8888, False),  # extrange unified - ambiguous, should default to not-paper
        ],
    )
    def test_port_fallback_when_no_mode_set(self, fresh_client, port, expected):
        with patch("app.services.clients.ibkr_client.settings") as mock_settings:
            mock_settings.IBKR_TRADING_MODE = ""
            mock_settings.IBKR_PORT = port
            fresh_client.port = port
            assert fresh_client._is_paper_trading() is expected

    def test_mode_paper_overrides_live_port(self, fresh_client):
        with patch("app.services.clients.ibkr_client.settings") as mock_settings:
            mock_settings.IBKR_TRADING_MODE = "paper"
            fresh_client.port = 4001  # Gateway Live port
            assert fresh_client._is_paper_trading() is True

    def test_mode_live_overrides_paper_port(self, fresh_client):
        with patch("app.services.clients.ibkr_client.settings") as mock_settings:
            mock_settings.IBKR_TRADING_MODE = "live"
            fresh_client.port = 7497  # TWS Paper port
            assert fresh_client._is_paper_trading() is False

    def test_no_mode_no_instance_port_uses_settings_port(self, fresh_client):
        with patch("app.services.clients.ibkr_client.settings") as mock_settings:
            mock_settings.IBKR_TRADING_MODE = ""
            mock_settings.IBKR_PORT = 4002
            fresh_client.port = None
            assert fresh_client._is_paper_trading() is True
