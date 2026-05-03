"""Test constants and JWT helpers."""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ISSUER = "https://clerk.example.test"
AUDIENCE = "https://api.example.test"
RSA_KID = "unit-test-kid"


def int_to_b64u(value: int) -> str:
    length = (value.bit_length() + 7) // 8
    raw = value.to_bytes(length, byteorder="big")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def generate_rsa_pem() -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def public_jwk_from_pem(rsa_private_pem: bytes) -> dict[str, Any]:
    private_key = serialization.load_pem_private_key(rsa_private_pem, password=None)
    public_numbers = private_key.public_key().public_numbers()
    return {
        "kty": "RSA",
        "kid": RSA_KID,
        "use": "sig",
        "alg": "RS256",
        "n": int_to_b64u(public_numbers.n),
        "e": int_to_b64u(public_numbers.e),
    }


def mint_clerk_token(
    *,
    rsa_private_pem: bytes,
    claims: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> str:
    from jose import jwt

    now = int(datetime.now(UTC).timestamp())
    base: dict[str, Any] = {
        "sub": "user_123",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + 3600,
        "org_id": "org_1",
        "org_role": "admin",
        "email": "dev@example.test",
    }
    if claims:
        base.update(claims)
    hdrs = {"kid": RSA_KID, "alg": "RS256"}
    if headers:
        hdrs.update(headers)
    return jwt.encode(
        base,
        rsa_private_pem.decode("utf-8"),
        algorithm="RS256",
        headers=hdrs,
    )


def expired_claims() -> dict[str, Any]:
    now = datetime.now(UTC)
    past = now - timedelta(seconds=240)
    return {
        "iat": int(past.timestamp()),
        "exp": int((past + timedelta(seconds=60)).timestamp()),
    }
