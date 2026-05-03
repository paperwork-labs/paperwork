"""Clerk bearer JWT validation built on JWKS-backed signing keys."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from clerk_auth.errors import (
    INVALID_TOKEN_MESSAGE,
    ClerkUnreachableError,
    InvalidTokenError,
)
from clerk_auth.jwks import JWKSClient

logger = logging.getLogger(__name__)


class ClerkClaims(BaseModel):
    """Verified Clerk bearer token claims surfaced to handlers."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    user_id: str = Field(
        ...,
        description="Subject claim identifying the Clerk user (`sub`).",
    )
    org_id: str | None = None
    org_role: str | None = None
    email: str | None = None
    expires_at: datetime = Field(..., description="Token expiry (`exp`) in UTC.")
    issued_at: datetime = Field(..., description="Token issued-at (`iat`) in UTC.")
    raw: dict[str, Any]


class ClerkTokenValidator:
    """Verify bearer JWTs minted by Clerk."""

    def __init__(
        self,
        issuer: str,
        audience: str,
        jwks_client: JWKSClient | None = None,
        *,
        leeway_seconds: int = 30,
    ) -> None:
        self._issuer = issuer.rstrip("/")
        self._audience = audience
        self._jwks = jwks_client if jwks_client is not None else JWKSClient(issuer)
        self._leeway_seconds = leeway_seconds

    def validate(self, token: str) -> ClerkClaims:
        """Verify signing key, expiry, issuer, audience, and core claims."""

        try:
            from jose import jwt
            from jose.exceptions import JOSEError
        except ModuleNotFoundError as exc:  # pragma: no cover - env guardrail
            raise InvalidTokenError(INVALID_TOKEN_MESSAGE) from exc

        if not isinstance(token, str) or not token.strip():
            raise InvalidTokenError(INVALID_TOKEN_MESSAGE)

        trimmed = token.strip()

        try:
            header = jwt.get_unverified_header(trimmed)
        except Exception:
            logger.debug("clerk token rejected: unreadable JWT header")
            raise InvalidTokenError(INVALID_TOKEN_MESSAGE) from None

        kid_any = header.get("kid") if isinstance(header, dict) else None
        if not isinstance(kid_any, str) or not kid_any:
            raise InvalidTokenError(INVALID_TOKEN_MESSAGE)

        try:
            jwk_dict = self._jwks.get_signing_key(kid_any)
        except ClerkUnreachableError:
            logger.warning("clerk token rejected: JWKS unavailable for kid=%s", kid_any)
            raise InvalidTokenError(INVALID_TOKEN_MESSAGE) from None

        try:
            claims_any: Any = jwt.decode(
                trimmed,
                jwk_dict,
                algorithms=[str(jwk_dict.get("alg", "RS256"))],
                issuer=self._issuer,
                audience=self._audience,
                options={
                    "verify_aud": True,
                    "leeway": self._leeway_seconds,
                },
            )
        except JOSEError:
            logger.warning("clerk token rejected during signature/claim verification")
            raise InvalidTokenError(INVALID_TOKEN_MESSAGE) from None

        if not isinstance(claims_any, dict):
            raise InvalidTokenError(INVALID_TOKEN_MESSAGE) from None

        claims_raw: dict[str, Any] = dict(claims_any)

        sub_any = claims_raw.get("sub")
        if not isinstance(sub_any, str) or not sub_any:
            raise InvalidTokenError(INVALID_TOKEN_MESSAGE)

        expires_at = _require_utc_timestamp(claims_raw, "exp")
        issued_at = _require_utc_timestamp(claims_raw, "iat")

        org_id_any = claims_raw.get("org_id")
        org_role_any = claims_raw.get("org_role")
        email_any = claims_raw.get("email")

        return ClerkClaims(
            user_id=sub_any,
            org_id=_optional_str(org_id_any),
            org_role=_optional_str(org_role_any),
            email=_optional_str(email_any),
            expires_at=expires_at,
            issued_at=issued_at,
            raw=claims_raw,
        )


def _optional_str(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _require_utc_timestamp(claims: Mapping[str, Any], key: str) -> datetime:
    val = claims.get(key)
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=UTC)
        return val.astimezone(UTC)
    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(float(val), UTC)
    raise InvalidTokenError(INVALID_TOKEN_MESSAGE) from None
