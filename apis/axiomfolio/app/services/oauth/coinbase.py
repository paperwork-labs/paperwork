"""Coinbase OAuth 2.0 adapter (retail Coinbase consumer / Coinbase App API).

Authorization-code flow against Coinbase's hosted login and token endpoints.
Bronze sync uses the v2 data API (``GET /v2/accounts``, per-account
transactions) with read-only scopes.

See D130 in ``docs/KNOWLEDGE.md`` for the bronze-plus-OAuth contract.

medallion: ops
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import requests

from app.config import settings

from .base import (
    OAuthBrokerAdapter,
    OAuthCallbackContext,
    OAuthError,
    OAuthInitiateResult,
    OAuthTokens,
)

logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://login.coinbase.com/oauth2/auth"
TOKEN_URL = "https://api.coinbase.com/oauth/token"
API_BASE = "https://api.coinbase.com"

READ_ONLY_SCOPES = "wallet:accounts:read wallet:transactions:read wallet:user:read"

_ACCESS_TOKEN_DEFAULT_LIFETIME_S = 7200
_REFRESH_TOKEN_DEFAULT_LIFETIME_S = 30 * 24 * 3600


def _classify_status(status: int) -> bool:
    """Return ``permanent=True`` for 4xx (except 429), False for 5xx / 429."""

    if status == 429:
        return False
    return 400 <= status < 500


def _parse_expires_at(expires_in: Any | None, default_s: int) -> datetime:
    try:
        seconds = int(expires_in) if expires_in is not None else default_s
    except (TypeError, ValueError):
        seconds = default_s
    if seconds <= 0:
        seconds = default_s
    return datetime.now(UTC) + timedelta(seconds=seconds)


class CoinbaseOAuthAdapter(OAuthBrokerAdapter):
    """OAuth 2.0 adapter for Coinbase (read-only wallet scopes)."""

    broker_id = "coinbase"
    environment = "live"

    def __init__(
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        timeout_s: float | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self._client_id = client_id or getattr(settings, "COINBASE_CLIENT_ID", None)
        self._client_secret = client_secret or getattr(settings, "COINBASE_CLIENT_SECRET", None)
        self._timeout_s = (
            timeout_s
            if timeout_s is not None
            else getattr(settings, "COINBASE_OAUTH_REQUEST_TIMEOUT_S", 15.0)
        )
        self._session = session or requests.Session()

    def _require_credentials(self) -> tuple[str, str]:
        if not self._client_id or not self._client_secret:
            raise OAuthError(
                "Coinbase credentials not configured (set COINBASE_CLIENT_ID "
                "and COINBASE_CLIENT_SECRET)",
                permanent=True,
                broker=self.broker_id,
            )
        return self._client_id, self._client_secret

    def _post_token(self, payload: dict[str, str]) -> dict[str, Any]:
        client_id, client_secret = self._require_credentials()
        body = dict(payload)
        body["client_id"] = client_id
        body["client_secret"] = client_secret
        try:
            resp = self._session.post(
                TOKEN_URL,
                data=body,
                headers={"Accept": "application/json"},
                timeout=self._timeout_s,
            )
        except requests.RequestException as exc:
            raise OAuthError(
                f"network failure calling Coinbase token endpoint: {exc}",
                permanent=False,
                broker=self.broker_id,
            ) from exc

        status = resp.status_code
        if status >= 400:
            raise OAuthError(
                f"Coinbase token endpoint returned HTTP {status}: {(resp.text or '')[:200]}",
                permanent=_classify_status(status),
                broker=self.broker_id,
                provider_status=status,
            )
        try:
            body_json = resp.json() if resp.content else {}
        except ValueError as exc:
            raise OAuthError(
                f"Coinbase token response is not JSON: {(resp.text or '')[:200]}",
                permanent=True,
                broker=self.broker_id,
                provider_status=status,
            ) from exc

        if not isinstance(body_json, dict):
            raise OAuthError(
                f"Coinbase token response has unexpected root type {type(body_json).__name__}",
                permanent=True,
                broker=self.broker_id,
                provider_status=status,
            )
        return body_json

    def initiate_url(self, *, user_id: int, callback_url: str) -> OAuthInitiateResult:
        client_id, _ = self._require_credentials()
        state = secrets.token_urlsafe(24)
        params = {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": callback_url,
            "scope": READ_ONLY_SCOPES,
            "state": state,
        }
        authorize_url = f"{AUTHORIZE_URL}?{urlencode(params)}"
        return OAuthInitiateResult(
            authorize_url=authorize_url,
            state=state,
            extra={
                "user_id": user_id,
                "callback_url": callback_url,
            },
        )

    def exchange_code(self, ctx: OAuthCallbackContext) -> OAuthTokens:
        if not ctx.code:
            raise OAuthError(
                "missing authorization code in Coinbase callback",
                permanent=True,
                broker=self.broker_id,
            )
        callback_url = str(ctx.extra.get("callback_url") or "").strip()
        if not callback_url:
            raise OAuthError(
                "missing callback_url in OAuth state; restart the Coinbase connection flow",
                permanent=True,
                broker=self.broker_id,
            )
        body = self._post_token(
            {
                "grant_type": "authorization_code",
                "code": ctx.code,
                "redirect_uri": callback_url,
            }
        )
        access_token = body.get("access_token")
        refresh_token = body.get("refresh_token")
        if not access_token:
            raise OAuthError(
                f"Coinbase token response missing access_token: {body!r}",
                permanent=True,
                broker=self.broker_id,
            )
        user_id_raw = (body.get("user_id") or body.get("sub") or "") or None
        return OAuthTokens(
            access_token=str(access_token),
            refresh_token=str(refresh_token) if refresh_token else None,
            expires_at=_parse_expires_at(body.get("expires_in"), _ACCESS_TOKEN_DEFAULT_LIFETIME_S),
            scope=str(body.get("scope") or "") or None,
            provider_account_id=str(user_id_raw) if user_id_raw else None,
            raw=dict(body),
        )

    def refresh(
        self,
        *,
        access_token: str,
        refresh_token: str | None,
    ) -> OAuthTokens:
        if not refresh_token:
            raise OAuthError(
                "Coinbase refresh requires a stored refresh_token",
                permanent=True,
                broker=self.broker_id,
            )
        body = self._post_token({"grant_type": "refresh_token", "refresh_token": refresh_token})
        new_access = body.get("access_token")
        new_refresh = body.get("refresh_token") or refresh_token
        if not new_access:
            raise OAuthError(
                f"Coinbase refresh response missing access_token: {body!r}",
                permanent=True,
                broker=self.broker_id,
            )
        user_id_raw = (body.get("user_id") or body.get("sub") or "") or None
        return OAuthTokens(
            access_token=str(new_access),
            refresh_token=str(new_refresh),
            expires_at=_parse_expires_at(body.get("expires_in"), _ACCESS_TOKEN_DEFAULT_LIFETIME_S),
            scope=str(body.get("scope") or "") or None,
            provider_account_id=str(user_id_raw) if user_id_raw else None,
            raw=dict(body),
        )

    def revoke(
        self,
        *,
        access_token: str,
        refresh_token: str | None = None,
    ) -> None:
        logger.info("Coinbase: no explicit revoke call in adapter; tokens cleared locally.")

    def fetch_account_summary(
        self,
        *,
        access_token: str,
        refresh_token: str | None = None,
    ) -> dict[str, Any] | None:
        if not access_token:
            return None
        try:
            resp = self._session.get(
                f"{API_BASE}/v2/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
                timeout=self._timeout_s,
            )
        except requests.RequestException as exc:
            logger.warning("Coinbase user probe network error: %s", exc)
            return None
        if resp.status_code >= 400:
            return {"status": resp.status_code, "ok": False}
        return {"status": resp.status_code, "ok": True}


__all__ = [
    "API_BASE",
    "AUTHORIZE_URL",
    "TOKEN_URL",
    "CoinbaseOAuthAdapter",
]
