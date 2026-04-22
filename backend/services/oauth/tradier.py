"""Tradier OAuth 2.0 adapter.

Tradier uses standard OAuth 2.0 authorization-code flow (unlike E*TRADE's
OAuth 1.0a). Endpoints:

* Authorize:   ``https://api.tradier.com/v1/oauth/authorize``
                (sandbox uses the same authorize URL — Tradier does not
                split the user-facing login endpoint by environment)
* Token:       ``https://api.tradier.com/v1/oauth/accesstoken`` (live)
               ``https://sandbox.tradier.com/v1/oauth/accesstoken`` (sandbox)
* Data:        ``https://api.tradier.com/v1/`` / ``https://sandbox.tradier.com/v1/``

Data-API bearer header: ``Authorization: Bearer <access_token>``,
``Accept: application/json``.

Tokens:
    * ``access_token`` lives ~24h.
    * ``refresh_token`` lives ~90d.
    * We refresh preemptively at T-1h (matches the job_catalog
      ``oauth-token-refresh`` cadence of 30 min so refresh happens with
      two full cycles of headroom).

This adapter ships two concrete classes — ``TradierOAuth2Adapter`` (live)
and ``TradierSandboxOAuth2Adapter`` (sandbox) — registered under
``broker_id`` strings ``tradier`` and ``tradier_sandbox``. They share the
same flow logic; only the base URL and credential pair differ. The
sandbox class is a thin subclass so the registry stays a one-liner.

Why not swagger-generate or pull in ``authlib``? A single-file hand-rolled
OAuth 2.0 code grant is tiny (~200 lines) and dependency-free, matching
the E*TRADE adapter's "no oauthlib for OAuth 1.0a" choice; see D130 in
``docs/KNOWLEDGE.md`` for the bronze+OAuth contract.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import requests

from backend.config import settings

from .base import (
    OAuthBrokerAdapter,
    OAuthCallbackContext,
    OAuthError,
    OAuthInitiateResult,
    OAuthTokens,
)

logger = logging.getLogger(__name__)


# Tradier's authorize URL is served only off the live host. Sandbox still
# uses the live ``/v1/oauth/authorize`` — only the token + data endpoints
# differ. Pinning this here keeps both adapters in sync.
AUTHORIZE_URL = "https://api.tradier.com/v1/oauth/authorize"

LIVE_BASE = "https://api.tradier.com"
SANDBOX_BASE = "https://sandbox.tradier.com"

# Match E*TRADE's "refresh at T-1h" policy. Access tokens live ~24h; the
# 60-minute cushion means the every-30-min ``oauth-token-refresh`` Beat
# task gets two shots at every token before it actually expires.
_ACCESS_TOKEN_DEFAULT_LIFETIME_S = 24 * 3600  # fallback when provider omits
_REFRESH_TOKEN_DEFAULT_LIFETIME_S = 90 * 24 * 3600


def _classify_status(status: int) -> bool:
    """Return ``permanent=True`` for 4xx (reauth needed), False for 5xx."""

    return 400 <= status < 500


def _parse_expires_at(expires_in: Optional[Any], default_s: int) -> datetime:
    """Coerce the provider's ``expires_in`` (seconds) into a UTC datetime.

    Tradier returns integer seconds; some SDKs stringify it. We coerce via
    ``int()`` with a fallback to ``default_s`` so a malformed provider
    response doesn't make the token look immortal.
    """

    try:
        seconds = int(expires_in) if expires_in is not None else default_s
    except (TypeError, ValueError):
        seconds = default_s
    if seconds <= 0:
        seconds = default_s
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


class TradierOAuth2Adapter(OAuthBrokerAdapter):
    """OAuth 2.0 adapter for Tradier (live brokerage).

    Subclass ``TradierSandboxOAuth2Adapter`` flips the token/data base URL
    and the credential pair; everything else is shared.
    """

    broker_id = "tradier"
    environment = "live"

    # Child classes override these three.
    _BASE_URL = LIVE_BASE
    _CLIENT_ID_SETTING = "TRADIER_CLIENT_ID"
    _CLIENT_SECRET_SETTING = "TRADIER_CLIENT_SECRET"

    def __init__(
        self,
        *,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_s: Optional[float] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self._client_id = client_id or getattr(settings, self._CLIENT_ID_SETTING, None)
        self._client_secret = (
            client_secret or getattr(settings, self._CLIENT_SECRET_SETTING, None)
        )
        self._base_url = (base_url or self._BASE_URL).rstrip("/")
        self._timeout_s = (
            timeout_s
            if timeout_s is not None
            else settings.TRADIER_OAUTH_REQUEST_TIMEOUT_S
        )
        self._session = session or requests.Session()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _require_credentials(self) -> Tuple[str, str]:
        if not self._client_id or not self._client_secret:
            raise OAuthError(
                f"Tradier credentials not configured (set "
                f"{self._CLIENT_ID_SETTING} and {self._CLIENT_SECRET_SETTING})",
                permanent=True,
                broker=self.broker_id,
            )
        return self._client_id, self._client_secret

    def _token_url(self) -> str:
        return f"{self._base_url}/v1/oauth/accesstoken"

    def _post_token(self, payload: Dict[str, str]) -> Dict[str, Any]:
        client_id, client_secret = self._require_credentials()
        url = self._token_url()
        # Tradier accepts HTTP Basic for the client credential pair and
        # ``application/x-www-form-urlencoded`` for the grant body — the
        # same shape every RFC 6749 server supports.
        try:
            resp = self._session.post(
                url,
                data=payload,
                auth=(client_id, client_secret),
                headers={"Accept": "application/json"},
                timeout=self._timeout_s,
            )
        except requests.RequestException as exc:
            raise OAuthError(
                f"network failure calling Tradier token endpoint: {exc}",
                permanent=False,
                broker=self.broker_id,
            ) from exc

        status = resp.status_code
        if status >= 400:
            raise OAuthError(
                f"Tradier token endpoint returned HTTP {status}: "
                f"{(resp.text or '')[:200]}",
                permanent=_classify_status(status),
                broker=self.broker_id,
                provider_status=status,
            )
        try:
            body = resp.json() if resp.content else {}
        except ValueError as exc:
            raise OAuthError(
                f"Tradier token response is not JSON: {(resp.text or '')[:200]}",
                permanent=True,
                broker=self.broker_id,
                provider_status=status,
            ) from exc

        if not isinstance(body, dict):
            raise OAuthError(
                f"Tradier token response has unexpected root type "
                f"{type(body).__name__}",
                permanent=True,
                broker=self.broker_id,
                provider_status=status,
            )
        return body

    # ------------------------------------------------------------------
    # OAuthBrokerAdapter contract
    # ------------------------------------------------------------------
    def initiate_url(self, *, user_id: int, callback_url: str) -> OAuthInitiateResult:
        client_id, _ = self._require_credentials()
        state = secrets.token_urlsafe(24)
        # Tradier requires ``scope=read,trade,market,stream`` for a full
        # read+write token; bronze only needs ``read`` but we ask for the
        # broader scope so a future order-execution feature doesn't require
        # the user to
        # re-auth. The user sees the scope list on the consent screen.
        params = {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": callback_url,
            "scope": "read,trade,market,stream",
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
                "missing authorization code in Tradier callback",
                permanent=True,
                broker=self.broker_id,
            )
        callback_url = str(ctx.extra.get("callback_url") or "").strip()
        if not callback_url:
            raise OAuthError(
                "missing callback_url in OAuth state; restart the Tradier connection flow",
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
                f"Tradier token response missing access_token: {body!r}",
                permanent=True,
                broker=self.broker_id,
            )
        return OAuthTokens(
            access_token=str(access_token),
            refresh_token=str(refresh_token) if refresh_token else None,
            expires_at=_parse_expires_at(
                body.get("expires_in"), _ACCESS_TOKEN_DEFAULT_LIFETIME_S
            ),
            scope=str(body.get("scope") or "") or None,
            provider_account_id=None,
            raw=dict(body),
        )

    def refresh(
        self,
        *,
        access_token: str,
        refresh_token: Optional[str],
    ) -> OAuthTokens:
        if not refresh_token:
            raise OAuthError(
                "Tradier refresh requires a stored refresh_token",
                permanent=True,
                broker=self.broker_id,
            )
        body = self._post_token(
            {"grant_type": "refresh_token", "refresh_token": refresh_token}
        )
        new_access = body.get("access_token")
        # Tradier occasionally rotates the refresh_token and occasionally
        # keeps it — fall back to the previous refresh so we never
        # accidentally null the stored credential.
        new_refresh = body.get("refresh_token") or refresh_token
        if not new_access:
            raise OAuthError(
                f"Tradier refresh response missing access_token: {body!r}",
                permanent=True,
                broker=self.broker_id,
            )
        return OAuthTokens(
            access_token=str(new_access),
            refresh_token=str(new_refresh),
            expires_at=_parse_expires_at(
                body.get("expires_in"), _ACCESS_TOKEN_DEFAULT_LIFETIME_S
            ),
            scope=str(body.get("scope") or "") or None,
            provider_account_id=None,
            raw=dict(body),
        )

    def revoke(
        self,
        *,
        access_token: str,
        refresh_token: Optional[str] = None,
    ) -> None:
        # Tradier does not publish an OAuth 2.0 revoke endpoint as of
        # 2026-04. The correct user-facing path is "Revoke Application"
        # inside the Tradier dashboard. Best-effort: log that revoke is a
        # no-op so operators know to tell the user. Forgetting the stored
        # ciphertext in our DB is handled by the caller.
        logger.info(
            "Tradier: no provider revoke endpoint; connection tokens will be "
            "forgotten locally. User can revoke at api.tradier.com."
        )

    def fetch_account_summary(
        self,
        *,
        access_token: str,
        refresh_token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Small ``/user/profile`` probe to answer "is the token live?".

        Returns ``{"status": <code>, "ok": bool}`` so the health/refresh
        task can log status without exposing profile PII.
        """

        if not access_token:
            return None
        try:
            resp = self._session.get(
                f"{self._base_url}/v1/user/profile",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
                timeout=self._timeout_s,
            )
        except requests.RequestException as exc:
            logger.warning("Tradier profile probe network error: %s", exc)
            return None
        if resp.status_code >= 400:
            return {"status": resp.status_code, "ok": False}
        return {"status": resp.status_code, "ok": True}


class TradierSandboxOAuth2Adapter(TradierOAuth2Adapter):
    """Tradier OAuth 2.0 adapter pointed at the sandbox host.

    The only difference is the base URL and the credential pair: the
    authorize URL, flow, and data-API shape are identical.
    """

    broker_id = "tradier_sandbox"
    environment = "sandbox"
    _BASE_URL = SANDBOX_BASE
    _CLIENT_ID_SETTING = "TRADIER_SANDBOX_CLIENT_ID"
    _CLIENT_SECRET_SETTING = "TRADIER_SANDBOX_CLIENT_SECRET"


__all__ = [
    "TradierOAuth2Adapter",
    "TradierSandboxOAuth2Adapter",
    "AUTHORIZE_URL",
    "LIVE_BASE",
    "SANDBOX_BASE",
]
