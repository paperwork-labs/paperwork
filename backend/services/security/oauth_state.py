from __future__ import annotations

"""medallion: ops"""
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
import jwt

from backend.config import settings


class OAuthStateService:
    """
    Issues and validates short-lived JWT 'state' tokens for OAuth flows.

    Uses OAUTH_STATE_SECRET (shared across environments) so that a state JWT
    issued by the dev backend can be verified by the production callback.
    Falls back to SECRET_KEY when OAUTH_STATE_SECRET is not configured.
    """

    def __init__(self, secret: str | None = None, algorithm: str = "HS256"):
        self._secret = (
            secret or settings.OAUTH_STATE_SECRET or settings.SECRET_KEY
        ).encode("utf-8")
        self._alg = algorithm

    def issue_state(
        self,
        user_id: int,
        account_id: int,
        code_verifier: Optional[str] = None,
        minutes_valid: int = 10,
    ) -> str:
        now = datetime.now(timezone.utc)
        payload: Dict[str, Any] = {
            "sub": "oauth_state",
            "uid": user_id,
            "aid": account_id,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=minutes_valid)).timestamp()),
            "nbf": int(now.timestamp()),
        }
        if code_verifier:
            payload["cv"] = code_verifier
        return jwt.encode(payload, self._secret, algorithm=self._alg)

    def validate_state(self, token: str) -> Dict[str, Any]:
        data = jwt.decode(token, self._secret, algorithms=[self._alg])
        if data.get("sub") != "oauth_state":
            raise ValueError("Invalid state subject")
        if "uid" not in data or "aid" not in data:
            raise ValueError("State missing required fields")
        return data


oauth_state_service = OAuthStateService()


