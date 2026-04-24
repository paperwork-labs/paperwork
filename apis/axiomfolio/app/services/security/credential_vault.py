"""medallion: ops"""

from __future__ import annotations

import base64
import json
import hashlib
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _derive_fernet_key(secret: str) -> bytes:
    """
    Derive a urlsafe base64-encoded 32-byte key from an arbitrary secret.
    """
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _build_fernet(key_override: Optional[str] = None) -> Fernet:
    """
    Build a Fernet instance from ENCRYPTION_KEY or SECRET_KEY fallback.
    Accepts either a pre-encoded Fernet key or an arbitrary secret which will be derived.
    """
    candidate = key_override or settings.ENCRYPTION_KEY or settings.SECRET_KEY
    try:
        # Try treating candidate as a Fernet key
        return Fernet(candidate)
    except Exception:
        # Derive a valid Fernet key from arbitrary secret
        derived = _derive_fernet_key(candidate)
        return Fernet(derived)


class CredentialVault:
    """
    Small utility for encrypting/decrypting credential payloads at rest.
    """

    def __init__(self, key_override: Optional[str] = None):
        self._fernet = _build_fernet(key_override)

    def encrypt_text(self, plaintext: str) -> str:
        token = self._fernet.encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")

    def decrypt_text(self, token: str) -> str:
        try:
            data = self._fernet.decrypt(token.encode("utf-8"))
            return data.decode("utf-8")
        except InvalidToken as e:
            raise ValueError("Invalid encryption token") from e

    def encrypt_dict(self, payload: Dict[str, Any]) -> str:
        serialized = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        return self.encrypt_text(serialized)

    def decrypt_dict(self, token: str) -> Dict[str, Any]:
        text = self.decrypt_text(token)
        obj = json.loads(text) if text else {}
        if not isinstance(obj, dict):
            raise ValueError("Decrypted payload is not a JSON object")
        return obj


# Default instance for convenience
credential_vault = CredentialVault()


