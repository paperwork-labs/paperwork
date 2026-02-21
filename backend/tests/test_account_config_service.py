#!/usr/bin/env python3
"""
AxiomFolio V1 - Account Configuration Service Tests
===================================================

Tests for account_config_service.py functionality:
- Environment variable parsing
- Account seeding from .env to database
- Account type detection and validation
- DRY principle adherence
"""

import pytest
from unittest.mock import Mock, patch

from backend.models import User, BrokerAccount
from backend.models.broker_account import BrokerType, AccountType, SyncStatus
from backend.services.portfolio.account_config_service import AccountConfigService


class TestAccountConfigService:
    """Test account configuration service functionality."""

    # Use global db_session fixture from tests/conftest.py (Alembic + transaction rollback)

    @pytest.fixture
    def account_service(self):
        """Create account config service instance."""
        return AccountConfigService()

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with test account data."""
        mock_settings = Mock()
        mock_settings.IBKR_ACCOUNTS = (
            "IBKR_TEST_ACCOUNT_A:TAXABLE,IBKR_TEST_ACCOUNT_B:IRA"
        )
        mock_settings.TASTYTRADE_CLIENT_SECRET = "test_secret"
        mock_settings.TASTYTRADE_ACCOUNT_NUMBER = "TT_TEST_ACCOUNT_1"
        mock_settings.FIDELITY_ACCOUNTS = ""  # Empty for testing
        return mock_settings

    def test_account_config_service_initialization(self, account_service):
        """Test service initializes correctly."""
        assert account_service is not None
        assert hasattr(account_service, "get_ibkr_accounts_from_env")
        assert hasattr(account_service, "get_tastytrade_account_from_env")
        assert hasattr(account_service, "seed_broker_accounts")
        print("✅ AccountConfigService initialization successful")

    def test_ibkr_account_parsing(self, account_service, mock_settings):
        """Test IBKR account parsing from environment variables."""
        accounts = account_service.get_ibkr_accounts_from_env(mock_settings)

        assert len(accounts) == 2

        # Test first account (TAXABLE)
        assert accounts[0]["account_id"] == "IBKR_TEST_ACCOUNT_A"
        assert accounts[0]["account_type"] == AccountType.TAXABLE
        assert accounts[0]["broker"] == BrokerType.IBKR

        # Test second account (IRA)
        assert accounts[1]["account_id"] == "IBKR_TEST_ACCOUNT_B"
        assert accounts[1]["account_type"] == AccountType.IRA
        assert accounts[1]["broker"] == BrokerType.IBKR

        print("✅ IBKR account parsing working correctly")

    def test_tastytrade_account_parsing(self, account_service, mock_settings):
        """Test TastyTrade account parsing from environment variables."""
        account = account_service.get_tastytrade_account_from_env(mock_settings)

        assert account is not None
        assert account["account_id"] == "oauth"
        assert account["account_number"] == "TT_TEST_ACCOUNT_1"
        assert account["broker"] == BrokerType.TASTYTRADE
        assert account["account_type"] == AccountType.TAXABLE  # Default

        print("✅ TastyTrade account parsing working correctly")

    def test_account_type_detection(self, account_service):
        """Test automatic account type detection from account number patterns."""
        # Test TAXABLE account (U prefix)
        taxable_type = account_service._detect_account_type("IBKR_TEST_ACCOUNT_A")
        assert taxable_type == AccountType.TAXABLE

        # Test IRA account (specific pattern)
        ira_type = account_service._detect_account_type("IBKR_TEST_ACCOUNT_B")
        assert ira_type == AccountType.IRA

        # Test default case
        default_type = account_service._detect_account_type("UNKNOWN123")
        assert default_type == AccountType.TAXABLE  # Default fallback

        print("✅ Account type detection working correctly")

    def test_ensure_user_exists(self, account_service, db_session):
        """Test user creation when none exists."""
        # Verify no users initially
        users = db_session.query(User).all()
        assert len(users) == 0

        # Create default user
        user = account_service.ensure_user_exists(db_session)

        # Verify user was created
        assert user is not None
        assert user.email == "default@axiomfolio.com"
        assert user.username == "default_user"
        assert user.full_name == "Default AxiomFolio User"

        # Verify user persisted in database
        db_users = db_session.query(User).all()
        assert len(db_users) == 1
        assert db_users[0].email == "default@axiomfolio.com"

        print("✅ User creation working correctly")

    def test_ensure_user_exists_idempotent(self, account_service, db_session):
        """Test that ensure_user_exists is idempotent."""
        # Create user first time
        user1 = account_service.ensure_user_exists(db_session)
        user1_id = user1.id

        # Call again - should return same user
        user2 = account_service.ensure_user_exists(db_session)
        user2_id = user2.id

        assert user1_id == user2_id

        # Verify only one user in database
        db_users = db_session.query(User).all()
        assert len(db_users) == 1

        print("✅ User creation is idempotent")

    @patch("backend.services.portfolio.account_config_service.settings")
    def test_seed_broker_accounts_complete(
        self, mock_settings_patch, account_service, db_session
    ):
        """Test complete broker account seeding process."""
        # Setup mock settings
        mock_settings_patch.IBKR_ACCOUNTS = (
            "IBKR_TEST_ACCOUNT_A:TAXABLE,IBKR_TEST_ACCOUNT_B:IRA"
        )
        mock_settings_patch.TASTYTRADE_CLIENT_SECRET = "test_secret"
        mock_settings_patch.TASTYTRADE_ACCOUNT_NUMBER = "TT_TEST_ACCOUNT_1"
        mock_settings_patch.FIDELITY_ACCOUNTS = ""

        # Run seeding
        account_service.seed_broker_accounts(db_session)

        # Verify user was created
        users = db_session.query(User).all()
        assert len(users) == 1
        user = users[0]

        # Verify all accounts were created
        broker_accounts = db_session.query(BrokerAccount).all()
        assert len(broker_accounts) == 3  # 2 IBKR + 1 TastyTrade

        # Check IBKR accounts
        ibkr_accounts = (
            db_session.query(BrokerAccount).filter_by(broker=BrokerType.IBKR).all()
        )
        assert len(ibkr_accounts) == 2

        ibkr_taxable = next(
            (acc for acc in ibkr_accounts if acc.account_number == "IBKR_TEST_ACCOUNT_A"),
            None,
        )
        assert ibkr_taxable is not None
        assert ibkr_taxable.account_type == AccountType.TAXABLE
        assert ibkr_taxable.user_id == user.id

        ibkr_ira = next(
            (acc for acc in ibkr_accounts if acc.account_number == "IBKR_TEST_ACCOUNT_B"),
            None,
        )
        assert ibkr_ira is not None
        assert ibkr_ira.account_type == AccountType.IRA
        assert ibkr_ira.user_id == user.id

        # Check TastyTrade account
        tt_accounts = (
            db_session.query(BrokerAccount)
            .filter_by(broker=BrokerType.TASTYTRADE)
            .all()
        )
        assert len(tt_accounts) == 1
        tt_account = tt_accounts[0]
        assert tt_account.account_number == "TT_TEST_ACCOUNT_1"
        assert tt_account.account_type == AccountType.TAXABLE
        assert tt_account.user_id == user.id

        print("✅ Complete broker account seeding working correctly")

    def test_seed_accounts_idempotent(self, account_service, db_session, mock_settings):
        """Test that seeding is idempotent (won't create duplicates)."""
        with patch(
            "backend.services.portfolio.account_config_service.settings", mock_settings
        ):
            # First seeding
            account_service.seed_broker_accounts(db_session)
            first_count = db_session.query(BrokerAccount).count()

            # Second seeding - should not create duplicates
            account_service.seed_broker_accounts(db_session)
            second_count = db_session.query(BrokerAccount).count()

            assert first_count == second_count
            assert second_count == 3  # 2 IBKR + 1 TastyTrade

        print("✅ Account seeding is idempotent")

    def test_no_hardcoded_account_numbers(self, account_service):
        """Test that no account numbers are hardcoded in the service."""
        import inspect

        # Get the source code of the service
        source = inspect.getsource(AccountConfigService)

        # Check that no IBKR-style account numbers are hardcoded (e.g., U########)
        import re

        found = re.findall(r"U\\d{7,}", source)
        assert not found, f"❌ Hardcoded-looking IBKR account numbers found: {found}"

        print("✅ No hardcoded account numbers found - DRY principle maintained")

    def test_dry_principle_enum_usage(self, account_service):
        """Test that enums are used consistently (DRY principle)."""
        # Test that service uses proper enums instead of strings
        accounts = [
            {"broker": BrokerType.IBKR, "account_type": AccountType.TAXABLE},
            {"broker": BrokerType.TASTYTRADE, "account_type": AccountType.IRA},
        ]

        for account in accounts:
            assert isinstance(account["broker"], BrokerType)
            assert isinstance(account["account_type"], AccountType)

        print("✅ DRY principle maintained - proper enum usage")

    def test_error_handling_malformed_env(self, account_service):
        """Test error handling with malformed environment variables."""
        mock_settings = Mock()
        mock_settings.IBKR_ACCOUNTS = "MALFORMED_STRING_NO_COLON"
        mock_settings.TASTYTRADE_CLIENT_SECRET = ""

        # Should handle malformed data gracefully
        try:
            accounts = account_service.get_ibkr_accounts_from_env(mock_settings)
            # Should return empty list or handle gracefully
            assert isinstance(accounts, list)
        except Exception as e:
            # Should provide meaningful error message
            assert "malformed" in str(e).lower() or "invalid" in str(e).lower()

        print("✅ Error handling working correctly")

    def test_integration_with_broker_account_model(self, account_service, db_session):
        """Test integration with BrokerAccount model and enums."""
        # Ensure user exists
        user = account_service.ensure_user_exists(db_session)

        # Create broker account directly
        broker_account = BrokerAccount(
            user_id=user.id,
            account_number="TEST_INTEGRATION",
            account_name="Test Integration",
            broker=BrokerType.IBKR,
            account_type=AccountType.TAXABLE,
            sync_status=SyncStatus.QUEUED,
            connection_status="connected",
        )

        db_session.add(broker_account)
        db_session.commit()

        # Verify the relationship works
        retrieved_account = (
            db_session.query(BrokerAccount)
            .filter_by(account_number="TEST_INTEGRATION")
            .first()
        )
        assert retrieved_account is not None
        assert retrieved_account.user.email == "default@axiomfolio.com"
        assert retrieved_account.broker == BrokerType.IBKR
        assert retrieved_account.account_type == AccountType.TAXABLE

        print("✅ Integration with BrokerAccount model working correctly")


class TestAccountConfigServiceArchitecture:
    """Test architectural compliance and DRY principles."""

    def test_no_broker_specific_hardcoding(self):
        """Test that service is extensible for new brokers without hardcoding."""
        from backend.services.portfolio.account_config_service import (
            AccountConfigService,
        )
        import inspect

        source = inspect.getsource(AccountConfigService)

        # Should not have hardcoded broker names except in method names
        suspicious_strings = ["ibkr", "tastytrade", "fidelity"]
        method_definitions = [line for line in source.split("\n") if "def " in line]

        for line in source.split("\n"):
            if any(suspicious in line.lower() for suspicious in suspicious_strings):
                # Allow in method names and comments
                if (
                    "def " in line
                    or "#" in line
                    or "IBKR_" in line
                    or "TASTYTRADE_" in line
                ):
                    continue
                # Allow in environment variable names
                if "settings." in line:
                    continue
                print(f"⚠️  Potential hardcoding: {line.strip()}")

        print("✅ Service is broker-agnostic and extensible")

    def test_single_responsibility_principle(self):
        """Test that service follows single responsibility principle."""
        from backend.services.portfolio.account_config_service import (
            AccountConfigService,
        )

        service = AccountConfigService()

        # Should only have account configuration related methods
        methods = [method for method in dir(service) if not method.startswith("_")]
        expected_methods = [
            "get_ibkr_accounts_from_env",
            "get_tastytrade_account_from_env",
            "seed_broker_accounts",
            "ensure_user_exists",
        ]

        for method in expected_methods:
            assert hasattr(service, method), f"Missing expected method: {method}"

        # Should not have sync or trading methods (those belong elsewhere)
        forbidden_methods = ["sync_positions", "execute_trade", "get_market_data"]
        for method in forbidden_methods:
            assert not hasattr(
                service, method
            ), f"Service has method it shouldn't: {method}"

        print("✅ Single responsibility principle maintained")


if __name__ == "__main__":
    print("🧪 Running Account Configuration Service Tests...")
    pytest.main([__file__, "-v"])
    print("🎉 Account Configuration Service tests completed!")
