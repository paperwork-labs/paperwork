"""JWKS fetcher + JWT verifier for Clerk-issued tokens.

Uses python-jose for JWT validation (already in apis/brain/requirements.txt
and apis/filefree/requirements.txt). httpx is preferred for fetching JWKS but
this module falls back to urllib so the sidecar stays drop-in.

The cache is a per-process dict keyed by JWKS URL with a TTL — Clerk rotates
keys roughly every 24h so a 10-minute TTL keeps us within reasonable freshness
without hammering the JWKS endpoint.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

logger = logging.getLogger(__name__)


class ClerkAuthError(Exception):
    """Raised when token verification fails for any reason.

    Callers (FastAPI dependencies, middleware) should translate this into a
    401 response. We never leak the underlying jose error message to the
    client because some failure modes (e.g. ``InvalidAudienceError``) include
    config details that aren't useful to attackers.
    """


@dataclass(frozen=True)
class ClerkJwtConfig:
    """Static configuration for a Clerk JWT verifier.

    Attributes:
        issuer: Clerk Frontend API URL, e.g. ``https://clerk.filefree.ai``.
        audience: Optional ``aud`` claim to require. Clerk session tokens do
            not always include ``aud``; only set this when using a custom JWT
            template that asserts an audience.
        jwks_url: Override the JWKS URL. Defaults to
            ``{issuer}/.well-known/jwks.json``.
        leeway_seconds: Clock-skew tolerance applied to ``exp`` / ``nbf``.
        cache_ttl_seconds: How long fetched JWKS keys are cached. Default 10m.
    """

    issuer: str
    audience: Optional[str] = None
    jwks_url: Optional[str] = None
    leeway_seconds: int = 30
    cache_ttl_seconds: int = 600

    @property
    def resolved_jwks_url(self) -> str:
        if self.jwks_url:
            return self.jwks_url
        normalized = self.issuer.rstrip("/")
        return f"{normalized}/.well-known/jwks.json"


@dataclass
class _JwksCacheEntry:
    keys: Mapping[str, Any]
    fetched_at: float = field(default_factory=time.monotonic)


_jwks_cache: dict[str, _JwksCacheEntry] = {}
_jwks_lock = threading.Lock()


def _fetch_jwks(url: str, timeout: float = 5.0) -> Mapping[str, Any]:
    """Fetch the JWKS document. Falls back to urllib when httpx is missing."""
    try:
        import httpx  # type: ignore

        response = httpx.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except ModuleNotFoundError:
        pass
    except Exception as exc:
        raise ClerkAuthError(f"jwks fetch failed: {exc!s}") from exc

    request = urllib.request.Request(url, headers={"User-Agent": "paperwork-auth/0.2"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise ClerkAuthError(f"jwks fetch failed: {exc!s}") from exc

    try:
        return json.loads(payload)
    except ValueError as exc:
        raise ClerkAuthError(f"jwks parse failed: {exc!s}") from exc


def _get_cached_jwks(config: ClerkJwtConfig) -> Mapping[str, Any]:
    url = config.resolved_jwks_url
    with _jwks_lock:
        entry = _jwks_cache.get(url)
        if entry and (time.monotonic() - entry.fetched_at) < config.cache_ttl_seconds:
            return entry.keys

    fresh = _fetch_jwks(url)
    with _jwks_lock:
        _jwks_cache[url] = _JwksCacheEntry(keys=fresh)
    return fresh


def clear_jwks_cache() -> None:
    """Reset the JWKS cache. Primarily useful in tests."""
    with _jwks_lock:
        _jwks_cache.clear()


def verify_clerk_jwt(token: str, config: ClerkJwtConfig) -> Mapping[str, Any]:
    """Verify a Clerk JWT and return its claims.

    Raises ``ClerkAuthError`` on any failure (invalid signature, expired,
    issuer mismatch, malformed token).
    """
    if not token or not isinstance(token, str):
        raise ClerkAuthError("token is empty")

    try:
        from jose import jwt
        from jose.exceptions import JOSEError
    except ModuleNotFoundError as exc:
        raise ClerkAuthError(
            "python-jose is required: pip install 'python-jose[cryptography]'"
        ) from exc

    jwks = _get_cached_jwks(config)

    try:
        unverified_header = jwt.get_unverified_header(token)
    except Exception as exc:
        raise ClerkAuthError(f"malformed token header: {exc!s}") from exc

    kid = unverified_header.get("kid")
    if not kid:
        raise ClerkAuthError("token header missing kid")

    keys = jwks.get("keys", []) if isinstance(jwks, Mapping) else []
    matching_key = next((k for k in keys if k.get("kid") == kid), None)
    if matching_key is None:
        # One refresh attempt — Clerk may have rotated keys after our cache.
        clear_jwks_cache()
        jwks = _get_cached_jwks(config)
        keys = jwks.get("keys", []) if isinstance(jwks, Mapping) else []
        matching_key = next((k for k in keys if k.get("kid") == kid), None)
        if matching_key is None:
            raise ClerkAuthError(f"no matching jwk for kid={kid}")

    try:
        claims: Mapping[str, Any] = jwt.decode(
            token,
            matching_key,
            algorithms=[matching_key.get("alg", "RS256")],
            issuer=config.issuer.rstrip("/"),
            audience=config.audience,
            options={
                "verify_aud": config.audience is not None,
                "leeway": config.leeway_seconds,
            },
        )
    except JOSEError as exc:
        logger.warning("clerk jwt verify failed", extra={"reason": str(exc)})
        raise ClerkAuthError(f"jwt verification failed: {exc!s}") from exc

    return claims
