"""Tests for :class:`clerk_auth.validator.ClerkTokenValidator`."""

from __future__ import annotations

import time
from typing import Any

import pytest
from jose import jwt

from clerk_auth.errors import (
    INVALID_TOKEN_MESSAGE,
    ClerkUnreachableError,
    InvalidTokenError,
)
from clerk_auth.jwks import JWKSClient
from clerk_auth.validator import ClerkTokenValidator
from tests.support import (
    AUDIENCE,
    ISSUER,
    RSA_KID,
    expired_claims,
    mint_clerk_token,
)


@pytest.fixture()
def validator(
    monkeypatch: pytest.MonkeyPatch,
    rsa_public_jwk: dict[str, Any],
) -> ClerkTokenValidator:
    doc = {"keys": [rsa_public_jwk]}

    monkeypatch.setattr(
        JWKSClient,
        "_fetch_jwks_document",
        lambda _self: doc,
    )

    return ClerkTokenValidator(ISSUER, AUDIENCE, JWKSClient(ISSUER))


def test_validate_happy_path(
    validator: ClerkTokenValidator,
    rsa_private_pem: bytes,
) -> None:
    token = mint_clerk_token(rsa_private_pem=rsa_private_pem)
    claims = validator.validate(token)
    assert claims.user_id == "user_123"
    assert claims.org_id == "org_1"
    assert claims.org_role == "admin"
    assert claims.email == "dev@example.test"
    assert claims.raw["sub"] == "user_123"


def test_validate_expired_token(
    validator: ClerkTokenValidator,
    rsa_private_pem: bytes,
) -> None:
    token = mint_clerk_token(
        rsa_private_pem=rsa_private_pem,
        claims=expired_claims(),
    )

    with pytest.raises(InvalidTokenError) as exc:
        validator.validate(token)

    assert str(exc.value) == INVALID_TOKEN_MESSAGE


def test_validate_wrong_issuer(
    validator: ClerkTokenValidator,
    rsa_private_pem: bytes,
) -> None:
    token = mint_clerk_token(
        rsa_private_pem=rsa_private_pem,
        claims={"iss": "https://evil.example"},
    )

    with pytest.raises(InvalidTokenError) as exc:
        validator.validate(token)

    assert str(exc.value) == INVALID_TOKEN_MESSAGE


def test_validate_wrong_audience(
    validator: ClerkTokenValidator,
    rsa_private_pem: bytes,
) -> None:
    token = mint_clerk_token(
        rsa_private_pem=rsa_private_pem,
        claims={"aud": "https://other.consumer"},
    )

    with pytest.raises(InvalidTokenError) as exc:
        validator.validate(token)

    assert str(exc.value) == INVALID_TOKEN_MESSAGE


def test_validate_bad_signature(
    validator: ClerkTokenValidator,
    rsa_private_pem: bytes,
) -> None:
    token = mint_clerk_token(rsa_private_pem=rsa_private_pem)
    parts = token.split(".")
    parts[2] = parts[2][:-4] + "xxxx"
    mangled = ".".join(parts)

    with pytest.raises(InvalidTokenError) as exc:
        validator.validate(mangled)

    assert str(exc.value) == INVALID_TOKEN_MESSAGE


def test_validate_empty_token_raises(validator: ClerkTokenValidator) -> None:
    with pytest.raises(InvalidTokenError) as exc:
        validator.validate("   ")

    assert str(exc.value) == INVALID_TOKEN_MESSAGE


def test_validate_jwks_outage_opaque(
    monkeypatch: pytest.MonkeyPatch,
    rsa_private_pem: bytes,
) -> None:
    def failing(_self: JWKSClient) -> dict[str, Any]:
        raise ClerkUnreachableError("jwks outage")

    monkeypatch.setattr(JWKSClient, "_fetch_jwks_document", failing)

    validator = ClerkTokenValidator(ISSUER, AUDIENCE, JWKSClient(ISSUER))
    token = mint_clerk_token(rsa_private_pem=rsa_private_pem)

    with pytest.raises(InvalidTokenError) as exc:
        validator.validate(token)

    assert str(exc.value) == INVALID_TOKEN_MESSAGE


def test_validate_missing_sub_raises(
    validator: ClerkTokenValidator,
    rsa_private_pem: bytes,
) -> None:
    token = mint_clerk_token(
        rsa_private_pem=rsa_private_pem,
        claims={"sub": ""},
    )

    with pytest.raises(InvalidTokenError) as exc:
        validator.validate(token)

    assert str(exc.value) == INVALID_TOKEN_MESSAGE


def test_validate_missing_kid_header(
    monkeypatch: pytest.MonkeyPatch,
    rsa_public_jwk: dict[str, Any],
    rsa_private_pem: bytes,
) -> None:
    doc = {"keys": [rsa_public_jwk]}
    monkeypatch.setattr(
        JWKSClient,
        "_fetch_jwks_document",
        lambda _self: doc,
    )
    jwt_validator = ClerkTokenValidator(ISSUER, AUDIENCE, JWKSClient(ISSUER))

    now = int(time.time())
    body = {
        "sub": "user_123",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + 3600,
    }
    encoded = jwt.encode(
        body,
        rsa_private_pem.decode("utf-8"),
        algorithm="RS256",
        headers={"alg": "RS256"},
    )
    hdr = jwt.get_unverified_header(encoded)
    assert "kid" not in hdr

    with pytest.raises(InvalidTokenError) as exc:
        jwt_validator.validate(encoded)

    assert str(exc.value) == INVALID_TOKEN_MESSAGE


def test_validate_unknown_kid_opaque(
    monkeypatch: pytest.MonkeyPatch,
    rsa_public_jwk: dict[str, Any],
    rsa_private_pem: bytes,
) -> None:
    doc = {"keys": [rsa_public_jwk]}
    monkeypatch.setattr(
        JWKSClient,
        "_fetch_jwks_document",
        lambda _self: doc,
    )
    bad_validator = ClerkTokenValidator(ISSUER, AUDIENCE, JWKSClient(ISSUER))
    token = mint_clerk_token(
        rsa_private_pem=rsa_private_pem,
        headers={"kid": "nope", "alg": "RS256"},
    )

    with pytest.raises(InvalidTokenError) as exc:
        bad_validator.validate(token)

    assert str(exc.value) == INVALID_TOKEN_MESSAGE


def test_validate_missing_exp_claim_opaque(
    monkeypatch: pytest.MonkeyPatch,
    rsa_public_jwk: dict[str, Any],
    rsa_private_pem: bytes,
) -> None:
    doc = {"keys": [rsa_public_jwk]}
    monkeypatch.setattr(
        JWKSClient,
        "_fetch_jwks_document",
        lambda _self: doc,
    )
    strict = ClerkTokenValidator(ISSUER, AUDIENCE, JWKSClient(ISSUER))
    now = int(time.time())
    body = {
        "sub": "user_abc",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
    }
    token = jwt.encode(
        body,
        rsa_private_pem.decode("utf-8"),
        algorithm="RS256",
        headers={"kid": RSA_KID, "alg": "RS256"},
    )

    with pytest.raises(InvalidTokenError) as exc:
        strict.validate(token)

    assert str(exc.value) == INVALID_TOKEN_MESSAGE


def test_validate_missing_iat_claim_opaque(
    monkeypatch: pytest.MonkeyPatch,
    rsa_public_jwk: dict[str, Any],
    rsa_private_pem: bytes,
) -> None:
    doc = {"keys": [rsa_public_jwk]}
    monkeypatch.setattr(
        JWKSClient,
        "_fetch_jwks_document",
        lambda _self: doc,
    )
    strict = ClerkTokenValidator(ISSUER, AUDIENCE, JWKSClient(ISSUER))
    now = int(time.time())
    body = {
        "sub": "user_abc",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "exp": now + 600,
    }
    token = jwt.encode(
        body,
        rsa_private_pem.decode("utf-8"),
        algorithm="RS256",
        headers={"kid": RSA_KID, "alg": "RS256"},
    )

    with pytest.raises(InvalidTokenError) as exc:
        strict.validate(token)

    assert str(exc.value) == INVALID_TOKEN_MESSAGE
