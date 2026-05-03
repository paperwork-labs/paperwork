"""Errors for JWKS retrieval and JWT validation."""


class InvalidTokenError(Exception):
    """The presented bearer token could not be accepted.

    Raised for every token validation failure with a stable, non-specific
    message so clients cannot distinguish signature vs expiry vs issuer
    mismatch from the exception text alone.
    """


INVALID_TOKEN_MESSAGE = "invalid token"


class ClerkUnreachableError(Exception):
    """JWKS discovery failed and no degraded cache exists for the key id."""
