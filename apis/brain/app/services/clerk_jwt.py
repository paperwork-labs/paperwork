"""Verify Clerk JWTs for Brain HTTP auth (WS-76 PR-13).

medallion: ops
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import httpx
from jose import jwk, jwt
from jose.exceptions import JWTError

from app.config import Settings  # noqa: TC001

logger = logging.getLogger(__name__)


class ClerkJwtConfigurationError(RuntimeError):
    """Raised when JWT verification is misconfigured."""


@lru_cache(maxsize=4)
def _jwks_payload(url: str) -> dict[str, Any]:
    resp = httpx.get(url, timeout=10.0)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise ClerkJwtConfigurationError("JWKS response must be a JSON object")
    return data


def clerk_jwt_claims(token: str, cfg: Settings) -> dict[str, Any]:
    """Decode and verify *token*, returning claim dict (includes ``sub``)."""
    if cfg.BRAIN_ALLOW_UNVERIFIED_CLERK_JWT:
        claims = jwt.get_unverified_claims(token)
        if not isinstance(claims, dict):
            raise JWTError("Unverified claims are not an object")
        return claims

    jwks_url = cfg.CLERK_JWKS_URL.strip()
    if not jwks_url:
        raise ClerkJwtConfigurationError(
            "CLERK_JWKS_URL is required for Clerk JWT verification "
            "(or set BRAIN_ALLOW_UNVERIFIED_CLERK_JWT=true for tests only)."
        )

    try:
        header = jwt.get_unverified_header(token)
    except JWTError:
        raise
    kid = header.get("kid")
    alg = header.get("alg")
    if not isinstance(kid, str) or not kid:
        raise JWTError("JWT header missing kid")
    if alg != "RS256":
        raise JWTError(f"Unsupported JWT alg: {alg!r}")

    payload = _jwks_payload(jwks_url)
    keys_raw = payload.get("keys")
    if not isinstance(keys_raw, list):
        raise JWTError("JWKS payload missing keys array")

    rsa_dict: dict[str, Any] | None = None
    for entry in keys_raw:
        if isinstance(entry, dict) and entry.get("kid") == kid:
            rsa_dict = entry
            break
    if rsa_dict is None:
        raise JWTError(f"No JWKS key for kid={kid!r}")

    public_key = jwk.construct(rsa_dict)

    decode_kw: dict[str, Any] = {"algorithms": ["RS256"]}
    issuer = cfg.CLERK_JWT_ISSUER.strip()
    audience = cfg.CLERK_JWT_AUDIENCE.strip()
    options: dict[str, bool] = {}
    if issuer:
        decode_kw["issuer"] = issuer
    else:
        options["verify_iss"] = False
    if audience:
        decode_kw["audience"] = audience
    else:
        options["verify_aud"] = False
    if options:
        decode_kw["options"] = options

    try:
        claims = jwt.decode(token, public_key.key, **decode_kw)
    except JWTError:
        logger.info("Clerk JWT decode failed", exc_info=True)
        raise
    if not isinstance(claims, dict):
        raise JWTError("Decoded JWT claims are not an object")
    return claims
