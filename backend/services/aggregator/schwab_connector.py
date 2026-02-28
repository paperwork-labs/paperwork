from __future__ import annotations

import urllib.parse
from typing import Dict, Any, Optional
import httpx

from backend.config import settings


class SchwabConnector:
    """
    Minimal Schwab OAuth connector:
    - Builds authorization URL (read scopes by default)
    - Exchanges auth code for tokens
    - Refreshes tokens
    """

    AUTH_BASE = "https://api.schwabapi.com/v1/oauth/authorize"
    TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        timeout_seconds: int = 20,
    ):
        self.client_id = client_id or settings.SCHWAB_CLIENT_ID
        self.client_secret = client_secret or settings.SCHWAB_CLIENT_SECRET
        self.redirect_uri = redirect_uri or settings.SCHWAB_REDIRECT_URI
        self.timeout_seconds = timeout_seconds
        # Allow override of authorization base URL from settings
        self.auth_base = getattr(settings, "SCHWAB_AUTH_BASE", None) or self.AUTH_BASE
        self.client_id_suffix = getattr(settings, "SCHWAB_CLIENT_ID_SUFFIX", None) or ""

    def get_authorization_url(self, state: str, trading: bool = False) -> str:
        if not self.client_id or not self.redirect_uri:
            raise ValueError("Schwab OAuth not configured")
        # OAuth2 scopes should be space-delimited per spec
        # Schwab Accounts & Trading typically expects both read and trade scopes available.
        # Request both; trading execution is still gated by server feature flags.
        scopes = ["read", "trade"]
        client_id_to_use = f"{self.client_id}{self.client_id_suffix}" if self.client_id_suffix else self.client_id
        query = {
            "response_type": "code",
            "client_id": client_id_to_use,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
        }
        return f"{self.auth_base}?{urllib.parse.urlencode(query)}"

    async def exchange_code_for_tokens(self, code: str, code_verifier: Optional[str] = None) -> Dict[str, Any]:
        if not (self.client_id and self.client_secret and self.redirect_uri):
            raise ValueError("Schwab OAuth not configured")
        data: Dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        if code_verifier:
            data["code_verifier"] = code_verifier
        auth = httpx.BasicAuth(self.client_id, self.client_secret)
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            res = await client.post(self.TOKEN_URL, data=data, auth=auth)
            if res.status_code >= 400:
                raise RuntimeError(f"Token exchange failed: {res.status_code} {res.text[:200]}")
            return res.json()

    async def refresh_tokens(self, refresh_token: str) -> Dict[str, Any]:
        if not (self.client_id and self.client_secret and self.redirect_uri):
            raise ValueError("Schwab OAuth not configured")
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        auth = httpx.BasicAuth(self.client_id, self.client_secret)
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            res = await client.post(self.TOKEN_URL, data=data, auth=auth)
            if res.status_code >= 400:
                raise RuntimeError(f"Token refresh failed: {res.status_code} {res.text[:200]}")
            return res.json()


