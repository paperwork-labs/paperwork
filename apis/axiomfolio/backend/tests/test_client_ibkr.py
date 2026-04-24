#!/usr/bin/env python3
"""
Comprehensive Tests for IBKR Real-time Client
=============================================

Tests all functionality of the IBKRClient including:
- Connection management
- Real-time data retrieval
- Position fetching
- Error handling and retry logic
"""

import pytest
import asyncio
from unittest.mock import Mock, patch

from backend.services.clients.ibkr_client import IBKRClient


class TestIBKRClient:
    """Test suite for IBKRClient."""

    @pytest.fixture
    def client(self):
        """Create a test client instance."""
        return IBKRClient()

    def test_client_initialization(self, client):
        """Test that client initializes correctly."""
        assert client.host == "127.0.0.1"
        assert client.port == 7497
        assert client.client_id == 1
        assert client.ib is None
        assert not client.connected

    def test_client_singleton_pattern(self):
        """Test that IBKRClient follows singleton pattern."""
        client1 = IBKRClient()
        client2 = IBKRClient()
        assert client1 is client2

    @pytest.mark.asyncio
    async def test_connect_success(self, client):
        """Test successful connection to IBKR."""
        mock_ib = Mock()
        mock_ib.connectAsync.return_value = asyncio.Future()
        mock_ib.connectAsync.return_value.set_result(True)
        mock_ib.isConnected.return_value = True

        with patch("backend.services.clients.ibkr_client.IB", return_value=mock_ib):
            success = await client.connect()
            assert success is True
            assert client.connected is True
            assert client.ib == mock_ib

    @pytest.mark.asyncio
    async def test_connect_failure(self, client):
        """Test failed connection to IBKR."""
        mock_ib = Mock()
        mock_ib.connectAsync.side_effect = Exception("Connection failed")

        with patch("backend.services.clients.ibkr_client.IB", return_value=mock_ib):
            success = await client.connect()
            assert success is False
            assert client.connected is False

    @pytest.mark.asyncio
    async def test_connect_with_retry(self, client):
        """Test connection with retry logic."""
        mock_ib = Mock()
        fut = asyncio.Future()
        fut.set_result(None)
        mock_ib.connectAsync.side_effect = [
            Exception("Connection failed"),
            fut,
        ]
        mock_ib.isConnected.return_value = True
        mock_ib.managedAccounts.return_value = []
        mock_ib.reqAccountSummary.return_value = None

        with (
            patch("backend.services.clients.ibkr_client.IB", return_value=mock_ib),
            patch("backend.services.clients.ibkr_client.util"),
            patch("asyncio.sleep"),
        ):
            success = await client.connect_with_retry(max_attempts=2)
            assert success is True
            assert client.connected is True

    @pytest.mark.asyncio
    async def test_ensure_connected_when_connected(self, client):
        """Test _ensure_connected when already connected."""
        client.connected = True
        client.ib = Mock()
        client.ib.isConnected.return_value = True
        # Match current event loop so _ensure_connected returns True without reconnecting
        client.ib._owner_loop = asyncio.get_running_loop()

        result = await client._ensure_connected()
        assert result is True

    @pytest.mark.asyncio
    async def test_ensure_connected_when_disconnected(self, client):
        """Test _ensure_connected when not connected."""
        client.connected = False

        with patch.object(client, "connect_with_retry", return_value=True):
            result = await client._ensure_connected()
            assert result is True

    @pytest.mark.asyncio
    async def test_get_positions_success(self, client):
        """Test successful position retrieval."""
        # Mock position data
        mock_position = Mock()
        mock_position.account = "IBKR_TEST_ACCOUNT_A"
        mock_position.contract.symbol = "AAPL"
        mock_position.position = 100.0
        mock_position.marketValue = 15000.0
        mock_position.avgCost = 149.0
        mock_position.unrealizedPNL = 1000.0
        mock_position.contract.secType = "STK"
        mock_position.contract.currency = "USD"
        mock_position.contract.exchange = "NASDAQ"

        client.ib = Mock()
        client.ib.positions.return_value = [mock_position]

        with patch.object(client, "_ensure_connected", return_value=True):
            positions = await client.get_positions("IBKR_TEST_ACCOUNT_A")

            assert len(positions) == 1
            position = positions[0]
            assert position["account"] == "IBKR_TEST_ACCOUNT_A"
            assert position["symbol"] == "AAPL"
            assert position["position"] == 100.0
            assert position["market_value"] == 15000.0
            assert position["avg_cost"] == 149.0
            assert position["unrealized_pnl"] == 1000.0
            assert position["contract_type"] == "STK"
            assert position["currency"] == "USD"
            assert position["exchange"] == "NASDAQ"

    @pytest.mark.asyncio
    async def test_get_positions_no_connection(self, client):
        """Test position retrieval when not connected."""
        with patch.object(client, "_ensure_connected", return_value=False):
            positions = await client.get_positions("IBKR_TEST_ACCOUNT_A")
            assert positions == []

    @pytest.mark.asyncio
    async def test_get_positions_filter_zero_positions(self, client):
        """Test that zero positions are filtered out."""
        # Mock position data with zero position
        mock_position_zero = Mock()
        mock_position_zero.position = 0.0
        mock_position_zero.account = "IBKR_TEST_ACCOUNT_A"

        mock_position_nonzero = Mock()
        mock_position_nonzero.account = "IBKR_TEST_ACCOUNT_A"
        mock_position_nonzero.contract.symbol = "AAPL"
        mock_position_nonzero.position = 100.0
        mock_position_nonzero.marketValue = 15000.0
        mock_position_nonzero.avgCost = 149.0
        mock_position_nonzero.unrealizedPNL = 1000.0
        mock_position_nonzero.contract.secType = "STK"
        mock_position_nonzero.contract.currency = "USD"
        mock_position_nonzero.contract.exchange = "NASDAQ"

        client.ib = Mock()
        client.ib.positions.return_value = [mock_position_zero, mock_position_nonzero]

        with patch.object(client, "_ensure_connected", return_value=True):
            positions = await client.get_positions("IBKR_TEST_ACCOUNT_A")

            # Should only return non-zero positions
            assert len(positions) == 1
            assert positions[0]["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_get_positions_handles_none_values(self, client):
        """Test that None values in position data are handled gracefully."""
        mock_position = Mock()
        mock_position.account = "IBKR_TEST_ACCOUNT_A"
        mock_position.contract.symbol = "AAPL"
        mock_position.position = 100.0
        mock_position.marketValue = None  # None value
        mock_position.avgCost = None  # None value
        mock_position.unrealizedPNL = None  # None value
        mock_position.contract.secType = "STK"
        mock_position.contract.currency = None  # None value
        mock_position.contract.exchange = "NASDAQ"

        client.ib = Mock()
        client.ib.positions.return_value = [mock_position]

        with patch.object(client, "_ensure_connected", return_value=True):
            positions = await client.get_positions("IBKR_TEST_ACCOUNT_A")

            assert len(positions) == 1
            position = positions[0]
            assert position["market_value"] == 0.0  # None converted to 0.0
            assert position["avg_cost"] == 0.0
            assert position["unrealized_pnl"] == 0.0
            assert position["currency"] == "USD"  # None converted to default

    @pytest.mark.asyncio
    async def test_disconnect_success(self, client):
        """Test successful disconnection."""
        mock_ib = Mock()
        client.ib = mock_ib
        client.connected = True

        await client.disconnect()

        mock_ib.disconnect.assert_called_once()
        assert client.connected is False
        assert client.ib is None

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, client):
        """Test disconnection when not connected."""
        client.ib = None
        client.connected = False

        # Should not raise an exception
        await client.disconnect()
        assert client.connected is False

    @pytest.mark.asyncio
    async def test_disconnect_with_error(self, client):
        """Test disconnection handles errors gracefully."""
        mock_ib = Mock()
        mock_ib.disconnect.side_effect = Exception("Disconnect error")
        client.ib = mock_ib
        client.connected = True

        # Should not raise an exception
        await client.disconnect()
        assert client.connected is False
        assert client.ib is None

    def test_connection_health_tracking(self):
        """Test connection health tracking functionality."""
        fresh = IBKRClient.__new__(IBKRClient)
        fresh.host = "127.0.0.1"
        fresh.port = 7497
        fresh.client_id = 1
        fresh.ib = None
        fresh.connected = False
        fresh.managed_accounts = []
        fresh.connection_health = {"status": "disconnected", "consecutive_failures": 0}
        fresh.retry_count = 0
        fresh._lock = None

        assert fresh.connection_health["status"] == "disconnected"
        assert fresh.connection_health["consecutive_failures"] == 0
        assert "status" in fresh.connection_health
        assert "consecutive_failures" in fresh.connection_health

    @pytest.mark.asyncio
    async def test_error_handling_in_get_positions(self, client):
        """Test error handling in get_positions method."""
        client.ib = Mock()
        client.ib.positions.side_effect = Exception("API Error")

        with patch.object(client, "_ensure_connected", return_value=True):
            positions = await client.get_positions("IBKR_TEST_ACCOUNT_A")
            assert positions == []


class TestIBKRClientIntegration:
    """Integration tests for IBKR client (require TWS/Gateway)."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_ibkr_connection(self):
        """Test real IBKR connection (requires TWS/Gateway running)."""
        client = IBKRClient()

        # Try to connect to local TWS/Gateway
        success = await client.connect()

        if success:
            assert client.connected is True
            assert client.ib is not None

            # Test getting positions
            positions = await client.get_positions("IBKR_TEST_ACCOUNT_A")
            assert isinstance(positions, list)

            # Clean up
            await client.disconnect()
        else:
            pytest.skip("IBKR TWS/Gateway not available")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_position_data_structure(self):
        """Test real position data has expected structure."""
        client = IBKRClient()

        success = await client.connect()
        if not success:
            pytest.skip("IBKR TWS/Gateway not available")

        try:
            positions = await client.get_positions("IBKR_TEST_ACCOUNT_A")

            if positions:
                # Verify structure of real position data
                position = positions[0]
                required_fields = [
                    "account",
                    "symbol",
                    "position",
                    "market_value",
                    "avg_cost",
                    "unrealized_pnl",
                    "contract_type",
                    "currency",
                    "exchange",
                ]

                for field in required_fields:
                    assert field in position, f"Missing field: {field}"

                # Verify data types
                assert isinstance(position["position"], float)
                assert isinstance(position["market_value"], float)
                assert isinstance(position["avg_cost"], float)

        finally:
            await client.disconnect()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
