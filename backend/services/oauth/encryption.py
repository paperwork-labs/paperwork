"""Fernet-based encryption for OAuth broker tokens.

Why a dedicated helper? The existing ``CredentialVault`` is tied to the
``account_credentials`` table and bakes in a JSON envelope we don't need for
single-token storage. OAuth tokens are short opaque strings and benefit from:

* Independent key rotation (``OAUTH_TOKEN_ENCRYPTION_KEY`` separate from the
  app-wide ``ENCRYPTION_KEY``) so that broker credential leaks can be
  remediated without re-encrypting every other secret.
* MultiFernet rotation — new tokens encrypt under the primary key, but
  existing tokens encrypted under retired keys keep decrypting until they
  rotate naturally on next refresh.

There is **no silent fallback** for missing keys: if no key is configured at
all we raise ``EncryptionUnavailableError`` rather than storing plaintext.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import logging
from functools import lru_cache
from typing import List, Optional

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

logger = logging.getLogger(__name__)


class EncryptionUnavailableError(RuntimeError):
    """Raised when no OAuth encryption key is configured."""


class EncryptionDecryptError(RuntimeError):
    """Raised when ciphertext cannot be decrypted by any active key."""


def _normalize_key(raw: str) -> bytes:
    """Coerce arbitrary key material into a 32-byte url-safe-base64 Fernet key.

    Accepts either:
    * a properly formatted Fernet key (44-char url-safe base64), or
    * any free-form string, in which case we derive a 32-byte key via SHA-256.

    The latter mode is for dev convenience so operators can reuse
    ``ENCRYPTION_KEY`` / ``SECRET_KEY`` without having to mint a new key just
    for OAuth. We log a warning so the operator knows derived keys are in use.
    """

    raw = (raw or "").strip()
    if not raw:
        raise EncryptionUnavailableError("empty key material passed to OAuth encryption")
    try:
        decoded = base64.urlsafe_b64decode(raw.encode("ascii"))
        if len(decoded) == 32:
            return raw.encode("ascii")
    except (binascii.Error, ValueError):
        pass
    logger.warning(
        "OAuth encryption key is not 32-byte url-safe base64; deriving via SHA-256"
    )
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _resolve_keys() -> List[bytes]:
    # Local import keeps this module importable even before settings finishes
    # loading (e.g. during alembic offline mode).
    from backend.config import settings

    primary = (
        getattr(settings, "OAUTH_TOKEN_ENCRYPTION_KEY", None)
        or getattr(settings, "ENCRYPTION_KEY", None)
        or getattr(settings, "SECRET_KEY", None)
    )
    if not primary:
        raise EncryptionUnavailableError(
            "No OAuth encryption key configured. Set OAUTH_TOKEN_ENCRYPTION_KEY "
            "(preferred) or ENCRYPTION_KEY in environment."
        )

    keys: List[bytes] = [_normalize_key(primary)]

    retired_csv = getattr(settings, "OAUTH_TOKEN_ENCRYPTION_KEYS_RETIRED", None) or ""
    for piece in retired_csv.split(","):
        piece = piece.strip()
        if piece:
            keys.append(_normalize_key(piece))

    if primary == getattr(settings, "SECRET_KEY", None) and not getattr(
        settings, "OAUTH_TOKEN_ENCRYPTION_KEY", None
    ):
        logger.warning(
            "OAUTH_TOKEN_ENCRYPTION_KEY not set; falling back to SECRET_KEY for "
            "OAuth token encryption. Configure a dedicated key in production."
        )
    return keys


@lru_cache(maxsize=1)
def _multi() -> MultiFernet:
    keys = _resolve_keys()
    fernets = [Fernet(k) for k in keys]
    return MultiFernet(fernets)


def reset_cache() -> None:
    """Clear the cached Fernet instance (used by tests after env mutation)."""

    _multi.cache_clear()


def encrypt(plaintext: str) -> str:
    """Encrypt a token string and return the Fernet ciphertext as ``str``."""

    if plaintext is None:
        raise ValueError("cannot encrypt None")
    token = _multi().encrypt(plaintext.encode("utf-8"))
    return token.decode("ascii")


def decrypt(ciphertext: str) -> str:
    """Decrypt a Fernet ciphertext, trying primary then retired keys."""

    if ciphertext is None:
        raise ValueError("cannot decrypt None")
    try:
        return _multi().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise EncryptionDecryptError(
            "OAuth token ciphertext could not be decrypted with any active key"
        ) from exc


def decrypt_optional(ciphertext: Optional[str]) -> Optional[str]:
    """Convenience wrapper that returns None for None input."""

    if ciphertext is None:
        return None
    return decrypt(ciphertext)


__all__ = [
    "EncryptionUnavailableError",
    "EncryptionDecryptError",
    "encrypt",
    "decrypt",
    "decrypt_optional",
    "reset_cache",
]
