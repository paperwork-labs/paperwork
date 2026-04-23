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
        return self._request_json("GET", path, params=params)

    def _post_json(
        self,
        path: str,
        *,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Form-encoded POST returning parsed JSON.

        Tradier's order-write endpoints accept ``application/x-www-form-
        urlencoded`` payloads (not JSON) and return JSON responses. The
        ``requests`` library handles form-encoding automatically when
        ``data=`` is a dict.
        """

        return self._request_json("POST", path, data=data)

    def _delete_json(self, path: str) -> Dict[str, Any]:
        """HTTP DELETE returning parsed JSON (order cancellation)."""

        return self._request_json("DELETE", path)

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self._base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": self._JSON_ACCEPT,
        }
        try:
            resp = self._session.request(
                method,
                url,
                headers=headers,
                params=params,
                data=data,
                timeout=self._timeout_s,
            )
        except requests.RequestException as exc:
            logger.warning(
                "tradier client: network failure on %s %s: %s", method, path, exc
            )
            raise TradierAPIError(
                f"network failure calling Tradier {method} {path}: {exc}",
                permanent=False,
                path=path,
            ) from exc

        status = resp.status_code
        if status >= 400:
            logger.warning(
                "tradier client: HTTP %s on %s %s body=%s",
                status, method, path, (resp.text or "")[:200],
            )
            raise TradierAPIError(
                f"Tradier {method} {path} returned HTTP {status}: "
                f"{(resp.text or '')[:200]}",
                permanent=_classify_permanent(status),
                status=status,
                path=path,
            )

        try:
            body = resp.json() if resp.content else {}
        except ValueError as exc:
            raise TradierAPIError(
                f"Tradier {method} {path} returned non-JSON body: "
                f"{(resp.text or '')[:200]}",
                permanent=True,
                status=status,
                path=path,
            ) from exc

        if not isinstance(body, dict):
            raise TradierAPIError(
                f"Tradier {method} {path} returned unexpected root type "
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

    # ------------------------------------------------------------------
    # Order write-path.
    #
    # These helpers stay additive — they do not change the signatures of
    # the read-only sync methods above. Each returns the raw
    # ``{"order": {...}}`` envelope so the executor can extract provider-
    # specific context (commission, margin, fill price) without the client
    # hiding it.
    # ------------------------------------------------------------------
    def preview_order(
        self,
        *,
        account_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """POST ``/v1/accounts/{id}/orders`` with ``preview=true``.

        ``payload`` is the form-encoded shape built by
        :func:`build_tradier_order_payload`. This helper injects
        ``preview=true`` so callers can reuse the same payload for preview
        and place.
        """

        if not account_id:
            raise TradierAPIError(
                "preview_order requires a non-empty account_id",
                permanent=True,
            )
        body = dict(payload)
        body["preview"] = "true"
        return self._post_json(
            f"/v1/accounts/{account_id}/orders",
            data=body,
        )

    def place_order(
        self,
        *,
        account_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """POST ``/v1/accounts/{id}/orders`` (no preview).

        The Tradier-assigned order identifier lives at ``order.id`` in the
        response; the executor stringifies it into
        ``OrderResult.broker_order_id``.
        """

        if not account_id:
            raise TradierAPIError(
                "place_order requires a non-empty account_id",
                permanent=True,
            )
        body = {k: v for k, v in payload.items() if k != "preview"}
        return self._post_json(
            f"/v1/accounts/{account_id}/orders",
            data=body,
        )

    def cancel_order(
        self,
        *,
        account_id: str,
        order_id: str,
    ) -> Dict[str, Any]:
        """DELETE ``/v1/accounts/{id}/orders/{order_id}``.

        Tradier returns ``{"order": {"id": ..., "status": "ok"}}`` on a
        successful cancellation request. The executor normalizes that into
        ``status="cancelled"`` for the caller.
        """

        if not account_id:
            raise TradierAPIError(
                "cancel_order requires a non-empty account_id",
                permanent=True,
            )
        if not order_id:
            raise TradierAPIError(
                "cancel_order requires a non-empty order_id",
                permanent=True,
            )
        return self._delete_json(
            f"/v1/accounts/{account_id}/orders/{order_id}"
        )

    def get_order(
        self,
        *,
        account_id: str,
        order_id: str,
    ) -> Dict[str, Any]:
        """GET ``/v1/accounts/{id}/orders/{order_id}``.

        Returns the raw ``{"order": {...}}`` envelope. The executor maps
        ``status`` / ``exec_quantity`` / ``avg_fill_price`` onto the
        ``OrderResult`` fields.
        """

        if not account_id:
            raise TradierAPIError(
                "get_order requires a non-empty account_id",
                permanent=True,
            )
        if not order_id:
            raise TradierAPIError(
                "get_order requires a non-empty order_id",
                permanent=True,
            )
        return self._get_json(
            f"/v1/accounts/{account_id}/orders/{order_id}"
        )


def build_tradier_order_payload(
    *,
    symbol: str,
    side: str,
    quantity: float,
    order_type: str,
    duration: str = "day",
    limit_price: Optional[float] = None,
    stop_price: Optional[float] = None,
    order_class: str = "equity",
) -> Dict[str, Any]:
    """Build the form-encoded payload Tradier's order endpoint expects.

    Kept as a module-level helper so the executor can test payload shaping
    without hitting the network. Tradier's ``side`` values for equity are
    ``buy|buy_to_cover|sell|sell_short``; ``order_type`` is
    ``market|limit|stop|stop_limit``; ``duration`` is ``day|gtc|pre|post``.
    """

    if not symbol:
        raise TradierAPIError("order payload requires a symbol", permanent=True)
    if quantity <= 0:
        raise TradierAPIError(
            f"order payload requires positive quantity; got {quantity}",
            permanent=True,
        )
    qty_float = float(quantity)
    payload: Dict[str, Any] = {
        "class": order_class,
        "symbol": symbol.upper(),
        "side": side.lower(),
        "quantity": (
            str(int(qty_float)) if qty_float.is_integer() else str(qty_float)
        ),
        "type": order_type.lower(),
        "duration": duration.lower(),
    }
    if limit_price is not None:
        payload["price"] = str(limit_price)
    if stop_price is not None:
        payload["stop"] = str(stop_price)
    return payload


__all__ = [
    "TradierAPIError",
    "TradierBronzeClient",
    "build_tradier_order_payload",
]
