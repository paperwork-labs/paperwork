import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.config import settings

JWT_ALGORITHM = "HS256"


def get_secret_key() -> str:
    return getattr(settings, "SECRET_KEY", "fallback-secret-key-for-development")


def create_access_token(claims: dict[str, Any], expires: timedelta | None = None) -> str:
    payload = dict(claims)
    exp = datetime.now(UTC) + (
        expires or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload["exp"] = exp
    payload["type"] = "access"
    return jwt.encode(payload, get_secret_key(), algorithm=JWT_ALGORITHM)


def create_refresh_token(claims: dict[str, Any], family: str | None = None) -> str:
    payload = dict(claims)
    payload["exp"] = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload["type"] = "refresh"
    payload["family"] = family or str(uuid.uuid4())
    payload["jti"] = str(uuid.uuid4())
    return jwt.encode(payload, get_secret_key(), algorithm=JWT_ALGORITHM)


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    """Decode a JWT and enforce token type.

    Args:
        expected_type: 'access', 'refresh', or None to skip type check.
    """
    payload = jwt.decode(token, get_secret_key(), algorithms=[JWT_ALGORITHM])
    if expected_type and payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(
            f"Expected token type '{expected_type}', got '{payload.get('type')}'"
        )
    return payload
