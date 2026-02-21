"""Tests for AccountCredentialsService."""

import pytest
from unittest.mock import patch

try:
    from backend.models import User, BrokerAccount
    from backend.models.broker_account import (
        AccountCredentials,
        BrokerType,
        AccountType,
    )
    from backend.services.portfolio.account_credentials_service import (
        AccountCredentialsService,
        CredentialsNotFoundError,
    )
    from backend.services.security.credential_vault import credential_vault

    AVAILABLE = True
except Exception:
    AVAILABLE = False


@pytest.fixture
def user(db_session):
    u = User(email="creds@test.com", username="credsuser", password_hash="x")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def broker_account(db_session, user):
    acc = BrokerAccount(
        user_id=user.id,
        broker=BrokerType.IBKR,
        account_number="U123",
        account_type=AccountType.TAXABLE,
        is_enabled=True,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


@pytest.mark.skipif(not AVAILABLE, reason="Dependencies not available")
def test_get_decrypted_raises_when_not_found(db_session, broker_account):
    """get_decrypted raises CredentialsNotFoundError when no credentials exist."""
    # Create account with no AccountCredentials row
    with pytest.raises(CredentialsNotFoundError):
        AccountCredentialsService.get_decrypted(broker_account.id, db_session)


@pytest.mark.skipif(not AVAILABLE, reason="Dependencies not available")
def test_get_decrypted_raises_when_empty_encrypted(db_session, broker_account):
    """get_decrypted raises when encrypted_credentials is empty."""
    cred = AccountCredentials(
        account_id=broker_account.id,
        encrypted_credentials=None,
        provider=BrokerType.IBKR,
    )
    db_session.add(cred)
    db_session.commit()

    with pytest.raises(CredentialsNotFoundError):
        AccountCredentialsService.get_decrypted(broker_account.id, db_session)


@pytest.mark.skipif(not AVAILABLE, reason="Dependencies not available")
def test_get_decrypted_returns_dict_when_present(db_session, broker_account):
    """get_decrypted returns decrypted payload when credentials exist."""
    payload = {"flex_token": "tok123", "query_id": "q456"}
    enc = credential_vault.encrypt_dict(payload)
    cred = AccountCredentials(
        account_id=broker_account.id,
        encrypted_credentials=enc,
        provider=BrokerType.IBKR,
    )
    db_session.add(cred)
    db_session.commit()

    result = AccountCredentialsService.get_decrypted(broker_account.id, db_session)
    assert result["flex_token"] == "tok123"
    assert result["query_id"] == "q456"
    assert result.get("provider") == "ibkr"


@pytest.mark.skipif(not AVAILABLE, reason="Dependencies not available")
def test_get_ibkr_credentials_raises_when_incomplete(db_session, broker_account):
    """get_ibkr_credentials raises when payload missing flex_token or query_id."""
    payload = {"flex_token": "x"}  # missing query_id
    enc = credential_vault.encrypt_dict(payload)
    cred = AccountCredentials(
        account_id=broker_account.id,
        encrypted_credentials=enc,
        provider=BrokerType.IBKR,
    )
    db_session.add(cred)
    db_session.commit()

    with pytest.raises(CredentialsNotFoundError):
        AccountCredentialsService.get_ibkr_credentials(broker_account.id, db_session)


@pytest.mark.skipif(not AVAILABLE, reason="Dependencies not available")
def test_get_ibkr_credentials_returns_dict(db_session, broker_account):
    """get_ibkr_credentials returns flex_token and query_id."""
    payload = {"flex_token": "tok", "query_id": "qid"}
    enc = credential_vault.encrypt_dict(payload)
    cred = AccountCredentials(
        account_id=broker_account.id,
        encrypted_credentials=enc,
        provider=BrokerType.IBKR,
    )
    db_session.add(cred)
    db_session.commit()

    result = AccountCredentialsService.get_ibkr_credentials(broker_account.id, db_session)
    assert result == {"flex_token": "tok", "query_id": "qid"}
