"""E*TRADE OAuth 1.0a sandbox adapter.

E*TRADE still uses **OAuth 1.0a** (RFC 5849), not 2.0. Flow:

1. POST oauth/request_token  -> returns ``oauth_token`` + ``oauth_token_secret``
2. Redirect user to https://us.etrade.com/e/t/etws/authorize
   with ``key=`` consumer_key + ``token=`` request_token
3. User logs in, sees a 5-character verifier code on the screen and pastes
   it back into our app (E*TRADE does **not** auto-redirect).
4. POST oauth/access_token (signed with request_token + verifier) -> returns
   the permanent ``oauth_token`` + ``oauth_token_secret``.
5. Tokens expire at midnight US/Eastern; renew with /oauth/renew_access_token.
6. Revoke with /oauth/revoke_access_token.

We hand-roll the HMAC-SHA1 signing rather than pulling in ``oauthlib`` for a
single OAuth 1.0a broker — fewer dependencies, lower supply-chain risk, and
the canonical-string construction is well-defined.

Sandbox credentials (``ETRADE_SANDBOX_KEY`` / ``ETRADE_SANDBOX_SECRET``) must
be issued by E*TRADE; without them ``initiate_url`` raises ``OAuthError``
loudly so we never silently degrade.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import time
from datetime import datetime, time as dtime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

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


SANDBOX_BASE = "https://apisb.etrade.com"
AUTHORIZE_URL = "https://us.etrade.com/e/t/etws/authorize"


def _percent_encode(value: str) -> str:
    """RFC 5849 §3.6 percent-encoding (unreserved chars are A-Za-z0-9-._~)."""

    return quote(str(value), safe="-._~")


def _nonce() -> str:
    return secrets.token_hex(16)


def _timestamp() -> str:
    return str(int(time.time()))


def build_signature_base_string(
    method: str,
    url: str,
    params: Dict[str, str],
) -> str:
    """Build the OAuth 1.0a canonical signature base string.

    Steps (RFC 5849 §3.4.1):
    1. Percent-encode each key and value.
    2. Sort by encoded key, then by encoded value.
    3. Join as ``key=value`` with ``&``.
    4. Build base = METHOD & encoded_url & encoded_param_string.
    """

    encoded = sorted(
        (_percent_encode(k), _percent_encode(v)) for k, v in params.items()
    )
    param_string = "&".join(f"{k}={v}" for k, v in encoded)
    return "&".join([
        method.upper(),
        _percent_encode(url),
        _percent_encode(param_string),
    ])


def sign_hmac_sha1(base_string: str, consumer_secret: str, token_secret: str = "") -> str:
    """Compute HMAC-SHA1 signature; key = consumer_secret&token_secret (encoded)."""

    key = f"{_percent_encode(consumer_secret)}&{_percent_encode(token_secret)}"
    digest = hmac.new(
        key.encode("utf-8"),
        base_string.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def _build_oauth_header(params: Dict[str, str]) -> str:
    """Format params into an ``Authorization: OAuth ...`` header."""

    pieces = [f'{_percent_encode(k)}="{_percent_encode(v)}"' for k, v in sorted(params.items())]
    return "OAuth " + ", ".join(pieces)


def _next_midnight_us_eastern() -> datetime:
    """Return the next midnight US/Eastern as an aware UTC datetime.

    E*TRADE access tokens expire at midnight US/Eastern. We approximate this
    in pure stdlib by using fixed UTC-5 (EST). DST changes mean the expiry can
    drift up to an hour, which is fine for "should we refresh proactively?"
    purposes — the actual provider truth is rechecked on every renew call.
    """

    eastern = timezone(timedelta(hours=-5), name="US/Eastern-approx")
    now_eastern = datetime.now(eastern)
    next_day = now_eastern.date() + timedelta(days=1)
    midnight = datetime.combine(next_day, dtime(0, 0), tzinfo=eastern)
    return midnight.astimezone(timezone.utc)


def _parse_token_response(text: str) -> Dict[str, str]:
    """Parse ``key=value&key=value`` from an E*TRADE token response body."""

    out: Dict[str, str] = {}
    for piece in text.split("&"):
        if "=" not in piece:
            continue
        k, _, v = piece.partition("=")
        out[k.strip()] = v.strip()
    return out


def _classify_status(status: int) -> bool:
    """Return ``permanent=True`` for 4xx (need reauth), False for 5xx/network."""

    return 400 <= status < 500


class ETradeSandboxAdapter(OAuthBrokerAdapter):
    """OAuth 1.0a adapter for E*TRADE sandbox.

    The same code drives ``etrade`` (live) when constructed with ``live=True``;
    we keep ``broker_id="etrade_sandbox"`` here because v1 only ships sandbox.
    Switching to live requires E*TRADE to approve the application — adding a
    sibling subclass at that point is a one-liner.
    """

    broker_id = "etrade_sandbox"
    environment = "sandbox"

    def __init__(
        self,
        *,
        consumer_key: Optional[str] = None,
        consumer_secret: Optional[str] = None,
        base_url: str = SANDBOX_BASE,
        timeout_s: Optional[float] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self._consumer_key = consumer_key or settings.ETRADE_SANDBOX_KEY
        self._consumer_secret = consumer_secret or settings.ETRADE_SANDBOX_SECRET
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s if timeout_s is not None else settings.ETRADE_OAUTH_REQUEST_TIMEOUT_S
        self._session = session or requests.Session()

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------
    def _require_credentials(self) -> Tuple[str, str]:
        if not self._consumer_key or not self._consumer_secret:
            raise OAuthError(
                "E*TRADE sandbox credentials not configured "
                "(set ETRADE_SANDBOX_KEY and ETRADE_SANDBOX_SECRET)",
                permanent=True,
                broker=self.broker_id,
            )
        return self._consumer_key, self._consumer_secret

    def _signed_request(
        self,
        method: str,
        path: str,
        *,
        token: str = "",
        token_secret: str = "",
        callback: Optional[str] = None,
        verifier: Optional[str] = None,
    ) -> requests.Response:
        consumer_key, consumer_secret = self._require_credentials()
        url = f"{self._base_url}{path}"
        params: Dict[str, str] = {
            "oauth_consumer_key": consumer_key,
            "oauth_nonce": _nonce(),
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": _timestamp(),
            "oauth_version": "1.0",
        }
        if token:
            params["oauth_token"] = token
        if callback:
            params["oauth_callback"] = callback
        if verifier:
            params["oauth_verifier"] = verifier

        base_string = build_signature_base_string(method, url, params)
        params["oauth_signature"] = sign_hmac_sha1(
            base_string, consumer_secret, token_secret
        )
        headers = {"Authorization": _build_oauth_header(params)}
        try:
            return self._session.request(
                method.upper(),
                url,
                headers=headers,
                timeout=self._timeout_s,
            )
        except requests.RequestException as exc:
            raise OAuthError(
                f"network failure calling E*TRADE {path}: {exc}",
                permanent=False,
                broker=self.broker_id,
            ) from exc

    # ------------------------------------------------------------------
    # OAuthBrokerAdapter contract
    # ------------------------------------------------------------------
    def initiate_url(self, *, user_id: int, callback_url: str) -> OAuthInitiateResult:
        consumer_key, _ = self._require_credentials()
        # E*TRADE accepts ``oob`` (out-of-band) when there's no auto-callback,
        # but our flow always uses the app callback so we pass it.
        resp = self._signed_request(
            "POST",
            "/oauth/request_token",
            callback=callback_url or "oob",
        )
        if resp.status_code >= 400:
            raise OAuthError(
                f"E*TRADE request_token failed: HTTP {resp.status_code} {resp.text[:200]}",
                permanent=_classify_status(resp.status_code),
                broker=self.broker_id,
                provider_status=resp.status_code,
            )
        body = _parse_token_response(resp.text)
        request_token = body.get("oauth_token")
        request_token_secret = body.get("oauth_token_secret")
        if not request_token or not request_token_secret:
            raise OAuthError(
                f"E*TRADE request_token response missing oauth_token: {resp.text[:200]}",
                permanent=True,
                broker=self.broker_id,
                provider_status=resp.status_code,
            )

        authorize_url = (
            f"{AUTHORIZE_URL}?key={_percent_encode(consumer_key)}"
            f"&token={_percent_encode(request_token)}"
        )
        # E*TRADE doesn't auto-redirect with a state param, so we mint our own
        # CSRF token and pin the request_token_secret to it via the state store.
        state = secrets.token_urlsafe(24)
        return OAuthInitiateResult(
            authorize_url=authorize_url,
            state=state,
            extra={
                "request_token": request_token,
                "request_token_secret": request_token_secret,
                "user_id": user_id,
                "callback_url": callback_url,
            },
        )

    def exchange_code(self, ctx: OAuthCallbackContext) -> OAuthTokens:
        request_token = ctx.extra.get("request_token")
        request_token_secret = ctx.extra.get("request_token_secret")
        if not request_token or not request_token_secret:
            raise OAuthError(
                "missing request_token / request_token_secret in callback context",
                permanent=True,
                broker=self.broker_id,
            )
        resp = self._signed_request(
            "GET",
            "/oauth/access_token",
            token=request_token,
            token_secret=request_token_secret,
            verifier=ctx.code,
        )
        if resp.status_code >= 400:
            raise OAuthError(
                f"E*TRADE access_token failed: HTTP {resp.status_code} {resp.text[:200]}",
                permanent=_classify_status(resp.status_code),
                broker=self.broker_id,
                provider_status=resp.status_code,
            )
        body = _parse_token_response(resp.text)
        access_token = body.get("oauth_token")
        access_token_secret = body.get("oauth_token_secret")
        if not access_token or not access_token_secret:
            raise OAuthError(
                f"E*TRADE access_token response missing oauth_token: {resp.text[:200]}",
                permanent=True,
                broker=self.broker_id,
                provider_status=resp.status_code,
            )
        return OAuthTokens(
            access_token=access_token,
            refresh_token=access_token_secret,  # OAuth 1.0a: store secret here
            expires_at=_next_midnight_us_eastern(),
            scope=None,
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
                "E*TRADE refresh requires the access_token_secret",
                permanent=True,
                broker=self.broker_id,
            )
        resp = self._signed_request(
            "GET",
            "/oauth/renew_access_token",
            token=access_token,
            token_secret=refresh_token,
        )
        if resp.status_code >= 400:
            raise OAuthError(
                f"E*TRADE renew_access_token failed: HTTP {resp.status_code} {resp.text[:200]}",
                permanent=_classify_status(resp.status_code),
                broker=self.broker_id,
                provider_status=resp.status_code,
            )
        # E*TRADE renew responds 200 with the existing token reactivated, or
        # may respond with a fresh token; handle both shapes.
        body = _parse_token_response(resp.text)
        new_token = body.get("oauth_token") or access_token
        new_secret = body.get("oauth_token_secret") or refresh_token
        return OAuthTokens(
            access_token=new_token,
            refresh_token=new_secret,
            expires_at=_next_midnight_us_eastern(),
            scope=None,
            provider_account_id=None,
            raw=dict(body),
        )

    def revoke(
        self,
        *,
        access_token: str,
        refresh_token: Optional[str] = None,
    ) -> None:
        try:
            resp = self._signed_request(
                "GET",
                "/oauth/revoke_access_token",
                token=access_token,
                token_secret=refresh_token or "",
            )
        except OAuthError as exc:
            logger.warning(
                "E*TRADE revoke network error (oauth token redacted): %s",
                exc,
            )
            return
        if resp.status_code >= 400:
            logger.warning(
                "E*TRADE revoke returned HTTP %s (oauth token redacted): %s",
                resp.status_code,
                resp.text[:200],
            )

    def fetch_account_summary(
        self,
        *,
        access_token: str,
        refresh_token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        # The /v1/accounts/list endpoint is the canonical "is this token live?"
        # probe. We only attempt it when the caller passes the token secret;
        # otherwise we can't sign and return ``None`` (caller treats as "skip").
        if not refresh_token:
            return None
        try:
            resp = self._signed_request(
                "GET",
                "/v1/accounts/list",
                token=access_token,
                token_secret=refresh_token,
            )
        except OAuthError as exc:
            logger.warning("E*TRADE accounts/list probe failed: %s", exc)
            return None
        if resp.status_code >= 400:
            return {"status": resp.status_code, "ok": False}
        return {"status": resp.status_code, "ok": True}


__all__ = ["ETradeSandboxAdapter"]
