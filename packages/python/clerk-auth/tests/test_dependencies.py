"""FastAPI dependency integration tests."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from clerk_auth.dependencies import optional_clerk_user, require_clerk_user
from clerk_auth.errors import INVALID_TOKEN_MESSAGE
from clerk_auth.jwks import JWKSClient
from clerk_auth.validator import ClerkClaims, ClerkTokenValidator
from tests.support import AUDIENCE, ISSUER, mint_clerk_token


@pytest.fixture()
def api_client(
    monkeypatch: pytest.MonkeyPatch,
    rsa_public_jwk: dict[str, Any],
) -> TestClient:
    doc = {"keys": [rsa_public_jwk]}
    monkeypatch.setattr(
        JWKSClient,
        "_fetch_jwks_document",
        lambda _self: doc,
    )

    jwt_validator = ClerkTokenValidator(ISSUER, AUDIENCE, JWKSClient(ISSUER))
    app = FastAPI()

    secured_dep = Depends(require_clerk_user(jwt_validator))
    optional_dep = Depends(optional_clerk_user(jwt_validator))

    @app.get("/secure")
    def secure(user: ClerkClaims = secured_dep) -> dict[str, Any]:
        return {"user_id": user.user_id}

    @app.get("/optional")
    def optional(
        user: ClerkClaims | None = optional_dep,
    ) -> dict[str, Any]:
        return {"present": bool(user), "sub": user.user_id if user else None}

    return TestClient(app)


def test_requires_bearer_returns_401_without_header(api_client: TestClient) -> None:
    response = api_client.get("/secure")
    assert response.status_code == 401
    assert response.json()["detail"] == INVALID_TOKEN_MESSAGE


def test_requires_bearer_returns_401_on_bad_token(
    api_client: TestClient,
    rsa_private_pem: bytes,
) -> None:
    token = mint_clerk_token(
        rsa_private_pem=rsa_private_pem,
        claims={"iss": "https://evil.example"},
    )

    response = api_client.get(
        "/secure",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == INVALID_TOKEN_MESSAGE


def test_requires_bearer_returns_200_with_claims(
    api_client: TestClient,
    rsa_private_pem: bytes,
) -> None:
    token = mint_clerk_token(rsa_private_pem=rsa_private_pem)

    response = api_client.get(
        "/secure",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"user_id": "user_123"}


def test_optional_user_returns_none(api_client: TestClient) -> None:
    response = api_client.get("/optional")
    assert response.status_code == 200
    body = response.json()
    assert body["present"] is False
    assert body["sub"] is None


def test_optional_user_rejects_invalid_token(
    api_client: TestClient,
    rsa_private_pem: bytes,
) -> None:
    token = mint_clerk_token(
        rsa_private_pem=rsa_private_pem,
        claims={"aud": "https://oops"},
    )

    response = api_client.get(
        "/optional",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_requires_scheme_other_than_bearer_returns_401(
    api_client: TestClient,
) -> None:
    response = api_client.get(
        "/secure",
        headers={"Authorization": "Digest realm=noop"},
    )
    assert response.status_code == 401


def test_requires_well_formed_scheme_tokens(api_client: TestClient) -> None:
    malformed = api_client.get(
        "/secure",
        headers={"Authorization": "Bearer"},
    )
    assert malformed.status_code == 401

    missing_scheme = api_client.get(
        "/secure",
        headers={"Authorization": "notokent"},
    )
    assert missing_scheme.status_code == 401


def test_optional_ignores_non_bearer_scheme_tokens(api_client: TestClient) -> None:
    """Values without explicit ``Bearer`` should behave like an absent credential."""

    response = api_client.get(
        "/optional",
        headers={"Authorization": "token-without-space"},
    )
    assert response.status_code == 200
    assert response.json()["present"] is False
