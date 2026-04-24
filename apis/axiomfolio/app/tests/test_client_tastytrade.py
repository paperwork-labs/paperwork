"""
Tests for TastyTrade Client (OAuth / SDK v12+)
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

try:
    from app.services.clients.tastytrade_client import (
        TASTYTRADE_AVAILABLE,
        TastyTradeClient,
    )
except ImportError:
    TASTYTRADE_AVAILABLE = False


class TestTastyTradeClient:
    @pytest.fixture
    def client(self):
        if not TASTYTRADE_AVAILABLE:
            pytest.skip("TastyTrade SDK not available")
        return TastyTradeClient()

    def test_client_initialization(self, client):
        assert client.session is None
        assert client.accounts == []
        assert not client.connected
        assert client.max_retries == 3
        assert client.base_retry_delay == 2
        assert client.connection_health["status"] == "disconnected"

    def test_client_instances_are_independent(self):
        if not TASTYTRADE_AVAILABLE:
            pytest.skip("TastyTrade SDK not available")
        client1 = TastyTradeClient()
        client2 = TastyTradeClient()
        assert client1 is not client2
        client1.connected = True
        assert client2.connected is False

    @pytest.mark.asyncio
    async def test_connect_success(self, client):
        mock_session = Mock()
        mock_account = Mock()
        mock_account.account_number = "TT_DEMO_ACCOUNT"
        mock_account.nickname = "Test Account"
        mock_account.account_type_name = "Individual"

        with (
            patch(
                "app.services.clients.tastytrade_client.Session",
                return_value=mock_session,
            ),
            patch(
                "app.services.clients.tastytrade_client.Account.get",
                new_callable=AsyncMock,
                return_value=[mock_account],
            ),
            patch.object(client, "_verify_connection", new_callable=AsyncMock, return_value=True),
            patch("app.services.clients.tastytrade_client.settings") as mock_settings,
        ):
            mock_settings.TASTYTRADE_CLIENT_SECRET = "test_secret"
            mock_settings.TASTYTRADE_REFRESH_TOKEN = "test_refresh"
            mock_settings.TASTYTRADE_IS_TEST = True

            success = await client.connect_with_retry()

            assert success is True
            assert client.connected is True
            assert client.session == mock_session
            assert len(client.accounts) == 1
            assert client.accounts[0].account_number == "TT_DEMO_ACCOUNT"

    @pytest.mark.asyncio
    async def test_connect_no_credentials(self, client):
        with patch("app.services.clients.tastytrade_client.settings") as mock_settings:
            mock_settings.TASTYTRADE_CLIENT_SECRET = None
            mock_settings.TASTYTRADE_REFRESH_TOKEN = None

            success = await client.connect_with_retry()
            assert success is False

    @pytest.mark.asyncio
    async def test_connect_with_retry_logic(self, client):
        mock_session = Mock()

        with (
            patch("app.services.clients.tastytrade_client.Session") as mock_session_class,
            patch(
                "app.services.clients.tastytrade_client.Account.get",
                new_callable=AsyncMock,
            ) as mock_account_get,
            patch.object(client, "_verify_connection", new_callable=AsyncMock, return_value=True),
            patch("app.services.clients.tastytrade_client.settings") as mock_settings,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_settings.TASTYTRADE_CLIENT_SECRET = "test_secret"
            mock_settings.TASTYTRADE_REFRESH_TOKEN = "test_refresh"
            mock_settings.TASTYTRADE_IS_TEST = True

            mock_account = Mock()
            mock_account.account_number = "TT_DEMO_ACCOUNT"

            mock_session_class.side_effect = [
                Exception("Connection failed"),
                mock_session,
            ]
            mock_account_get.return_value = [mock_account]

            success = await client.connect_with_retry(max_attempts=2)
            assert success is True
            assert client.retry_count == 0

    @pytest.mark.asyncio
    async def test_disconnect(self, client):
        client.session = Mock()
        client.connected = True
        client.accounts = [Mock()]

        await client.disconnect()

        assert client.session is None
        assert client.connected is False
        assert client.accounts == []
        assert client.connection_health["status"] == "disconnected"

    @pytest.mark.asyncio
    async def test_get_accounts_success(self, client):
        mock_account1 = Mock()
        mock_account1.account_number = "TT_DEMO_ACCOUNT"
        mock_account1.nickname = "Primary"
        mock_account1.account_type_name = "Individual"
        mock_account1.is_closed = False

        mock_account2 = Mock()
        mock_account2.account_number = "TT_DEMO_ACCOUNT_2"
        mock_account2.nickname = "IRA"
        mock_account2.account_type_name = "Traditional IRA"
        mock_account2.is_closed = False

        client.connected = True
        client.accounts = [mock_account1, mock_account2]

        accounts = await client.get_accounts()

        assert len(accounts) == 2
        assert accounts[0]["account_number"] == "TT_DEMO_ACCOUNT"
        assert accounts[0]["nickname"] == "Primary"
        assert accounts[0]["account_type"] == "Individual"
        assert accounts[1]["account_number"] == "TT_DEMO_ACCOUNT_2"

    @pytest.mark.asyncio
    async def test_get_accounts_not_connected(self, client):
        client.connected = False
        accounts = await client.get_accounts()
        assert accounts == []

    @pytest.mark.asyncio
    async def test_get_current_positions_success(self, client):
        mock_account = Mock()
        mock_account.account_number = "TT_DEMO_ACCOUNT"

        mock_position = Mock()
        mock_position.symbol = "AAPL"
        mock_position.instrument_type = "Equity"
        mock_position.quantity = 100.0
        mock_position.quantity_direction = "Long"
        mock_position.close_price = 150.0
        mock_position.average_open_price = 149.0
        mock_position.average_yearly_market_close_price = 148.0
        mock_position.average_daily_market_close_price = 151.0
        mock_position.multiplier = 1.0
        mock_position.cost_effect = "Debit"
        mock_position.is_suppressed = False
        mock_position.is_frozen = False
        mock_position.realized_day_gain = 100.0
        mock_position.realized_day_gain_effect = "Credit"
        mock_position.realized_day_gain_date = "2024-01-15"
        mock_position.realized_today = 50.0
        mock_position.created_at = datetime.now()
        mock_position.updated_at = datetime.now()
        mock_position.mark = 150.5
        mock_position.mark_value = 15050.0
        mock_position.restricted_quantity = 0.0
        mock_position.expired_quantity = 0.0
        mock_position.expiring_quantity = 0.0
        mock_position.right_quantity = 0.0
        mock_position.pending_quantity = 0.0
        mock_position.underlying_symbol = ""
        mock_position.product_code = "AAPL"
        mock_position.exchange = "NASDAQ"
        mock_position.listed_market = "NASDAQ"
        mock_position.description = "Apple Inc."
        mock_position.is_closing_only = False
        mock_position.active = True

        mock_account.get_positions = AsyncMock(return_value=[mock_position])

        client.connected = True
        client.accounts = [mock_account]

        positions = await client.get_current_positions("TT_DEMO_ACCOUNT")

        assert len(positions) == 1
        position = positions[0]
        assert position["symbol"] == "AAPL"
        assert position["instrument_type"] == "Equity"
        assert position["quantity"] == 100.0
        assert position["mark_value"] == 15050.0
        assert position["account_number"] == "TT_DEMO_ACCOUNT"

    @pytest.mark.asyncio
    async def test_get_current_positions_options(self, client):
        mock_account = Mock()
        mock_account.account_number = "TT_DEMO_ACCOUNT"

        mock_option_position = Mock()
        mock_option_position.symbol = "AAPL 240315C150"
        mock_option_position.instrument_type = "Equity Option"
        mock_option_position.quantity = 5.0
        mock_option_position.quantity_direction = "Long"
        mock_option_position.close_price = 2.50
        mock_option_position.average_open_price = 2.00
        mock_option_position.average_yearly_market_close_price = 2.25
        mock_option_position.average_daily_market_close_price = 2.60
        mock_option_position.multiplier = 100.0
        mock_option_position.cost_effect = "Debit"
        mock_option_position.is_suppressed = False
        mock_option_position.is_frozen = False
        mock_option_position.realized_day_gain = 250.0
        mock_option_position.realized_day_gain_effect = "Credit"
        mock_option_position.realized_day_gain_date = "2024-01-15"
        mock_option_position.realized_today = 125.0
        mock_option_position.created_at = datetime.now()
        mock_option_position.updated_at = datetime.now()
        mock_option_position.mark = 2.75
        mock_option_position.mark_value = 1375.0
        mock_option_position.restricted_quantity = 0.0
        mock_option_position.expired_quantity = 0.0
        mock_option_position.expiring_quantity = 0.0
        mock_option_position.right_quantity = 0.0
        mock_option_position.pending_quantity = 0.0
        mock_option_position.underlying_symbol = "AAPL"
        mock_option_position.option_type = "C"
        mock_option_position.strike_price = 150.0
        mock_option_position.expiration_date = "2024-03-15"
        mock_option_position.days_to_expiration = 60
        mock_option_position.delta = 0.75
        mock_option_position.gamma = 0.05
        mock_option_position.theta = -0.02
        mock_option_position.vega = 0.25

        mock_account.get_positions = AsyncMock(return_value=[mock_option_position])

        client.connected = True
        client.accounts = [mock_account]

        positions = await client.get_current_positions("TT_DEMO_ACCOUNT")

        assert len(positions) == 1
        position = positions[0]
        assert position["symbol"] == "AAPL 240315C150"
        assert position["instrument_type"] == "Equity Option"
        assert position["option_type"] == "C"
        assert position["strike_price"] == 150.0
        assert position["delta"] == 0.75

    @pytest.mark.asyncio
    async def test_get_current_positions_account_not_found(self, client):
        client.connected = True
        client.accounts = []
        positions = await client.get_current_positions("NONEXISTENT")
        assert positions == []

    @pytest.mark.asyncio
    async def test_get_current_positions_not_connected(self, client):
        client.connected = False
        positions = await client.get_current_positions("TT_DEMO_ACCOUNT")
        assert positions == []

    @pytest.mark.asyncio
    async def test_get_transaction_history_success(self, client):
        mock_account = Mock()
        mock_account.account_number = "TT_DEMO_ACCOUNT"

        mock_transaction = Mock()
        mock_transaction.id = "TXN123456"
        mock_transaction.symbol = "AAPL"
        mock_transaction.action = "Buy to Open"
        mock_transaction.quantity = 100.0
        mock_transaction.price = 149.0
        mock_transaction.commission = 1.0

        mock_account.get_history = AsyncMock(return_value=[mock_transaction])

        client.connected = True
        client.accounts = [mock_account]

        transactions = await client.get_transaction_history("TT_DEMO_ACCOUNT", days=30)

        assert len(transactions) == 1
        assert transactions[0]["id"] == "TXN123456"
        assert transactions[0]["account_number"] == "TT_DEMO_ACCOUNT"
        assert transactions[0]["symbol"] == "AAPL"
        assert transactions[0]["quantity"] == 100.0

    @pytest.mark.asyncio
    async def test_get_transaction_history_not_connected(self, client):
        client.connected = False
        transactions = await client.get_transaction_history("TT_DEMO_ACCOUNT")
        assert transactions == []

    @pytest.mark.asyncio
    async def test_error_handling_in_positions(self, client):
        mock_account = Mock()
        mock_account.account_number = "TT_DEMO_ACCOUNT"
        mock_account.get_positions = AsyncMock(side_effect=Exception("API Error"))

        client.connected = True
        client.accounts = [mock_account]

        positions = await client.get_current_positions("TT_DEMO_ACCOUNT")
        assert positions == []

    @pytest.mark.asyncio
    async def test_error_handling_in_transactions(self, client):
        mock_account = Mock()
        mock_account.account_number = "TT_DEMO_ACCOUNT"
        mock_account.get_history = AsyncMock(side_effect=Exception("API Error"))

        client.connected = True
        client.accounts = [mock_account]

        transactions = await client.get_transaction_history("TT_DEMO_ACCOUNT")
        assert transactions == []

    @pytest.mark.asyncio
    async def test_connect_with_credentials(self, client):
        mock_session = Mock()
        mock_account = Mock()
        mock_account.account_number = "TT_OAUTH_ACCOUNT"

        with (
            patch(
                "app.services.clients.tastytrade_client.Session",
                return_value=mock_session,
            ),
            patch(
                "app.services.clients.tastytrade_client.Account.get",
                new_callable=AsyncMock,
                return_value=[mock_account],
            ),
        ):
            success = await client.connect_with_credentials(
                client_secret="secret123", refresh_token="refresh456"
            )
            assert success is True
            assert client.connected is True
            assert client.session == mock_session

    @pytest.mark.asyncio
    async def test_get_account_balances(self, client):
        mock_account = Mock()
        mock_account.account_number = "TT_DEMO_ACCOUNT"

        mock_bal = Mock()
        mock_bal.cash_balance = 10000.0
        mock_bal.net_liquidating_value = 50000.0
        mock_bal.long_margineable_value = 20000.0
        mock_bal.short_margineable_value = 5000.0
        mock_bal.equity_buying_power = 40000.0
        mock_bal.derivative_buying_power = 30000.0
        mock_bal.day_trading_buying_power = 100000.0
        mock_bal.maintenance_requirement = 15000.0
        mock_bal.margin_equity = 45000.0

        mock_account.get_balances = AsyncMock(return_value=mock_bal)

        client.connected = True
        client.accounts = [mock_account]

        balances = await client.get_account_balances("TT_DEMO_ACCOUNT")
        assert balances["cash_balance"] == 10000.0
        assert balances["net_liquidating_value"] == 50000.0
        assert balances["equity_buying_power"] == 40000.0


class TestTastyTradeClientIntegration:
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_tastytrade_connection(self):
        if not TASTYTRADE_AVAILABLE:
            pytest.skip("TastyTrade SDK not available")

        client = TastyTradeClient()
        success = await client.connect_with_retry()

        if success:
            assert client.connected is True
            assert client.session is not None
            assert len(client.accounts) > 0

            accounts = await client.get_accounts()
            assert isinstance(accounts, list)
            assert len(accounts) > 0

            first_account = accounts[0]
            positions = await client.get_current_positions(first_account["account_number"])
            assert isinstance(positions, list)

            await client.disconnect()
        else:
            pytest.skip("TastyTrade credentials not configured or invalid")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
