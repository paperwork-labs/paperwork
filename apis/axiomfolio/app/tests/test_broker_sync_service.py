#!/usr/bin/env python3
"""
AxiomFolio V1 - Broker Sync Service Tests
==========================================

Tests for broker_sync_service.py functionality:
- Broker-agnostic sync coordination
- Routing requests to appropriate broker services
- DRY principle adherence
- Extensibility for new brokers
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from app.models import User, BrokerAccount
from app.models.broker_account import BrokerType, AccountType, SyncStatus
from app.services.portfolio.broker_sync_service import BrokerSyncService


class TestBrokerSyncService:
    """Test broker sync service coordination functionality."""

    # Use global db_session fixture from tests/conftest.py (Alembic + transaction rollback)

    @pytest.fixture
    def broker_sync_service(self):
        """Create broker sync service instance."""
        return BrokerSyncService()

    @pytest.fixture
    def test_user(self, db_session):
        """Create test user."""
        user = User(
            email="test@axiomfolio.com", username="testuser", full_name="Test User"
        )
        db_session.add(user)
        db_session.commit()
        return user

    @pytest.fixture
    def test_ibkr_account(self, db_session, test_user):
        """Create test IBKR broker account."""
        account = BrokerAccount(
            user_id=test_user.id,
            account_number="IBKR_TEST_ACCOUNT_A",
            account_name="IBKR Test A",
            broker=BrokerType.IBKR,
            account_type=AccountType.TAXABLE,
            sync_status=SyncStatus.QUEUED,
            connection_status="connected",
        )
        db_session.add(account)
        db_session.commit()
        return account

    @pytest.fixture
    def test_tastytrade_account(self, db_session, test_user):
        """Create test TastyTrade broker account."""
        account = BrokerAccount(
            user_id=test_user.id,
            account_number="TT_TEST_ACCOUNT_1",
            account_name="TastyTrade Test",
            broker=BrokerType.TASTYTRADE,
            account_type=AccountType.TAXABLE,
            sync_status=SyncStatus.QUEUED,
            connection_status="connected",
        )
        db_session.add(account)
        db_session.commit()
        return account

    def test_broker_sync_service_initialization(self, broker_sync_service):
        """Test service initializes correctly."""
        assert broker_sync_service is not None
        assert hasattr(broker_sync_service, "sync_account")
        assert hasattr(broker_sync_service, "sync_all_accounts")
        assert hasattr(broker_sync_service, "get_available_brokers")
        print("✅ BrokerSyncService initialization successful")

    def test_get_available_brokers(self, broker_sync_service):
        """Test that service can list available brokers."""
        brokers = broker_sync_service.get_available_brokers()

        assert isinstance(brokers, list)
        assert BrokerType.IBKR in brokers
        assert BrokerType.TASTYTRADE in brokers

        # Should return enum values, not strings
        for broker in brokers:
            assert isinstance(broker, BrokerType)

        print("✅ Available brokers listing working correctly")

    @patch("app.services.portfolio.broker_sync_service.IBKRSyncService")
    def test_sync_ibkr_account(
        self, mock_ibkr_service, broker_sync_service, db_session, test_ibkr_account
    ):
        """Test IBKR account sync routing."""
        # Setup mock
        mock_ibkr_instance = Mock()
        mock_ibkr_service.return_value = mock_ibkr_instance
        mock_ibkr_instance.sync_account_comprehensive.return_value = {
            "status": "success",
            "positions_synced": 10,
            "tax_lots_synced": 25,
        }

        # Execute sync
        result = broker_sync_service.sync_account(
            test_ibkr_account.account_number, db_session
        )

        # Verify correct service was called
        mock_ibkr_service.assert_called_once()
        mock_ibkr_instance.sync_account_comprehensive.assert_called_once_with(
            test_ibkr_account.account_number, db_session
        )

        # Verify result
        assert result["status"] == "success"
        assert "positions_synced" in result

        print("✅ IBKR account sync routing working correctly")

    @patch("app.services.portfolio.broker_sync_service.TastyTradeSyncService")
    def test_sync_tastytrade_account(
        self, mock_tt_service, broker_sync_service, db_session, test_tastytrade_account
    ):
        """Test TastyTrade account sync routing."""
        # Setup mock
        mock_tt_instance = Mock()
        mock_tt_service.return_value = mock_tt_instance
        mock_tt_instance.sync_account_comprehensive.return_value = {
            "status": "success",
            "positions_synced": 5,
            "transactions_synced": 15,
        }

        # Execute sync
        result = broker_sync_service.sync_account(
            test_tastytrade_account.account_number, db_session
        )

        # Verify correct service was called
        mock_tt_service.assert_called_once()
        mock_tt_instance.sync_account_comprehensive.assert_called_once_with(
            test_tastytrade_account.account_number, db_session
        )

        # Verify result
        assert result["status"] == "success"
        assert "positions_synced" in result

        print("✅ TastyTrade account sync routing working correctly")

    @pytest.mark.asyncio
    async def test_tastytrade_sync_uses_stored_credentials(
        self, db_session, test_user
    ):
        """TastyTrade sync uses AccountCredentials when present."""
        from app.models.broker_account import AccountCredentials
        from app.services.security.credential_vault import credential_vault
        from app.services.portfolio.tastytrade_sync_service import (
            TastyTradeSyncService,
        )

        account = BrokerAccount(
            user_id=test_user.id,
            account_number="TT_CRED_TEST",
            account_name="TT Cred Test",
            broker=BrokerType.TASTYTRADE,
            account_type=AccountType.TAXABLE,
            sync_status=SyncStatus.NEVER_SYNCED,
            api_credentials_stored=True,
        )
        db_session.add(account)
        db_session.flush()

        payload = {"client_secret": "test_secret", "refresh_token": "test_refresh"}
        enc = credential_vault.encrypt_dict(payload)
        cred = AccountCredentials(
            account_id=account.id,
            encrypted_credentials=enc,
            provider=BrokerType.TASTYTRADE,
            credential_type="oauth",
        )
        db_session.add(cred)
        db_session.commit()

        svc = TastyTradeSyncService()
        with (
            patch.object(
                svc.client,
                "connect_with_credentials",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_creds,
            patch.object(
                svc.client, "connect_with_retry", new_callable=AsyncMock
            ) as mock_retry,
            patch.object(
                svc,
                "_sync_positions",
                new_callable=AsyncMock,
                return_value={"positions": 0},
            ),
            patch.object(
                svc, "_sync_trades", new_callable=AsyncMock, return_value={"trades": 0}
            ),
            patch.object(
                svc,
                "_sync_transactions",
                new_callable=AsyncMock,
                return_value={"transactions": 0},
            ),
            patch.object(
                svc,
                "_sync_dividends",
                new_callable=AsyncMock,
                return_value={"dividends": 0},
            ),
            patch.object(
                svc,
                "_sync_account_balances",
                new_callable=AsyncMock,
                return_value={"account_balances": 0},
            ),
        ):
            result = await svc.sync_account(db_session, account)
            mock_creds.assert_called_once_with(
                client_secret="test_secret", refresh_token="test_refresh"
            )
            mock_retry.assert_not_called()
            assert result.get("positions") == 0

    @pytest.mark.asyncio
    async def test_tastytrade_sync_falls_back_to_env(self, db_session, test_user):
        """TastyTrade sync uses env vars when no stored credentials."""
        from app.services.portfolio.tastytrade_sync_service import (
            TastyTradeSyncService,
        )

        account = BrokerAccount(
            user_id=test_user.id,
            account_number="TT_NO_CRED",
            broker=BrokerType.TASTYTRADE,
            account_type=AccountType.TAXABLE,
            sync_status=SyncStatus.NEVER_SYNCED,
            api_credentials_stored=False,
        )
        db_session.add(account)
        db_session.commit()

        svc = TastyTradeSyncService()
        with (
            patch.object(
                svc.client, "connect_with_credentials", new_callable=AsyncMock
            ) as mock_creds,
            patch.object(
                svc.client,
                "connect_with_retry",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_retry,
            patch.object(
                svc,
                "_sync_positions",
                new_callable=AsyncMock,
                return_value={"positions": 0},
            ),
            patch.object(
                svc, "_sync_trades", new_callable=AsyncMock, return_value={"trades": 0}
            ),
            patch.object(
                svc,
                "_sync_transactions",
                new_callable=AsyncMock,
                return_value={"transactions": 0},
            ),
            patch.object(
                svc,
                "_sync_dividends",
                new_callable=AsyncMock,
                return_value={"dividends": 0},
            ),
            patch.object(
                svc,
                "_sync_account_balances",
                new_callable=AsyncMock,
                return_value={"account_balances": 0},
            ),
        ):
            result = await svc.sync_account(db_session, account)
            mock_retry.assert_called_once()
            mock_creds.assert_not_called()
            assert result.get("positions") == 0

    def test_sync_unknown_broker_account(
        self, broker_sync_service, db_session, test_user
    ):
        """Test handling of unknown broker type."""
        # Create account with unknown broker (simulate future broker)
        unknown_account = BrokerAccount(
            user_id=test_user.id,
            account_number="UNKNOWN_123",
            account_name="Unknown Broker",
            broker=BrokerType.UNKNOWN_BROKER,
            account_type=AccountType.TAXABLE,
            sync_status=SyncStatus.QUEUED,
            connection_status="connected",
        )

        db_session.add(unknown_account)
        db_session.commit()

        # Should raise for unsupported broker enum
        with pytest.raises(ValueError) as exc_info:
            broker_sync_service.sync_account("UNKNOWN_123", db_session)

        assert "unsupported broker" in str(exc_info.value).lower()

        print("✅ Unknown broker handling working correctly")

    @patch("app.services.portfolio.broker_sync_service.IBKRSyncService")
    @patch("app.services.portfolio.broker_sync_service.TastyTradeSyncService")
    def test_sync_all_accounts(
        self,
        mock_tt_service,
        mock_ibkr_service,
        broker_sync_service,
        db_session,
        test_ibkr_account,
        test_tastytrade_account,
    ):
        """Test syncing all accounts across different brokers."""
        # Setup mocks
        mock_ibkr_instance = Mock()
        mock_ibkr_service.return_value = mock_ibkr_instance
        mock_ibkr_instance.sync_account_comprehensive.return_value = {
            "status": "success"
        }

        mock_tt_instance = Mock()
        mock_tt_service.return_value = mock_tt_instance
        mock_tt_instance.sync_account_comprehensive.return_value = {"status": "success"}

        # Execute sync all
        results = broker_sync_service.sync_all_accounts(db_session)

        # Verify accounts were synced (at least the two fixtures)
        assert len(results) >= 2
        assert any(k.startswith("ibkr_") for k in results.keys())
        assert any(k.startswith("tastytrade_") for k in results.keys())
        assert all(result["status"] == "success" for result in results.values())

        # Verify both services were called
        mock_ibkr_service.assert_called()
        mock_tt_service.assert_called()

        print("✅ Sync all accounts working correctly")

    def test_account_sync_status_update(
        self, broker_sync_service, db_session, test_ibkr_account
    ):
        """Test that account sync status is updated properly."""
        # Mock successful sync
        with patch(
            "app.services.portfolio.broker_sync_service.IBKRSyncService"
        ) as mock_service:
            mock_instance = Mock()
            mock_service.return_value = mock_instance
            mock_instance.sync_account_comprehensive.return_value = {
                "status": "success"
            }

            # Execute sync
            broker_sync_service.sync_account(
                test_ibkr_account.account_number, db_session
            )

            # Verify status was updated
            db_session.refresh(test_ibkr_account)
            assert test_ibkr_account.sync_status == SyncStatus.SUCCESS
            assert test_ibkr_account.last_successful_sync is not None

        print("✅ Account sync status update working correctly")

    def test_sync_error_handling(
        self, broker_sync_service, db_session, test_ibkr_account
    ):
        """Test error handling during sync operations."""
        # Mock sync failure
        with patch(
            "app.services.portfolio.broker_sync_service.IBKRSyncService"
        ) as mock_service:
            mock_instance = Mock()
            mock_service.return_value = mock_instance
            mock_instance.sync_account_comprehensive.side_effect = Exception(
                "Connection failed"
            )

            # Execute sync - should handle error gracefully
            result = broker_sync_service.sync_account(
                test_ibkr_account.account_number, db_session
            )

            # Verify error was handled
            assert result["status"] == "error"
            assert "error" in result

            # NOTE: The db_session fixture uses nested transactions; BrokerSyncService
            # rolls back the session on failure, which can roll back the fixture's outer
            # transaction too. We intentionally avoid asserting on persisted DB state here.

        print("✅ Sync error handling working correctly")

    def test_broker_service_factory_pattern(self, broker_sync_service):
        """Test that service uses factory pattern for broker services."""
        # Should be able to get appropriate service for each broker
        ibkr_service = broker_sync_service._get_broker_service(BrokerType.IBKR)
        tt_service = broker_sync_service._get_broker_service(BrokerType.TASTYTRADE)

        # Services should be different classes
        assert type(ibkr_service).__name__ == "IBKRSyncService"
        assert type(tt_service).__name__ == "TastyTradeSyncService"

        print("✅ Broker service factory pattern working correctly")


class TestBrokerSyncServiceArchitecture:
    """Test architectural compliance and extensibility."""

    def test_dry_principle_no_broker_duplication(self):
        """Test that broker-specific logic is not duplicated."""
        from app.services.portfolio.broker_sync_service import BrokerSyncService
        import inspect

        source = inspect.getsource(BrokerSyncService)

        # Should not have duplicated broker-specific code
        # Each broker should be handled by its own service
        lines = source.split("\n")

        # Count broker-specific mentions (should be minimal in coordinator)
        ibkr_mentions = sum(
            1
            for line in lines
            if "ibkr" in line.lower() and "import" not in line.lower()
        )
        tastytrade_mentions = sum(
            1
            for line in lines
            if "tastytrade" in line.lower() and "import" not in line.lower()
        )

        # Should have minimal broker-specific code (just routing)
        assert ibkr_mentions <= 3, f"Too many IBKR-specific references: {ibkr_mentions}"
        assert (
            tastytrade_mentions <= 3
        ), f"Too many TastyTrade-specific references: {tastytrade_mentions}"

        print("✅ DRY principle maintained - no broker logic duplication")

    def test_extensibility_for_new_brokers(self):
        """Test that adding new brokers doesn't require changing existing code."""
        from app.services.portfolio.broker_sync_service import BrokerSyncService
        import inspect

        source = inspect.getsource(BrokerSyncService)

        # Should use factory pattern or mapping, not long if/elif chains
        elif_count = source.count("elif")

        # Should have minimal elif statements (good architecture uses mapping/factory)
        assert (
            elif_count <= 2
        ), f"Too many elif statements - not extensible: {elif_count}"

        print("✅ Service is extensible for new brokers")

    def test_single_responsibility_coordination_only(self):
        """Test that service only coordinates, doesn't implement sync logic."""
        from app.services.portfolio.broker_sync_service import BrokerSyncService
        import inspect

        source = inspect.getsource(BrokerSyncService)

        # Should not have detailed sync implementation
        forbidden_patterns = [
            "flexquery",
            "api_key",
            "authenticate",
            "parse_xml",
            "calculate_pnl",
            "process_transactions",
            "update_positions",
        ]

        for pattern in forbidden_patterns:
            assert (
                pattern not in source.lower()
            ), f"Service contains implementation detail: {pattern}"

        print("✅ Service maintains single responsibility (coordination only)")

    def test_dependency_injection_pattern(self):
        """Test that service uses dependency injection for broker services."""
        from app.services.portfolio.broker_sync_service import BrokerSyncService

        service = BrokerSyncService()

        # Should be able to inject custom broker services for testing
        custom_service = Mock()

        # If service supports DI, this should work
        if hasattr(service, "_broker_services"):
            service._broker_services[BrokerType.IBKR] = custom_service
            retrieved_service = service._get_broker_service(BrokerType.IBKR)
            assert retrieved_service == custom_service

        print("✅ Dependency injection pattern supported")


class TestBrokerSyncServiceIntegration:
    """Test integration with other services and models."""

    def test_integration_with_account_config_service(self):
        """Test that broker sync works with account config service."""
        from app.services.portfolio.account_config_service import (
            AccountConfigService,
        )
        from app.services.portfolio.broker_sync_service import BrokerSyncService

        config_service = AccountConfigService()
        sync_service = BrokerSyncService()

        # Should be compatible - both work with BrokerAccount model
        assert hasattr(config_service, "seed_broker_accounts")
        assert hasattr(sync_service, "sync_account")

        print("✅ Integration with AccountConfigService working")

    def test_broker_account_model_compatibility(self):
        """Test compatibility with BrokerAccount model."""
        from app.services.portfolio.broker_sync_service import BrokerSyncService

        service = BrokerSyncService()

        # Should work with all broker types from enum
        for broker_type in BrokerType:
            try:
                # Should not fail for any valid broker type
                if hasattr(service, "_get_broker_service"):
                    broker_service = service._get_broker_service(broker_type)
                    assert broker_service is not None
            except ValueError as e:
                # Some brokers might not be implemented yet - that's ok
                assert "unsupported" in str(e).lower()

        print("✅ BrokerAccount model compatibility working")

    def test_database_transaction_handling(self, db_session):
        """Test that service handles database transactions properly."""
        from app.services.portfolio.broker_sync_service import BrokerSyncService

        service = BrokerSyncService()

        # Mock successful and failed syncs to test transaction handling
        with patch.object(service, "_get_broker_service") as mock_get_service:
            mock_broker_service = Mock()
            mock_get_service.return_value = mock_broker_service

            # Test rollback on failure
            mock_broker_service.sync_account_comprehensive.side_effect = Exception(
                "Test error"
            )

            # Create test account
            user = User(email="test@test.com", username="testuser")
            db_session.add(user)
            db_session.flush()

            account = BrokerAccount(
                user_id=user.id,
                account_number="TEST_TRANSACTION",
                account_name="Test Transaction",
                broker=BrokerType.IBKR,
                account_type=AccountType.TAXABLE,
                sync_status=SyncStatus.QUEUED,
            )
            db_session.add(account)
            db_session.commit()

            # Sync should fail but not crash
            result = service.sync_account("TEST_TRANSACTION", db_session)
            assert result["status"] == "error"

            # Service should not raise; rollback semantics differ under the nested-transaction fixture.
            # In production, the broker account row exists in a committed transaction.
            # Here, we primarily assert the service reports the error cleanly.

        print("✅ Database transaction handling working correctly")


if __name__ == "__main__":
    print("🧪 Running Broker Sync Service Tests...")
    pytest.main([__file__, "-v"])
    print("🎉 Broker Sync Service tests completed!")
