"""AccountCredentialsService: load and decrypt stored broker credentials."""

from __future__ import annotations

from typing import Dict, Any

from sqlalchemy.orm import Session

from backend.models.broker_account import AccountCredentials
from backend.services.security.credential_vault import credential_vault


class CredentialsNotFoundError(Exception):
    """Raised when no credentials exist for the given account."""

    pass


class AccountCredentialsService:
    """Service for retrieving decrypted broker credentials."""

    @staticmethod
    def get_decrypted(account_id: int, db: Session) -> Dict[str, Any]:
        """
        Load AccountCredentials for the account, decrypt, and return full payload.

        Returns:
            Dict with 'provider' (BrokerType value) and decrypted credential fields.
        Raises:
            CredentialsNotFoundError: When no credentials exist for the account.
        """
        cred = (
            db.query(AccountCredentials)
            .filter(AccountCredentials.account_id == account_id)
            .first()
        )
        if not cred or not cred.encrypted_credentials:
            raise CredentialsNotFoundError(f"No credentials for account_id={account_id}")

        payload = credential_vault.decrypt_dict(cred.encrypted_credentials)
        provider = cred.provider
        if provider is not None:
            payload["provider"] = provider.value if hasattr(provider, "value") else str(provider)
        return payload

    @staticmethod
    def get_ibkr_credentials(account_id: int, db: Session) -> Dict[str, str]:
        """
        Get IBKR FlexQuery credentials (flex_token, query_id) for the account.

        Returns:
            Dict with 'flex_token' and 'query_id'.
        Raises:
            CredentialsNotFoundError: When no IBKR credentials exist.
            ValueError: When payload shape is invalid (missing flex_token or query_id).
        """
        payload = AccountCredentialsService.get_decrypted(account_id, db)
        flex_token = payload.get("flex_token") or payload.get("token")
        query_id = payload.get("query_id")
        if not flex_token or not query_id:
            raise CredentialsNotFoundError(
                f"IBKR credentials incomplete for account_id={account_id}: "
                "flex_token and query_id required"
            )
        return {"flex_token": str(flex_token).strip(), "query_id": str(query_id).strip()}


account_credentials_service = AccountCredentialsService()
