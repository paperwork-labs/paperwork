from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import uuid
import jwt

from backend.config import settings

JWT_ALGORITHM = "HS256"


def get_secret_key() -> str:
    return getattr(settings, "SECRET_KEY", "fallback-secret-key-for-development")


def create_access_token(claims: Dict[str, Any], expires: Optional[timedelta] = None) -> str:
    payload = dict(claims)
    exp = datetime.now(timezone.utc) + (expires or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload["exp"] = exp
    payload["type"] = "access"
    return jwt.encode(payload, get_secret_key(), algorithm=JWT_ALGORITHM)


def create_refresh_token(claims: Dict[str, Any], family: Optional[str] = None) -> str:
    payload = dict(claims)
    payload["exp"] = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload["type"] = "refresh"
    payload["family"] = family or str(uuid.uuid4())
    payload["jti"] = str(uuid.uuid4())
    return jwt.encode(payload, get_secret_key(), algorithm=JWT_ALGORITHM)


def decode_token(token: str, expected_type: str = "access") -> Dict[str, Any]:
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
