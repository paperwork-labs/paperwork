"""Thin data-API client for Tradier.

Wraps the handful of Tradier v1 endpoints the bronze sync consumes:

* ``GET /v1/user/profile``                     — list accounts
* ``GET /v1/accounts/{id}/balances``           — cash/equity/margin details
* ``GET /v1/accounts/{id}/positions``          — open positions (stocks + options)
* ``GET /v1/accounts/{id}/history``            — transactions / trades / dividends
* ``GET /v1/accounts/{id}/gainloss``           — realized gain/loss summary

All endpoints require a bearer access-token header and return JSON when
``Accept: application/json`` is set. We classify HTTP errors into
``permanent`` (4xx — needs reauth / bad input / closed account) vs
transient (5xx / network / 429). Callers never see raw ``Response``
objects.

Tradier wraps its payloads in either a ``{ "accounts": { "account": [...] } }``
or an equivalent ``{ "balances": { ... } }`` envelope. Array fields
collapse to the inner object when only one row exists, so every
extractor normalizes to a list.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests

from backend.config import settings

logger = logging.getLogger(__name__)


_LIVE_BASE = "https://api.tradier.com"
_SANDBOX_BASE = "https://sandbox.tradier.com"


class TradierAPIError(Exception):
    """Tradier data-API error.

    ``permanent=True`` means the caller should stop retrying and surface a
    "reauthorize" prompt (4xx, malformed response). ``permanent=False`` is
    retry-safe (5xx, 429, network timeout).
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
    """4xx is permanent; 5xx / 429 retryable.

    Note 429 is 4xx but Tradier only issues it on rate-limit burn, which
    is retry-safe with backoff. We special-case it to ``permanent=False``.
    """

    if status == 429:
        return False
    return 400 <= status < 500


def _as_list(value: Any) -> List[Dict[str, Any]]:
    """Normalize Tradier's "object when single, array when many" shape.

    Every collection endpoint collapses its inner array to a bare object
    when there is exactly one item. Silently iterating on a dict would
    iterate its keys — the single-row case would vanish without a trace.
    This helper makes the shape consistent without swallowing malformed
    payloads (non-dict/non-list inputs raise).
    """

    if value is None:
        return []
    if isinstance(value, list):
        return [v for v in value if isinstance(v, dict)]
    if isinstance(value, dict):
        return [value]
    # Unexpected scalar / string — surface rather than silently return [].
    raise TradierAPIError(
        f"expected object or list, got {type(value).__name__}",
        permanent=True,
    )


class TradierBronzeClient:
    """Authenticated thin client over the Tradier v1 data API.

    Construction does no I/O; the bearer token comes from
    :class:`backend.models.broker_oauth_connection.BrokerOAuthConnection`
    (decrypted by the caller). Set ``sandbox=True`` to target
    ``sandbox.tradier.com``.
    """

    #: Accept header Tradier honours for JSON responses.
    _JSON_ACCEPT = "application/json"

    def __init__(
        self,
        *,
        access_token: str,
        sandbox: bool = False,
        base_url: Optional[str] = None,
        session: Optional[requests.Session] = None,
        timeout_s: Optional[float] = None,
    ) -> None:
        if not access_token:
            raise TradierAPIError(
                "Tradier client requires a non-empty access_token",
                permanent=True,
            )
        self._token = access_token
        self._base_url = (
            base_url.rstrip("/") if base_url
            else (_SANDBOX_BASE if sandbox else _LIVE_BASE)
        )
        self._session = session or requests.Session()
        self._timeout_s = (
            timeout_s
            if timeout_s is not None
            else settings.TRADIER_OAUTH_REQUEST_TIMEOUT_S
        )

    # ------------------------------------------------------------------
    # Low-level bearer GET returning parsed JSON
    # ------------------------------------------------------------------
    def _get_json(
        self,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self._base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": self._JSON_ACCEPT,
        }
        try:
            resp = self._session.get(
                url, headers=headers, params=params, timeout=self._timeout_s
            )
        except requests.RequestException as exc:
            logger.warning(
                "tradier client: network failure on %s: %s", path, exc
            )
            raise TradierAPIError(
                f"network failure calling Tradier {path}: {exc}",
                permanent=False,
                path=path,
            ) from exc

        status = resp.status_code
        if status >= 400:
            logger.warning(
                "tradier client: HTTP %s on %s body=%s",
                status, path, (resp.text or "")[:200],
            )
            raise TradierAPIError(
                f"Tradier {path} returned HTTP {status}: "
                f"{(resp.text or '')[:200]}",
                permanent=_classify_permanent(status),
                status=status,
                path=path,
            )

        try:
            body = resp.json() if resp.content else {}
        except ValueError as exc:
            raise TradierAPIError(
                f"Tradier {path} returned non-JSON body: "
                f"{(resp.text or '')[:200]}",
                permanent=True,
                status=status,
                path=path,
            ) from exc

        if not isinstance(body, dict):
            raise TradierAPIError(
                f"Tradier {path} returned unexpected root type "
                f"{type(body).__name__}",
                permanent=True,
                status=status,
                path=path,
            )
        return body

    # ------------------------------------------------------------------
    # Public wrappers
    # ------------------------------------------------------------------
    def get_accounts(self) -> List[Dict[str, Any]]:
        """Return a flat list of account dicts from ``/user/profile``.

        Tradier nests at ``{"profile": {"account": [...]}}`` (or a single
        object when the user has only one account).
        """

        body = self._get_json("/v1/user/profile")
        profile = body.get("profile") or {}
        return _as_list(profile.get("account"))

    def get_balances(self, account_id: str) -> Dict[str, Any]:
        """Return the balances object for ``account_id``.

        Tradier returns ``{"balances": { ...fields... }}``; we unwrap. A
        missing / empty envelope returns ``{}`` rather than raising so
        balance-unavailable does not block a position/trade sync.
        """

        if not account_id:
            raise TradierAPIError(
                "get_balances requires a non-empty account_id",
                permanent=True,
            )
        body = self._get_json(f"/v1/accounts/{account_id}/balances")
        bal = body.get("balances")
        if isinstance(bal, dict):
            return bal
        return {}

    def get_positions(self, account_id: str) -> List[Dict[str, Any]]:
        """Return open positions (stocks + options) for ``account_id``.

        Tradier returns ``{"positions": "null"}`` (literal string) when
        the account has no positions. We coerce to an empty list.
        """

        if not account_id:
            raise TradierAPIError(
                "get_positions requires a non-empty account_id",
                permanent=True,
            )
        body = self._get_json(f"/v1/accounts/{account_id}/positions")
        positions = body.get("positions")
        if not positions or positions == "null":
            return []
        if isinstance(positions, dict):
            return _as_list(positions.get("position"))
        return []

    def get_history(
        self,
        account_id: str,
        *,
        start: Optional[str] = None,
        end: Optional[str] = None,
        history_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return transaction/trade/dividend history for ``account_id``.

        ``history_type`` maps to Tradier's ``type=`` query param
        (``trade``, ``dividend``, ``option``, etc.). Omitting it returns
        the full history. ``start`` / ``end`` are ISO dates (YYYY-MM-DD).

        Tradier returns ``{"history": "null"}`` when there is no history.
        """

        if not account_id:
            raise TradierAPIError(
                "get_history requires a non-empty account_id",
                permanent=True,
            )
        params: Dict[str, Any] = {}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        if history_type:
            params["type"] = history_type

        body = self._get_json(
            f"/v1/accounts/{account_id}/history",
            params=params or None,
        )
        history = body.get("history")
        if not history or history == "null":
            return []
        if isinstance(history, dict):
            return _as_list(history.get("event"))
        return []

    def get_gainloss(
        self,
        account_id: str,
        *,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return realized gain/loss rows for ``account_id``.

        Tradier exposes realized gains directly at ``/gainloss`` — useful
        context but not a substitute for our own closing-lot matcher,
        which also owns tax-lot attribution across accounts.
        """

        if not account_id:
            raise TradierAPIError(
                "get_gainloss requires a non-empty account_id",
                permanent=True,
            )
        params: Dict[str, Any] = {}
        if start:
            params["start"] = start
        if end:
            params["end"] = end

        body = self._get_json(
            f"/v1/accounts/{account_id}/gainloss",
            params=params or None,
        )
        gainloss = body.get("gainloss")
        if not gainloss or gainloss == "null":
            return []
        if isinstance(gainloss, dict):
            return _as_list(gainloss.get("closed_position"))
        return []


__all__ = ["TradierAPIError", "TradierBronzeClient"]
