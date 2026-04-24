"""Plaid SDK wrapper with env-aware configuration and Fernet token I/O.

Why a wrapper (vs. calling ``plaid_api.PlaidApi`` directly in routes / the
sync service):

1. **Environment resolution** — the SDK exposes three base URLs via
   ``plaid.Environment``. Dev/CI must default to ``sandbox``; prod only
   switches when the founder sets ``PLAID_ENV=production``. Centralising
   keeps every caller in one place.
2. **Encryption boundary** — callers in this codebase ALWAYS pass the
   Fernet ciphertext stored on :class:`PlaidConnection`. The wrapper
   decrypts once at the entry point so that plaintext lives only on the
   stack of the Plaid call itself; it's never passed around or logged
   (``.cursor/rules/no-silent-fallback.mdc``: secrets are a silent-fail
   class we can't afford).
3. **Structured errors** — Plaid raises
   :class:`plaid.exceptions.ApiException` with a JSON ``body`` containing
   ``error_code``. We translate to :class:`PlaidAPIError` so sync-service
   code can pattern-match on ``error_code`` (notably ``ITEM_LOGIN_REQUIRED``
   → ``needs_reauth``) without leaking SDK internals.
4. **Missing-config loudness** — routes must 503 when Plaid isn't
   configured in a given environment; the wrapper raises
   :class:`PlaidConfigurationError` rather than silently falling back to a
   sandbox client (which would send prod webhooks to sandbox and other
   fun outage modes).

See plan ``docs/plans/PLAID_FIDELITY_401K.md`` §4.

medallion: silver
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from plaid import Configuration, ApiClient, Environment
from plaid.api import plaid_api
from plaid.exceptions import ApiException
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.country_code import CountryCode
from plaid.model.investments_holdings_get_request import (
    InvestmentsHoldingsGetRequest,
)
from plaid.model.item_public_token_exchange_request import (
    ItemPublicTokenExchangeRequest,
)
from plaid.model.item_remove_request import ItemRemoveRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import (
    LinkTokenCreateRequestUser,
)
from plaid.model.products import Products

from backend.config import settings
from backend.services.oauth.encryption import decrypt, encrypt

logger = logging.getLogger(__name__)


class PlaidConfigurationError(RuntimeError):
    """Raised when required Plaid settings are missing or invalid.

    Routes should translate this into HTTP 503; the Celery task should
    mark the run as errored (never silently skipped).
    """


class PlaidAPIError(RuntimeError):
    """Raised when the Plaid API returns a structured error.

    Attributes:
        error_code: Plaid ``error_code`` string, e.g. ``"ITEM_LOGIN_REQUIRED"``.
        error_type: Plaid ``error_type``, e.g. ``"ITEM_ERROR"``.
        display_message: Plaid-provided human-readable message (may be None).
        request_id: Plaid request id for log correlation (may be None).
    """

    def __init__(
        self,
        message: str,
        *,
        error_code: Optional[str] = None,
        error_type: Optional[str] = None,
        display_message: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.error_type = error_type
        self.display_message = display_message
        self.request_id = request_id


_ENV_MAP = {
    "sandbox": Environment.Sandbox,
    # plaid-python 39.x removed the Development env; map to Production so
    # misconfigured ``PLAID_ENV=development`` fails in a recognisable way
    # instead of silently hitting the wrong host. Callers should use
    # ``sandbox`` for dev/CI and ``production`` for prod.
    "production": Environment.Production,
}


_COUNTRY_CODES: Tuple[CountryCode, ...] = (CountryCode("US"),)


# Known Plaid product tokens we validate against. plaid-python's
# ``Products`` constructor accepts any string (it's a free-form enum
# mixin in 39.x), so typo detection must live here — otherwise a typo
# like ``"investmennts"`` would propagate to Plaid as a cryptic
# ``INVALID_FIELD`` 400 instead of failing at config time.
_VALID_PLAID_PRODUCTS: frozenset[str] = frozenset(
    {
        "assets",
        "auth",
        "employment",
        "identity",
        "identity_verification",
        "income_verification",
        "investments",
        "investments_auth",
        "liabilities",
        "payment_initiation",
        "recurring_transactions",
        "signal",
        "standing_orders",
        "statements",
        "transactions",
        "transfer",
    }
)


def _resolve_products() -> List[Products]:
    """Parse ``PLAID_PRODUCTS`` into typed SDK enums.

    Invalid product tokens raise rather than being silently dropped; a
    typo in the env var must surface at app boot / route call, not
    manifest later as a cryptic 400 from Plaid.
    """

    raw = (settings.PLAID_PRODUCTS or "").strip()
    if not raw:
        raise PlaidConfigurationError(
            "PLAID_PRODUCTS is empty; configure at least 'investments'."
        )
    products: List[Products] = []
    for token in (p.strip() for p in raw.split(",") if p.strip()):
        if token not in _VALID_PLAID_PRODUCTS:
            raise PlaidConfigurationError(
                f"Unknown Plaid product {token!r} in PLAID_PRODUCTS; "
                f"expected one of {sorted(_VALID_PLAID_PRODUCTS)}"
            )
        try:
            products.append(Products(token))
        except ValueError as exc:  # pragma: no cover — defensive
            raise PlaidConfigurationError(
                f"Plaid SDK rejected product {token!r} in PLAID_PRODUCTS"
            ) from exc
    return products


def _extract_plaid_error(exc: ApiException) -> Dict[str, Optional[str]]:
    """Best-effort parse of a Plaid ``ApiException`` body.

    Plaid wraps errors in a JSON envelope; we parse defensively so
    malformed payloads still produce a structured error (vs. bare
    ``500 Internal Server Error`` in our logs).
    """

    body = getattr(exc, "body", None)
    if isinstance(body, (bytes, bytearray)):
        try:
            body = body.decode("utf-8")
        except UnicodeDecodeError:
            body = None
    parsed: Dict[str, Any] = {}
    if isinstance(body, str):
        try:
            parsed = json.loads(body) or {}
        except ValueError:
            parsed = {}
    elif isinstance(body, dict):
        parsed = body
    return {
        "error_code": parsed.get("error_code"),
        "error_type": parsed.get("error_type"),
        "display_message": parsed.get("display_message"),
        "request_id": parsed.get("request_id"),
    }


class PlaidClient:
    """Thin wrapper around ``plaid.api.plaid_api.PlaidApi``.

    Constructed per-request (cheap — just an SDK ``ApiClient`` handle) so
    settings changes mid-process (test fixtures, operator env rewrite via
    Render) take effect on the next call rather than being cached for the
    life of the worker.
    """

    def __init__(self) -> None:
        if not settings.PLAID_CLIENT_ID or not settings.PLAID_SECRET:
            raise PlaidConfigurationError(
                "Plaid is not configured (PLAID_CLIENT_ID / PLAID_SECRET "
                "missing). Set them in environment to enable the "
                "broker.plaid_investments feature."
            )

        env_key = (settings.PLAID_ENV or "sandbox").strip().lower()
        host = _ENV_MAP.get(env_key)
        if host is None:
            raise PlaidConfigurationError(
                f"Unknown PLAID_ENV {env_key!r}; expected 'sandbox' or "
                "'production'."
            )

        config = Configuration(
            host=host,
            api_key={
                "clientId": settings.PLAID_CLIENT_ID,
                "secret": settings.PLAID_SECRET,
                "plaidVersion": "2020-09-14",
            },
        )
        self._api_client = ApiClient(config)
        self._api = plaid_api.PlaidApi(self._api_client)
        self.environment = env_key

    # -- lifecycle --------------------------------------------------------

    @property
    def api_client(self) -> ApiClient:
        """Expose the raw SDK client (needed for webhook JWKS lookup)."""
        return self._api_client

    def close(self) -> None:
        """Release underlying HTTP resources.

        The SDK's ``ApiClient`` opens a ``urllib3.PoolManager`` — we don't
        hold onto them because :class:`PlaidClient` is per-request, but
        expose this so long-running tasks can be defensive.
        """
        try:
            self._api_client.close()
        except Exception as exc:  # pragma: no cover - best-effort cleanup
            logger.warning("PlaidClient.close() failed: %s", exc)

    # -- token utilities --------------------------------------------------

    @staticmethod
    def encrypt_access_token(plaintext: str) -> str:
        """Encrypt a plaintext Plaid access token for persistence."""
        return encrypt(plaintext)

    @staticmethod
    def decrypt_access_token(ciphertext: str) -> str:
        """Decrypt a stored ciphertext to the plaintext access token."""
        return decrypt(ciphertext)

    # -- API methods ------------------------------------------------------

    def create_link_token(
        self, *, user_id: int, client_name: str = "AxiomFolio"
    ) -> str:
        """Mint a short-lived Plaid Link token for the given user.

        ``user_id`` is stringified into ``client_user_id`` — Plaid uses it
        to de-duplicate Items across institutions per user. We use the
        ORM PK; stable across sessions and opaque to end users.
        """
        request = LinkTokenCreateRequest(
            products=_resolve_products(),
            client_name=client_name,
            country_codes=list(_COUNTRY_CODES),
            language="en",
            user=LinkTokenCreateRequestUser(client_user_id=str(user_id)),
        )
        webhook = settings.PLAID_WEBHOOK_URL
        if webhook:
            request.webhook = webhook
        try:
            response = self._api.link_token_create(request)
        except ApiException as exc:
            details = _extract_plaid_error(exc)
            logger.error(
                "plaid link_token_create failed: error_code=%s request_id=%s",
                details.get("error_code"),
                details.get("request_id"),
            )
            raise PlaidAPIError(
                "Failed to create Plaid link token", **details
            ) from exc
        return response["link_token"]

    def exchange_public_token(self, public_token: str) -> Tuple[str, str]:
        """Exchange a short-lived public token for ``(access_token, item_id)``.

        Returned ``access_token`` is PLAINTEXT — the caller is responsible
        for Fernet-encrypting it via :meth:`encrypt_access_token` BEFORE
        persisting.
        """
        request = ItemPublicTokenExchangeRequest(public_token=public_token)
        try:
            response = self._api.item_public_token_exchange(request)
        except ApiException as exc:
            details = _extract_plaid_error(exc)
            logger.error(
                "plaid item_public_token_exchange failed: error_code=%s "
                "request_id=%s",
                details.get("error_code"),
                details.get("request_id"),
            )
            raise PlaidAPIError(
                "Failed to exchange Plaid public token", **details
            ) from exc
        return response["access_token"], response["item_id"]

    def get_accounts(self, access_token_ciphertext: str) -> List[Dict[str, Any]]:
        """Return Plaid's ``accounts`` array for an Item.

        Each element includes ``account_id``, ``name``, ``type``,
        ``subtype``, and a ``balances`` sub-dict.
        """
        token = self.decrypt_access_token(access_token_ciphertext)
        try:
            response = self._api.accounts_get(AccountsGetRequest(access_token=token))
        except ApiException as exc:
            details = _extract_plaid_error(exc)
            raise PlaidAPIError(
                "Failed to fetch Plaid accounts", **details
            ) from exc
        return [a.to_dict() for a in response["accounts"]]

    def get_holdings(self, access_token_ciphertext: str) -> Dict[str, Any]:
        """Return ``{"accounts": [...], "holdings": [...], "securities": [...]}``.

        The return shape matches Plaid's ``/investments/holdings/get`` so
        the pipeline can index securities by ``security_id`` cheaply.
        """
        token = self.decrypt_access_token(access_token_ciphertext)
        request = InvestmentsHoldingsGetRequest(access_token=token)
        try:
            response = self._api.investments_holdings_get(request)
        except ApiException as exc:
            details = _extract_plaid_error(exc)
            raise PlaidAPIError(
                "Failed to fetch Plaid holdings", **details
            ) from exc
        return {
            "accounts": [a.to_dict() for a in response["accounts"]],
            "holdings": [h.to_dict() for h in response["holdings"]],
            "securities": [s.to_dict() for s in response["securities"]],
        }

    def remove_item(self, access_token_ciphertext: str) -> None:
        """Revoke an Item at Plaid; caller then marks the row ``revoked``."""
        token = self.decrypt_access_token(access_token_ciphertext)
        try:
            self._api.item_remove(ItemRemoveRequest(access_token=token))
        except ApiException as exc:
            details = _extract_plaid_error(exc)
            raise PlaidAPIError(
                "Failed to revoke Plaid item", **details
            ) from exc


__all__ = [
    "PlaidAPIError",
    "PlaidClient",
    "PlaidConfigurationError",
]
