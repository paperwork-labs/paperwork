import base64
import os
import hashlib
from cryptography.fernet import Fernet
from backend.services.security.credential_vault import CredentialVault


def _derive_key(secret: str) -> str:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8")


def test_vault_round_trip_with_valid_fernet_key():
    key = Fernet.generate_key().decode("utf-8")
    vault = CredentialVault(key_override=key)
    payload = {"access_token": "abc", "refresh_token": "xyz", "broker": "schwab"}
    token = vault.encrypt_dict(payload)
    back = vault.decrypt_dict(token)
    assert back == payload


def test_vault_round_trip_with_derived_key_from_secret():
    secret = "unit-test-secret"
    derived = _derive_key(secret)  # mimic module derivation behavior
    vault = CredentialVault(key_override=secret)  # raw secret; vault derives internally
    text = "hello-credentials"
    token = vault.encrypt_text(text)
    # Also ensure decrypt compatible with explicit derived key
    vault2 = CredentialVault(key_override=derived)
    assert vault2.decrypt_text(token) == text


def test_vault_rejects_invalid_token():
    key = Fernet.generate_key().decode("utf-8")
    vault = CredentialVault(key_override=key)
    invalid = "not-a-valid-token"
    try:
        vault.decrypt_text(invalid)
        assert False, "Expected ValueError for invalid token"
    except ValueError:
        pass


