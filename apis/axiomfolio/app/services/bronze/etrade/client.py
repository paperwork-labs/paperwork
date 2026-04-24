"""Thin data-API client for the E*TRADE sandbox.

Responsibilities:

* Wrap the four data endpoints the bronze sync needs
  (``/v1/accounts/list``, ``/v1/accounts/{k}/balance``,
  ``/v1/accounts/{k}/portfolio``, ``/v1/accounts/{k}/transactions``).
* Reuse the OAuth 1.0a HMAC-SHA1 signing code already living in
  :class:`app.services.oauth.etrade.ETradeSandboxAdapter`. **No HMAC
  logic is duplicated here** — if it needs to change, it changes in one
  place. We intentionally call ``adapter._signed_request`` (a "protected"
  method); the seam is validated by the unit tests in
  ``backend/tests/services/bronze/etrade``.
* Classify HTTP errors into permanent (reauth needed) vs transient
  (retry). Callers never see raw ``requests.Response`` objects.

JSON vs XML:
    The E*TRADE v1 data API returns XML by default and JSON when the URL
    ends in ``.json``. We always append ``.json`` to avoid having to
    parse XML or mutate the adapter's request headers.

medallion: bronze
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests

from app.services.oauth.etrade import ETradeSandboxAdapter

logger = logging.getLogger(__name__)


class ETradeAPIError(Exception):
    """E*TRADE data-API error.

    ``permanent=True`` means the caller should stop retrying and surface
    a "reauthorize" prompt (4xx from the provider, missing credentials,
    malformed response). ``permanent=False`` is the retry-safe case
    (5xx, network timeout).
    """

    def __init__(
        self,
        message: str,
        *,
        permanent: bool,
        status: Optional[int] = None,
        path: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.permanent = permanent
        self.status = status
        self.path = path


def _classify_permanent(status: int) -> bool:
    """Mirror ``_classify_status`` in the OAuth adapter — 4xx is permanent."""

    return 400 <= status < 500


class ETradeBronzeClient:
    """Authenticated thin client over the E*TRADE v1 data API.

    The access token + access-token secret come from
    :class:`app.models.broker_oauth_connection.BrokerOAuthConnection`
    (decrypted by the caller). Construction does no I/O.
    """

    #: Default Accept header we set on the underlying requests session.
    #: Belt-and-suspenders for providers that ignore the ``.json`` URL
    #: suffix; E*TRADE honours both.
    _JSON_ACCEPT = "application/json"

    def __init__(
        self,
        *,
        access_token: str,
        access_token_secret: str,
        adapter: Optional[ETradeSandboxAdapter] = None,
    ) -> None:
        if not access_token or not access_token_secret:
            raise ETradeAPIError(
                "E*TRADE client requires both access_token and access_token_secret",
                permanent=True,
            )
        self._token = access_token
        self._secret = access_token_secret
        # Fresh session per client instance so concurrent syncs don't
        # stomp on each other's connection pools. The session only
        # carries the Accept header; the Authorization header is set by
        # the adapter on every call (signed per RFC 5849).
        session = requests.Session()
        session.headers["Accept"] = self._JSON_ACCEPT
        self._adapter = adapter or ETradeSandboxAdapter(session=session)

    # ------------------------------------------------------------------
    # Low-level signed GET returning parsed JSON
    # ------------------------------------------------------------------
    def _signed_get_json(self, path: str) -> Dict[str, Any]:
        """Issue a signed GET and return parsed JSON.

        Raises :class:`ETradeAPIError` with ``permanent=True`` on 4xx or
        malformed JSON (neither is retry-safe without reauth / provider
        fix) and ``permanent=False`` on 5xx / network errors.
        """

        # Intentional protected-member access: this client is the sanctioned
        # second caller of the adapter's signing helper. Keeping the HMAC
        # logic in one place is more important than the lint warning.
        try:
            resp = self._adapter._signed_request(  # noqa: SLF001
                "GET",
                path,
                token=self._token,
                token_secret=self._secret,
            )
        except Exception as exc:  # OAuthError / requests.RequestException
            logger.warning(
                "etrade client: network/signing failure on %s: %s", path, exc
            )
            raise ETradeAPIError(
                f"network or signing failure calling E*TRADE {path}: {exc}",
                permanent=False,
                path=path,
            ) from exc

        status = resp.status_code
        if status >= 400:
            logger.warning(
                "etrade client: HTTP %s on %s body=%s",
                status, path, (resp.text or "")[:200],
            )
            raise ETradeAPIError(
                f"E*TRADE {path} returned HTTP {status}: {(resp.text or '')[:200]}",
                permanent=_classify_permanent(status),
                status=status,
                path=path,
            )

        try:
            body = resp.json() if resp.content else {}
        except ValueError as exc:
            logger.warning(
                "etrade client: non-JSON body on %s: %s", path, (resp.text or "")[:200]
            )
            raise ETradeAPIError(
                f"E*TRADE {path} returned non-JSON body: {(resp.text or '')[:200]}",
                permanent=True,
                status=status,
                path=path,
            ) from exc

        if not isinstance(body, dict):
            # v1 endpoints always wrap in an object; a top-level array
            # would be a schema surprise we want to surface loudly.
            raise ETradeAPIError(
                f"E*TRADE {path} returned unexpected JSON root type {type(body).__name__}",
                permanent=True,
                status=status,
                path=path,
            )
        return body

    # ------------------------------------------------------------------
    # Public data-API wrappers — one per endpoint
    # ------------------------------------------------------------------
    def list_accounts(self) -> List[Dict[str, Any]]:
        """Return the list of accounts accessible to the current token.

        Shape normalized to a flat list of ``Account`` dicts (E*TRADE
        wraps them in ``AccountListResponse.Accounts.Account``).
        """

        body = self._signed_get_json("/v1/accounts/list.json")
        accounts = (
            (body.get("AccountListResponse") or {})
            .get("Accounts", {})
            .get("Account", [])
            or []
        )
        if isinstance(accounts, dict):
            # Single-account responses come back as an object, not a list.
            accounts = [accounts]
        return list(accounts)

    def get_balance(self, account_id_key: str) -> Dict[str, Any]:
        """Return the BalanceResponse for ``account_id_key``.

        ``instType=BROKERAGE`` and ``realTimeNAV=true`` are required
        query params per the E*TRADE docs.
        """

        if not account_id_key:
            raise ETradeAPIError(
                "get_balance requires a non-empty account_id_key",
                permanent=True,
            )
        path = (
            f"/v1/accounts/{account_id_key}/balance.json"
            f"?instType=BROKERAGE&realTimeNAV=true"
        )
        body = self._signed_get_json(path)
        return body.get("BalanceResponse") or {}

    def get_portfolio(self, account_id_key: str) -> List[Dict[str, Any]]:
        """Return the flat list of open positions.

        E*TRADE nests positions inside
        ``PortfolioResponse.AccountPortfolio[].Position[]``; we flatten
        across any multi-portfolio response into a single list.
        """

        if not account_id_key:
            raise ETradeAPIError(
                "get_portfolio requires a non-empty account_id_key",
                permanent=True,
            )
        body = self._signed_get_json(f"/v1/accounts/{account_id_key}/portfolio.json")
        portfolios = (body.get("PortfolioResponse") or {}).get("AccountPortfolio", [])
        if isinstance(portfolios, dict):
            portfolios = [portfolios]
        out: List[Dict[str, Any]] = []
        for portfolio in portfolios or []:
            positions = portfolio.get("Position", []) if isinstance(portfolio, dict) else []
            if isinstance(positions, dict):
                positions = [positions]
            out.extend(p for p in positions if isinstance(p, dict))
        return out

    def get_transactions(self, account_id_key: str) -> List[Dict[str, Any]]:
        """Return the flat list of transactions for ``account_id_key``."""

        if not account_id_key:
            raise ETradeAPIError(
                "get_transactions requires a non-empty account_id_key",
                permanent=True,
            )
        body = self._signed_get_json(
            f"/v1/accounts/{account_id_key}/transactions.json"
        )
        txns = (body.get("TransactionListResponse") or {}).get("Transaction", [])
        if isinstance(txns, dict):
            txns = [txns]
        return list(txns or [])


__all__ = ["ETradeAPIError", "ETradeBronzeClient"]
