"""AccountCredentialsService: load and decrypt stored broker credentials.

medallion: ops
"""

from __future__ import annotations

from typing import Dict, Any

from sqlalchemy.orm import Session

from app.models.broker_account import AccountCredentials
from app.services.security.credential_vault import credential_vault


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
    def update_encrypted(account_id: int, updates: Dict[str, Any], db: Session) -> None:
        """Merge *updates* into an existing AccountCredentials payload and persist."""
        cred = (
            db.query(AccountCredentials)
            .filter(AccountCredentials.account_id == account_id)
            .first()
        )
        if not cred or not cred.encrypted_credentials:
            raise CredentialsNotFoundError(f"No credentials to update for account_id={account_id}")
        payload = credential_vault.decrypt_dict(cred.encrypted_credentials)
        payload.update(updates)
        cred.encrypted_credentials = credential_vault.encrypt_dict(payload)

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

    @staticmethod
    def get_ibkr_gateway_credentials(account_id: int, db: Session) -> Dict[str, Any]:
        """
        Get IB Gateway connection settings stored alongside FlexQuery creds.

        Returns dict with optional keys: gateway_username, gateway_password,
        gateway_trading_mode, gateway_host, gateway_port, gateway_client_id.
        Returns empty dict if no gateway-specific credentials are stored.
        """
        try:
            payload = AccountCredentialsService.get_decrypted(account_id, db)
        except CredentialsNotFoundError:
            return {}
        return {
            k: v for k, v in payload.items()
            if k.startswith("gateway_") and v is not None
        }

    @staticmethod
    def save_ibkr_gateway_credentials(
        account_id: int, gateway_settings: Dict[str, Any], db: Session
    ) -> None:
        """
        Merge gateway settings into the existing IBKR credential payload.
        Creates a new AccountCredentials row if none exists.
        """
        from app.models.broker_account import BrokerType

        cred = (
            db.query(AccountCredentials)
            .filter(AccountCredentials.account_id == account_id)
            .first()
        )
        if cred and cred.encrypted_credentials:
            payload = credential_vault.decrypt_dict(cred.encrypted_credentials)
        else:
            payload = {}

        for key in (
            "gateway_username", "gateway_password", "gateway_trading_mode",
            "gateway_host", "gateway_port", "gateway_client_id",
        ):
            if key in gateway_settings:
                val = gateway_settings[key]
                if val is not None and str(val).strip():
                    payload[key] = val

        enc = credential_vault.encrypt_dict(payload)
        if cred:
            cred.encrypted_credentials = enc
        else:
            cred = AccountCredentials(
                account_id=account_id,
                encrypted_credentials=enc,
                provider=BrokerType.IBKR,
                credential_type="ibkr_flex",
            )
            db.add(cred)
        db.commit()


account_credentials_service = AccountCredentialsService()
