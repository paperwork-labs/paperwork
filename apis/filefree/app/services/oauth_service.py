"""OAuth token verification for Google and Apple social login.

Google: uses google-auth library to verify ID tokens server-side.
Apple: fetches Apple's JWKS and validates JWT with python-jose.

medallion: ops
"""

import time
from dataclasses import dataclass
from functools import partial

import anyio
import httpx
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token as google_id_token
from jose import jwt as jose_jwt

from app.config import settings
from app.utils.exceptions import AppException, UnauthorizedError

_apple_jwks_cache: dict | None = None
_apple_jwks_fetched_at: float = 0
APPLE_JWKS_TTL = 3600  # 1 hour
APPLE_JWKS_TIMEOUT = 10.0  # seconds


@dataclass
class OAuthUser:
    email: str
    name: str | None
    provider_id: str


async def verify_google_token(id_token: str) -> OAuthUser:
    """Verify a Google ID token and extract user info.

    The token comes from Google Identity Services (One-Tap or button).
    We verify it server-side using google-auth, checking:
    - Signature (via Google's public keys)
    - Issuer (accounts.google.com)
    - Audience (our GOOGLE_CLIENT_ID)
    - Expiration

    google-auth uses synchronous requests internally, so we offload
    to a worker thread to avoid blocking the event loop.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise UnauthorizedError("Google Sign In is not configured")

    try:
        idinfo = await anyio.to_thread.run_sync(
            partial(
                google_id_token.verify_oauth2_token,
                id_token,
                GoogleRequest(),
                settings.GOOGLE_CLIENT_ID,
            )
        )
    except ValueError as err:
        raise UnauthorizedError("Invalid Google token") from err

    email = idinfo.get("email")
    if not email:
        raise UnauthorizedError("Google account has no email address")

    if not idinfo.get("email_verified", False):
        raise UnauthorizedError("Google email is not verified")

    return OAuthUser(
        email=email.lower(),
        name=idinfo.get("name"),
        provider_id=idinfo["sub"],
    )


async def _get_apple_jwks() -> dict:
    """Fetch and cache Apple's public JWKS for token verification."""
    global _apple_jwks_cache, _apple_jwks_fetched_at

    if _apple_jwks_cache and (time.time() - _apple_jwks_fetched_at) < APPLE_JWKS_TTL:
        return _apple_jwks_cache

    try:
        async with httpx.AsyncClient(timeout=APPLE_JWKS_TIMEOUT) as client:
            resp = await client.get("https://appleid.apple.com/auth/keys")
            resp.raise_for_status()
            _apple_jwks_cache = resp.json()
            _apple_jwks_fetched_at = time.time()
            return _apple_jwks_cache
    except httpx.HTTPError as err:
        raise AppException("Apple Sign In is temporarily unavailable", status_code=503) from err


async def verify_apple_token(id_token: str, user_info: dict | None = None) -> OAuthUser:
    """Verify an Apple ID token and extract user info.

    Apple's flow: the JS SDK returns an id_token (JWT). User info (name, email)
    is only provided on the FIRST authorization. On subsequent logins, only the
    id_token is available -- we extract email from the token claims.
    """
    if not settings.APPLE_CLIENT_ID:
        raise UnauthorizedError("Apple Sign In is not configured")

    try:
        jwks = await _get_apple_jwks()
        header = jose_jwt.get_unverified_header(id_token)

        matching_key = None
        for key in jwks.get("keys", []):
            if key["kid"] == header.get("kid"):
                matching_key = key
                break

        if not matching_key:
            raise UnauthorizedError("Apple token key not found")

        claims = jose_jwt.decode(
            id_token,
            matching_key,
            algorithms=["RS256"],
            audience=settings.APPLE_CLIENT_ID,
            issuer="https://appleid.apple.com",
        )
    except Exception as err:
        if isinstance(err, (UnauthorizedError, AppException)):
            raise
        raise UnauthorizedError("Invalid Apple token") from err

    email = claims.get("email")
    if not email:
        raise UnauthorizedError("Apple account has no email address")

    name = None
    if user_info:
        raw_name = user_info.get("name")
        if isinstance(raw_name, dict):
            first = raw_name.get("firstName", "")
            last = raw_name.get("lastName", "")
            name = f"{first} {last}".strip() or None

    return OAuthUser(
        email=email.lower(),
        name=name,
        provider_id=claims["sub"],
    )
