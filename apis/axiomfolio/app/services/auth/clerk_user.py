"""Resolve ``User`` rows from verified Clerk session JWT claims (Track B5).

medallion: ops
"""

from __future__ import annotations

import logging
import re
from typing import Any, Mapping, Optional

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User, UserRole
from paperwork_auth.jwks import ClerkAuthError, ClerkJwtConfig, verify_clerk_jwt

logger = logging.getLogger(__name__)


def clerk_jwt_config() -> ClerkJwtConfig:
    issuer = (settings.CLERK_JWT_ISSUER or "").strip()
    if not issuer:
        raise ClerkAuthError("CLERK_JWT_ISSUER is not configured")
    aud = (settings.CLERK_JWT_AUDIENCE or "").strip()
    return ClerkJwtConfig(issuer=issuer, audience=aud or None)


def verify_bearer_clerk_token(token: str) -> Mapping[str, Any]:
    return verify_clerk_jwt(token, clerk_jwt_config())


def _email_from_claims(claims: Mapping[str, Any]) -> Optional[str]:
    for key in ("email", "primary_email_address"):
        raw = claims.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip().lower()
    return None


def _fetch_clerk_primary_email(clerk_user_id: str) -> Optional[str]:
    secret = settings.CLERK_SECRET_KEY
    if not secret:
        return None
    base = settings.CLERK_API_URL.rstrip("/")
    url = f"{base}/v1/users/{clerk_user_id}"
    try:
        r = httpx.get(
            url,
            headers={"Authorization": f"Bearer {secret}"},
            timeout=10.0,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        logger.warning("clerk backend api user fetch failed: %s", exc)
        return None

    primary_id = data.get("primary_email_address_id")
    for row in data.get("email_addresses") or []:
        if not isinstance(row, dict):
            continue
        addr = row.get("email_address")
        if not isinstance(addr, str) or not addr.strip():
            continue
        if primary_id and row.get("id") == primary_id:
            return addr.strip().lower()
    # Fallback: first verified email
    for row in data.get("email_addresses") or []:
        if not isinstance(row, dict):
            continue
        if row.get("verification", {}).get("status") != "verified":
            continue
        addr = row.get("email_address")
        if isinstance(addr, str) and addr.strip():
            return addr.strip().lower()
    return None


def _unique_username(db: Session, base: str) -> str:
    slug = re.sub(r"[^a-z0-9_]", "_", base.lower())[:40] or "user"
    candidate = slug[:50]
    n = 0
    while db.query(User.id).filter(User.username == candidate).first():
        n += 1
        suffix = f"_{n}"
        candidate = f"{slug[: 50 - len(suffix)]}{suffix}"
    return candidate


def get_or_create_user_for_clerk(db: Session, claims: Mapping[str, Any]) -> User:
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub:
        raise ClerkAuthError("token missing sub")

    user = db.query(User).filter(User.clerk_user_id == sub).first()
    if user:
        return user

    email = _email_from_claims(claims)
    if not email:
        email = _fetch_clerk_primary_email(sub)

    if email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.clerk_user_id = sub
            if user.oauth_provider is None:
                user.oauth_provider = "clerk"
            db.commit()
            db.refresh(user)
            return user

    if not email:
        raise ClerkAuthError(
            "cannot provision user: add email to the Clerk session JWT or set CLERK_SECRET_KEY"
        )

    username = _unique_username(db, email.split("@")[0])
    user = User(
        username=username,
        email=email,
        password_hash=None,
        clerk_user_id=sub,
        oauth_provider="clerk",
        oauth_id=sub,
        role=UserRole.ANALYST,
        is_active=True,
        is_verified=True,
        is_approved=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("provisioned user id=%s for clerk_user_id=%s", user.id, sub)
    return user
