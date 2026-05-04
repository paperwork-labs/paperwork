"""AES-256-GCM for ``brain_user_vault`` — matches Studio ``apps/studio/src/lib/crypto.ts``."""

from __future__ import annotations

import base64
import logging
import os
from typing import Final

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings

logger = logging.getLogger(__name__)

_TAG_LEN: Final[int] = 16
_NONCE_LEN: Final[int] = 12


class VaultDecryptionError(RuntimeError):
    """Raised when ciphertext cannot be decrypted or authenticated (corrupt key or data)."""


def _key_material() -> bytes:
    raw_b64 = (
        (settings.BRAIN_USER_VAULT_ENCRYPTION_KEY or "").strip()
        or (settings.SECRETS_ENCRYPTION_KEY or "").strip()
        or os.environ.get("SECRETS_ENCRYPTION_KEY", "").strip()
        or os.environ.get("BRAIN_USER_VAULT_ENCRYPTION_KEY", "").strip()
    )
    if not raw_b64:
        raise RuntimeError(
            "brain_user_vault encryption key missing: set BRAIN_USER_VAULT_ENCRYPTION_KEY "
            "or SECRETS_ENCRYPTION_KEY (32-byte key, base64-encoded, same contract as Studio)"
        )
    try:
        key = base64.b64decode(raw_b64)
    except Exception as e:
        logger.warning("brain_user_vault key base64 decode failed: %s", type(e).__name__)
        raise RuntimeError("Invalid brain_user_vault encryption key encoding") from e
    if len(key) != 32:
        raise RuntimeError(
            "brain_user_vault encryption key must decode to exactly 32 bytes (AES-256); "
            "generate with Studio generateEncryptionKey() or openssl rand -base64 32"
        )
    return key


def encrypt_secret_value(plaintext: str) -> tuple[str, str, str]:
    """Encrypt plaintext; returns ``(encrypted_value_b64, iv_b64, auth_tag_b64)``."""
    key = _key_material()
    aes = AESGCM(key)
    nonce = os.urandom(_NONCE_LEN)
    ct_and_tag = aes.encrypt(nonce, plaintext.encode("utf-8"), None)
    if len(ct_and_tag) < _TAG_LEN:
        raise RuntimeError("AES-GCM output shorter than auth tag length")
    ciphertext = ct_and_tag[:-_TAG_LEN]
    tag = ct_and_tag[-_TAG_LEN:]
    return (
        base64.b64encode(ciphertext).decode("ascii"),
        base64.b64encode(nonce).decode("ascii"),
        base64.b64encode(tag).decode("ascii"),
    )


def decrypt_secret_value(encrypted_value_b64: str, iv_b64: str, auth_tag_b64: str) -> str:
    """Decrypt a row's crypto fields; raises :class:`VaultDecryptionError` on failure."""
    key = _key_material()
    try:
        ciphertext = base64.b64decode(encrypted_value_b64)
        nonce = base64.b64decode(iv_b64)
        tag = base64.b64decode(auth_tag_b64)
    except Exception as e:
        logger.warning("brain_user_vault base64 decode failed: %s", type(e).__name__)
        raise VaultDecryptionError("Corrupt vault encoding (base64)") from e
    if len(nonce) != _NONCE_LEN:
        raise VaultDecryptionError("Invalid IV length for AES-GCM")
    aes = AESGCM(key)
    try:
        plain = aes.decrypt(nonce, ciphertext + tag, None)
    except Exception as e:
        logger.warning("brain_user_vault decrypt/authenticate failed: %s", type(e).__name__)
        raise VaultDecryptionError("Decrypt failed — wrong key or corrupt ciphertext") from e
    return plain.decode("utf-8")
