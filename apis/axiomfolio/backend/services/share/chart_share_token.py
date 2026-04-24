"""
Signed JWT tokens for public chart share links (C1 / #360).

These tokens are NOT login JWTs: ``sub`` is ``chart_share`` and ``scope`` is
``chart-share`` (verified on decode so OAuth state or auth tokens are rejected).
Uses ``OAUTH_STATE_SECRET`` (with ``SECRET_KEY`` fallback) as the HS256 key,
matching `backend.services.security.oauth_state` configuration.

medallion: ops
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional, Sequence

import jwt

from backend.config import settings

logger = logging.getLogger(__name__)

CHART_SHARE_SUB = "chart_share"
CHART_SHARE_SCOPE = "chart-share"
CHART_TOKEN_VERSION = 1


def _signing_key() -> bytes:
    raw: Optional[str] = settings.OAUTH_STATE_SECRET or settings.SECRET_KEY
    if not raw or not str(raw).strip():
        raise RuntimeError(
            "OAUTH_STATE_SECRET (or SECRET_KEY) must be set to issue chart share tokens"
        )
    return str(raw).encode("utf-8")


def create_chart_share_token(
    *,
    user_id: int,
    symbol: str,
    period: str = "1y",
    indicators: Optional[Sequence[str]] = None,
) -> str:
    """Return an HS256 JWT expiring in 30 days. Payload includes ``uid`` for audit only."""
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=30)
    ind_list: List[str] = [str(x) for x in (indicators or []) if str(x).strip()][:32]
    payload: dict[str, Any] = {
        "sub": CHART_SHARE_SUB,
        "scope": CHART_SHARE_SCOPE,
        "v": CHART_TOKEN_VERSION,
        "uid": int(user_id),
        "symbol": symbol.strip().upper(),
        "period": period,
        "indicators": ind_list,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, _signing_key(), algorithm="HS256")


def decode_chart_share_token(token: str) -> dict[str, Any]:
    """
    Verify signature, expiry, and scope. Raises jwt exceptions or ValueError
    for wrong ``sub`` / ``scope`` / version.
    """
    data: dict[str, Any] = jwt.decode(
        token,
        _signing_key(),
        algorithms=["HS256"],
        options={"require": ["exp", "iat", "sub"]},
    )
    if data.get("sub") != CHART_SHARE_SUB:
        raise ValueError("Invalid chart share subject")
    if data.get("scope") != CHART_SHARE_SCOPE:
        raise ValueError("Invalid chart share scope")
    if int(data.get("v", 0)) != CHART_TOKEN_VERSION:
        raise ValueError("Unsupported chart share token version")
    if not data.get("symbol"):
        raise ValueError("Chart share token missing symbol")
    return data
