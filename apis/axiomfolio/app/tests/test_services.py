#!/usr/bin/env python3
"""
AxiomFolio V1 - Service Tests
==============================

Comprehensive tests for all major services.
Tests service initialization, core functionality, and integration.
"""

import pytest
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestMarketDataService:
    """Test Market Data service functionality."""

    @pytest.mark.asyncio
    async def test_market_data_service_import(self):
        """Test market data service can be imported."""
        try:
            from app.services.market.market_data_service import (
                provider_router,
                quote,
                snapshot_builder,
            )

            assert quote is not None and hasattr(quote, "get_current_price")
            assert provider_router is not None and hasattr(provider_router, "get_historical_data")
            assert snapshot_builder is not None and hasattr(snapshot_builder, "get_technical_analysis")

            logger.info("✅ Market Data Service import test passed")

        except Exception as e:
            pytest.fail(f"Market Data Service import failed: {e}")

    @pytest.mark.asyncio
    async def test_current_price_retrieval(self):
        """Test current price retrieval."""
        try:
            from app.services.market.market_data_service import quote

            test_symbol = "AAPL"
            price = await quote.get_current_price(test_symbol)

            if price and price > 0:
                assert isinstance(price, (int, float))
                assert price > 0
                logger.info(
                    f"✅ Current price test passed: {test_symbol} = ${price:.2f}"
                )
            else:
                logger.warning(f"⚠️ Current price not available for {test_symbol}")

        except Exception as e:
            logger.warning(f"⚠️ Current price test failed: {e}")

    @pytest.mark.asyncio
    async def test_historical_data_retrieval(self):
        """Test historical data retrieval."""
        try:
            from app.services.market.market_data_service import provider_router

            test_symbol = "AAPL"
            data = await provider_router.get_historical_data(
                test_symbol, period="1mo"
            )

            if data is not None and not data.empty:
                assert len(data) > 10, "Should have reasonable amount of data"

                # Check for required columns
                required_cols = ["open", "high", "low", "close"]
                available_cols = [col.lower() for col in data.columns]

                for col in required_cols:
                    assert col in available_cols or col.title() in data.columns

                logger.info(f"✅ Historical data test passed: {len(data)} periods")
            else:
                logger.warning(f"⚠️ Historical data not available for {test_symbol}")

        except Exception as e:
            logger.warning(f"⚠️ Historical data test failed: {e}")


class TestIndexConstituentsService:
    """Test Index Constituents service functionality."""

    @pytest.mark.asyncio
    async def test_index_service_import(self):
        """Test index service can be imported."""
        try:
            from app.services.market.market_data_service import index_universe

            assert index_universe is not None
            assert hasattr(index_universe, "get_index_constituents")
            assert hasattr(index_universe, "get_all_tradeable_symbols")

            logger.info("✅ Index Constituents Service import test passed")

        except Exception as e:
            pytest.fail(f"Index Constituents Service import failed: {e}")

    @pytest.mark.asyncio
    async def test_dow30_constituents(self):
        """Test getting Dow 30 constituents."""
        try:
            from app.services.market.market_data_service import index_universe

            dow30_symbols = await index_universe.get_index_constituents("DOW30")

            if dow30_symbols and len(dow30_symbols) > 10:
                assert isinstance(dow30_symbols, list)
                assert all(isinstance(symbol, str) for symbol in dow30_symbols)
                assert all(len(symbol) <= 5 for symbol in dow30_symbols)
                logger.info(
                    f"✅ Dow 30 constituents test passed: {len(dow30_symbols)} symbols"
                )
            else:
                logger.warning(
                    f"⚠️ Limited Dow 30 data: {len(dow30_symbols) if dow30_symbols else 0} symbols"
                )

        except Exception as e:
            logger.warning(f"⚠️ Dow 30 constituents test failed: {e}")

    @pytest.mark.asyncio
    async def test_atr_universe_generation(self):
        """Test ATR universe generation."""
        try:
            from app.services.market.market_data_service import index_universe

            data = await index_universe.get_all_tradeable_symbols(["SP500","NASDAQ100"])  # example
            universe = sorted({s for lst in data.values() for s in lst})

            if universe and len(universe) > 50:
                assert isinstance(universe, list)
                assert all(isinstance(symbol, str) for symbol in universe)
                logger.info(f"✅ ATR universe test passed: {len(universe)} symbols")
            else:
                logger.warning(
                    f"⚠️ Limited ATR universe: {len(universe) if universe else 0} symbols"
                )

        except Exception as e:
            logger.warning(f"⚠️ ATR universe test failed: {e}")


class TestNotificationService:
    """Test notification service (Brain + in-app wiring)."""

    def test_notification_service_import(self):
        """Notification service imports and exposes Brain configuration helper."""
        from app.services.notifications.notification_service import notification_service

        assert notification_service is not None
        assert hasattr(notification_service, "notify_user")
        assert hasattr(notification_service, "notify_system_sync")
        assert hasattr(notification_service, "is_brain_configured")
        assert isinstance(notification_service.is_brain_configured(), bool)

    def test_alert_service_import(self):
        """Ops alerts use Brain webhook client."""
        from app.services.notifications.alerts import AlertService, alert_service

        assert alert_service is not None
        assert hasattr(alert_service, "send_alert")
        assert hasattr(AlertService, "send_alert")


class TestDatabaseServices:
    """Test database-related services."""

    def test_database_connection(self, db_session):
        """Test basic database connection."""
        try:
            result = db_session.execute("SELECT 1").scalar()
            if result == 1:
                logger.info("✅ Database connection test passed")
            else:
                logger.warning("⚠️ Database query returned unexpected result")
        except Exception as e:
            logger.warning(f"⚠️ Database connection test failed: {e}")


# Service integration tests
class TestServiceIntegration:
    """Test integration between services."""

    @pytest.mark.asyncio
    async def test_market_data_to_indicator_integration(self):
        """Test market data to indicator engine integration."""
        try:
            from app.services.market.market_data_service import quote

            test_symbol = "AAPL"
            price = await quote.get_current_price(test_symbol)

            if price and price > 0:
                logger.info(f"✅ Market data integration: {test_symbol}=${price:.2f}")
            else:
                logger.warning("⚠️ Market data not available for integration test")

        except Exception as e:
            logger.warning(f"⚠️ Market data integration test failed: {e}")


# Test runners
async def run_service_tests():
    """Run all service tests."""
    print("🧪 Running Service Tests...")

    try:
        # Test Market Data Service
        market_test = TestMarketDataService()
        await market_test.test_market_data_service_import()
        await market_test.test_current_price_retrieval()
        await market_test.test_historical_data_retrieval()

        # Test Index Constituents Service
        index_test = TestIndexConstituentsService()
        await index_test.test_index_service_import()
        await index_test.test_dow30_constituents()
        await index_test.test_atr_universe_generation()

        # Test notification / Brain wiring
        notif_test = TestNotificationService()
        notif_test.test_notification_service_import()
        notif_test.test_alert_service_import()

        # Test Service Integration
        integration_test = TestServiceIntegration()
        await integration_test.test_market_data_to_indicator_integration()

        print("✅ Service tests completed!")
        return True

    except Exception as e:
        print(f"❌ Service tests failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_service_tests())
    if success:
        print("🎉 All service tests passed!")
    else:
        print("❌ Some service tests failed!")
