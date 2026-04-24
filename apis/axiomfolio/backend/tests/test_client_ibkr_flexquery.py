#!/usr/bin/env python3
"""
Comprehensive Tests for IBKR FlexQuery Client
=============================================

Tests all functionality of the IBKRFlexQueryClient including:
- Connection and authentication
- FlexQuery data parsing
- Tax lots extraction
- Option exercises parsing
- Error handling and retry logic
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from datetime import datetime

from backend.services.clients.ibkr_flexquery_client import IBKRFlexQueryClient


@pytest.mark.no_db
class TestIBKRFlexQueryClient:
    """Test suite for IBKRFlexQueryClient."""

    @pytest.fixture
    def client(self):
        """Create a test client instance."""
        c = IBKRFlexQueryClient()
        # Tests patch the network methods; set dummy credentials so we don't early-return.
        c.token = c.token or "test_token"
        c.query_id = c.query_id or "test_query_id"
        return c

    @pytest.fixture
    def sample_flexquery_xml(self):
        """Sample FlexQuery XML for testing."""
        return """<?xml version="1.0" encoding="UTF-8"?>
        <FlexQueryResponse queryName="Test" type="AF">
            <FlexStatements count="1">
                <FlexStatement accountId="IBKR_TEST_ACCOUNT_A" period="Last365CalendarDays">
                    <AccountInformation>
                        <AccountInformation accountId="IBKR_TEST_ACCOUNT_A" currency="USD" />
                    </AccountInformation>
                    <OpenPositions>
                        <OpenPosition accountId="IBKR_TEST_ACCOUNT_A" symbol="AAPL" position="100" markPrice="150.0" />
                    </OpenPositions>
                    <Trades>
                        <Trade accountId="IBKR_TEST_ACCOUNT_A" symbol="AAPL" quantity="100" tradePrice="149.0" tradeDate="20240115" tradeID="123456" assetCategory="STK" />
                    </Trades>
                    <OptionEAE>
                        <OptionEAE accountId="IBKR_TEST_ACCOUNT_A" symbol="AAPL240315C150" underlyingSymbol="AAPL" putCall="C" strike="150" expiry="20240315" exercisedQuantity="1" />
                    </OptionEAE>
                    <CashTransactions>
                        <CashTransaction accountId="IBKR_TEST_ACCOUNT_A" symbol="AAPL" type="Dividends" amount="50.0" />
                    </CashTransactions>
                    <InterestAccruals>
                        <InterestAccrual accountId="IBKR_TEST_ACCOUNT_A" currency="USD" fromDate="20240101" toDate="20240131" rate="5.5" />
                    </InterestAccruals>
                    <Transfers>
                        <Transfer accountId="IBKR_TEST_ACCOUNT_A" symbol="AAPL" quantity="50" direction="IN" />
                    </Transfers>
                </FlexStatement>
            </FlexStatements>
        </FlexQueryResponse>"""

    def test_client_initialization(self, client):
        """Test that client initializes correctly."""
        assert (
            client.base_url
            == "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"
        )
        assert hasattr(client, "token")
        assert hasattr(client, "query_id")

    def test_client_credentials_fallback(self):
        """Test that client falls back to settings for credentials."""
        with patch(
            "backend.services.clients.ibkr_flexquery_client.settings"
        ) as mock_settings:
            mock_settings.IBKR_FLEX_TOKEN = "test_token"
            mock_settings.IBKR_FLEX_QUERY_ID = "test_query_id"

            client = IBKRFlexQueryClient()
            # Since direct credentials are set, they should take precedence
            assert (
                client.token == "test_token"
            )  # todo: Sankalp has real token 205375653752966209211660

    @pytest.mark.asyncio
    async def test_request_report_success(self, client):
        """Test successful report request."""
        mock_response_xml = """<?xml version="1.0"?>
        <FlexStatementResponse timestamp="15 January, 2024 05:32 PM EST">
            <Status>Success</Status>
            <ReferenceCode>123456789</ReferenceCode>
        </FlexStatementResponse>"""

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value=mock_response_xml)
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await client._request_report()
            assert result == "123456789"

    @pytest.mark.asyncio
    async def test_request_report_failure(self, client):
        """Test failed report request."""
        mock_response_xml = """<?xml version="1.0"?>
        <FlexStatementResponse timestamp="15 January, 2024 05:32 PM EST">
            <Status>Fail</Status>
            <ErrorMessage>Invalid query ID</ErrorMessage>
        </FlexStatementResponse>"""

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value=mock_response_xml)
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await client._request_report()
            assert result is None

    @pytest.mark.asyncio
    async def test_get_report_success(self, client):
        """Test successful report retrieval."""
        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(
                return_value="<FlexQueryResponse>test</FlexQueryResponse>"
            )
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await client._get_report("123456789")
            assert result == "<FlexQueryResponse>test</FlexQueryResponse>"

    @pytest.mark.asyncio
    async def test_get_report_not_ready(self, client):
        """Test report not ready scenario."""
        mock_response_xml = """<?xml version="1.0"?>
        <FlexStatementResponse timestamp="15 January, 2024 05:32 PM EST">
            <Status>Warn</Status>
            <ErrorMessage>Statement generation in progress. Please try again shortly.</ErrorMessage>
        </FlexStatementResponse>"""

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value=mock_response_xml)
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await client._get_report("123456789")
            assert result is None

    def test_parse_tax_lots(self, client, sample_flexquery_xml):
        """Test tax lots parsing from FlexQuery XML."""
        tax_lots = client._parse_tax_lots(sample_flexquery_xml, "IBKR_TEST_ACCOUNT_A")

        assert len(tax_lots) >= 1
        tax_lot = tax_lots[0]
        assert tax_lot["symbol"] == "AAPL"
        assert tax_lot["account_id"] == "IBKR_TEST_ACCOUNT_A"
        assert "quantity" in tax_lot
        assert "cost_basis" in tax_lot
        assert "contract_type" in tax_lot

    def test_parse_option_exercises(self, client, sample_flexquery_xml):
        """Test option exercises parsing from OptionEAE section."""
        exercises = client._parse_option_exercises(
            sample_flexquery_xml, "IBKR_TEST_ACCOUNT_A"
        )

        assert len(exercises) >= 1
        exercise = exercises[0]
        assert exercise["symbol"] == "AAPL240315C150"
        assert exercise["underlying_symbol"] == "AAPL"
        assert exercise["option_type"] == "CALL"
        assert exercise["strike_price"] == 150.0
        assert exercise["exercised_quantity"] == 1

    def test_parse_option_positions(self, client, sample_flexquery_xml):
        """Test option positions parsing from OpenPositions section."""
        positions = client._parse_option_positions(
            sample_flexquery_xml, "IBKR_TEST_ACCOUNT_A"
        )

        # This sample doesn't have options in OpenPositions, so should be empty
        assert len(positions) == 0

    def test_parse_flexquery_date(self, client):
        """Test FlexQuery date parsing."""
        # Test various date formats
        assert client._parse_flexquery_date("20240115") == datetime(2024, 1, 15)
        assert client._parse_flexquery_date("2024-01-15") == datetime(2024, 1, 15)
        assert client._parse_flexquery_date("") is None
        assert client._parse_flexquery_date(None) is None
        assert client._parse_flexquery_date("invalid") is None

    @pytest.mark.asyncio
    async def test_get_official_tax_lots_no_credentials(self):
        """Test behavior when credentials are not configured."""
        client = IBKRFlexQueryClient()
        client.token = None
        client.query_id = None

        result = await client.get_official_tax_lots("IBKR_TEST_ACCOUNT_A")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_official_tax_lots_success(self, client, sample_flexquery_xml):
        """Test successful tax lots retrieval."""
        with (
            patch.object(client, "_request_report", return_value="123456789"),
            patch.object(client, "_get_report", return_value=sample_flexquery_xml),
            patch("asyncio.sleep"),
        ):

            result = await client.get_official_tax_lots("IBKR_TEST_ACCOUNT_A")
            assert len(result) >= 1
            assert result[0]["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_get_historical_option_exercises_success(
        self, client, sample_flexquery_xml
    ):
        """Test successful option exercises retrieval."""
        with (
            patch.object(client, "_request_report", return_value="123456789"),
            patch.object(client, "_get_report", return_value=sample_flexquery_xml),
            patch("asyncio.sleep"),
        ):

            result = await client.get_historical_option_exercises("IBKR_TEST_ACCOUNT_A")
            assert len(result) >= 1
            assert result[0]["symbol"] == "AAPL240315C150"

    def test_get_setup_instructions(self, client):
        """Test setup instructions are provided."""
        instructions = client.get_setup_instructions()

        assert isinstance(instructions, dict)
        assert "step_1" in instructions
        assert "step_2" in instructions
        assert "note" in instructions
        assert "FlexQuery" in instructions["note"]

    @pytest.mark.asyncio
    async def test_error_handling_network_failure(self, client):
        """Test error handling for network failures."""
        with patch("aiohttp.ClientSession.get", side_effect=Exception("Network error")):
            result = await client._request_report()
            assert result is None

    def test_xml_parsing_robustness(self, client):
        """Test XML parsing handles malformed XML gracefully."""
        malformed_xml = "<invalid>xml<structure>"

        result = client._parse_tax_lots(malformed_xml, "IBKR_TEST_ACCOUNT_A")
        assert result == []

        result = client._parse_option_exercises(malformed_xml, "IBKR_TEST_ACCOUNT_A")
        assert result == []

    def test_account_filtering(self, client):
        """Test that parsing correctly filters by account ID."""
        multi_account_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <FlexQueryResponse>
            <FlexStatements>
                <FlexStatement accountId="IBKR_TEST_ACCOUNT_A">
                    <Trades>
                        <Trade accountId="IBKR_TEST_ACCOUNT_A" symbol="AAPL" quantity="100" tradePrice="149.0" tradeDate="20240115" tradeID="123456" assetCategory="STK" />
                        <Trade accountId="IBKR_TEST_ACCOUNT_B" symbol="MSFT" quantity="50" tradePrice="250.0" tradeDate="20240115" tradeID="123457" assetCategory="STK" />
                    </Trades>
                </FlexStatement>
            </FlexStatements>
        </FlexQueryResponse>"""

        # Should only return trades for the specified account
        tax_lots = client._parse_tax_lots(multi_account_xml, "IBKR_TEST_ACCOUNT_A")
        assert len(tax_lots) >= 1
        for lot in tax_lots:
            assert lot["account_id"] == "IBKR_TEST_ACCOUNT_A"
            assert lot["symbol"] == "AAPL"  # Should not include MSFT from other account


class TestIBKRFlexQueryClientIntegration:
    """Integration tests for IBKR FlexQuery client (require real credentials)."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_flexquery_connection(self):
        """Test real FlexQuery connection (requires valid credentials)."""
        client = IBKRFlexQueryClient()

        if not client.token or not client.query_id:
            pytest.skip("FlexQuery credentials not configured")

        # Test report request
        reference_code = await client._request_report()
        assert reference_code is not None
        assert len(reference_code) > 0

        # Wait and test report retrieval
        await asyncio.sleep(10)
        report_data = await client._get_report(reference_code)
        assert report_data is not None
        assert "<FlexQueryResponse" in report_data

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_tax_lots_retrieval(self):
        """Test real tax lots retrieval (requires valid credentials and data)."""
        client = IBKRFlexQueryClient()

        if not client.token or not client.query_id:
            pytest.skip("FlexQuery credentials not configured")

        tax_lots = await client.get_official_tax_lots("IBKR_TEST_ACCOUNT_A")

        # Should return list (may be empty if no positions)
        assert isinstance(tax_lots, list)

        if tax_lots:
            # If we have tax lots, verify structure
            lot = tax_lots[0]
            required_fields = ["symbol", "account_id", "quantity", "cost_basis"]
            for field in required_fields:
                assert field in lot, f"Missing required field: {field}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
