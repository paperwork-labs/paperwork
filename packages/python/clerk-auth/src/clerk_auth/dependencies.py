"""FastAPI dependencies for Clerk bearer authentication."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Header, HTTPException

from clerk_auth.errors import INVALID_TOKEN_MESSAGE, InvalidTokenError
from clerk_auth.validator import ClerkClaims, ClerkTokenValidator


def _bearer_from_authorization_header(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    parts = value.strip().split(" ", 1)
    if len(parts) != 2:
        return None
    scheme, token = parts[0].lower(), parts[1].strip()
    if scheme != "bearer" or not token:
        return None
    return token


def require_clerk_user(
    validator: ClerkTokenValidator,
) -> Callable[..., ClerkClaims]:
    """Return a FastAPI dependency that requires a valid ``Authorization`` header."""

    def _dependency(
        authorization: str | None = Header(
            default=None,
            alias="Authorization",
        ),
    ) -> ClerkClaims:
        token = _bearer_from_authorization_header(authorization)
        if token is None:
            raise HTTPException(status_code=401, detail=INVALID_TOKEN_MESSAGE)

        try:
            return validator.validate(token)
        except InvalidTokenError:
            raise HTTPException(status_code=401, detail=INVALID_TOKEN_MESSAGE) from None

    return _dependency


def optional_clerk_user(
    validator: ClerkTokenValidator,
) -> Callable[..., ClerkClaims | None]:
    """Like :func:`require_clerk_user` but returns ``None`` when no bearer token."""

    def _dependency(
        authorization: str | None = Header(
            default=None,
            alias="Authorization",
        ),
    ) -> ClerkClaims | None:
        token = _bearer_from_authorization_header(authorization)
        if token is None:
            return None

        try:
            return validator.validate(token)
        except InvalidTokenError:
            raise HTTPException(status_code=401, detail=INVALID_TOKEN_MESSAGE) from None

    return _dependency
