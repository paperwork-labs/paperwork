"""Clerk JWT verification utilities for FastAPI services.

This package is the canonical uv workspace location at
``packages/python/clerk-auth``. The historical ``paperwork_auth`` module under
``packages/auth-clerk/src/python/`` remains in place for existing Docker-based
installs until Wave K10-K13 migrates each backend.
"""

from clerk_auth.dependencies import optional_clerk_user, require_clerk_user
from clerk_auth.errors import (
    INVALID_TOKEN_MESSAGE,
    ClerkUnreachableError,
    InvalidTokenError,
)
from clerk_auth.jwks import JWKSClient
from clerk_auth.validator import ClerkClaims, ClerkTokenValidator

__all__ = [
    "INVALID_TOKEN_MESSAGE",
    "ClerkClaims",
    "ClerkTokenValidator",
    "ClerkUnreachableError",
    "InvalidTokenError",
    "JWKSClient",
    "optional_clerk_user",
    "require_clerk_user",
]

__version__ = "0.1.0"
