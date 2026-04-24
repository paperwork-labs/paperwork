"""E*TRADE live executor.

Implements :class:`~app.services.execution.broker_base.BrokerExecutor` for
E*TRADE's 2-step ``preview`` → ``place`` order flow. Signed with OAuth 1.0a
HMAC-SHA1, reusing the helpers already living in
:mod:`app.services.oauth.etrade`. We do **not** re-implement the
signature primitives — if the canonicalization or HMAC path needs to
change, it changes in one place.

Safety contract
---------------
* ``environment="sandbox"`` is always registerable.
* ``environment="prod"`` requires ``settings.ETRADE_ALLOW_LIVE=True``; the
  constructor raises ``RuntimeError`` otherwise so a misconfigured router
  fails fast at **import / startup**, never at order submission time.
* Every write path calls :func:`app.services.execution.oauth_executor_mixin.ensure_broker_token`
  **before** the first HTTP call. There are no silent fallbacks: a token
  refresh failure surfaces as ``OrderResult.error`` (or a raised exception
  for preview), never as a missing broker order id.

Connection resolution
---------------------
The ``BrokerExecutor`` protocol does not carry a ``user_id`` or a
``Session``. E*TRADE needs both (plus an ``accountIdKey``) to sign a
request and refresh the token. We accept a ``connection_resolver``
callable at construction that takes an :class:`OrderRequest` and returns
``(Session, BrokerOAuthConnection, account_id_key)``. The default router
registration leaves this ``None`` so any attempt to place an order without
explicit OrderManager plumbing raises a clear error (we're deliberately
not guessing at tenant context). Tests inject their own resolver.

Endpoints
---------
* Preview: ``POST /v1/accounts/{accountIdKey}/orders/preview.json``
* Place: ``POST /v1/accounts/{accountIdKey}/orders/place.json``
* Cancel: ``PUT  /v1/accounts/{accountIdKey}/orders/cancel.json``
* Status: ``GET  /v1/accounts/{accountIdKey}/orders/{orderId}.json``

Base URLs follow the existing bronze sync client: ``apisb.etrade.com``
for sandbox and ``api.etrade.com`` for prod.

medallion: execution
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from typing import Any

import requests
from sqlalchemy.orm import Session

from app.config import settings
from app.models.broker_oauth_connection import BrokerOAuthConnection
from app.services.execution.broker_base import (
    ActionSide,
    IBOrderType,
    OrderRequest,
    OrderResult,
    PreviewResult,
)
from app.services.execution.oauth_executor_mixin import (
    TokenRefreshError,
    ensure_broker_token,
)
from app.services.oauth.encryption import decrypt
from app.services.oauth.etrade import (
    _build_oauth_header,
    _nonce,
    _timestamp,
    build_signature_base_string,
    sign_hmac_sha1,
)

logger = logging.getLogger(__name__)


#: Resolver signature: given an OrderRequest, return the DB session, the
#: caller's E*TRADE OAuth connection, and the target ``accountIdKey``.
ConnectionResolver = Callable[[OrderRequest], tuple[Session, BrokerOAuthConnection, str]]


SANDBOX_BASE = "https://apisb.etrade.com"
PROD_BASE = "https://api.etrade.com"

#: Maps the generic :class:`IBOrderType` to E*TRADE's ``priceType`` field.
_PRICE_TYPE_MAP: dict[IBOrderType, str] = {
    IBOrderType.MKT: "MARKET",
    IBOrderType.LMT: "LIMIT",
    IBOrderType.STP: "STOP",
    IBOrderType.STP_LMT: "STOP_LIMIT",
}


class ETradeExecutor:
    """BrokerExecutor for E*TRADE live orders (sandbox + prod).

    Parameters
    ----------
    environment:
        ``"sandbox"`` or ``"prod"``. Prod is gated behind
        ``settings.ETRADE_ALLOW_LIVE``; otherwise the constructor raises.
    consumer_key / consumer_secret:
        OAuth 1.0a application credentials. When unset we fall back to
        ``settings.ETRADE_SANDBOX_KEY`` / ``ETRADE_SANDBOX_SECRET``. The
        founder must provision real production credentials out-of-band
        before flipping ``ETRADE_ALLOW_LIVE``.
    connection_resolver:
        Callable that maps an :class:`OrderRequest` to
        ``(Session, BrokerOAuthConnection, account_id_key)``. The router
        registers the executor without a resolver; tests and the future
        OrderManager integration inject one explicitly.
    session:
        Optional ``requests.Session`` for dependency injection in tests.
    timeout_s:
        Per-request HTTP timeout.
    """

    def __init__(
        self,
        *,
        environment: str = "sandbox",
        consumer_key: str | None = None,
        consumer_secret: str | None = None,
        connection_resolver: ConnectionResolver | None = None,
        session: requests.Session | None = None,
        timeout_s: float = 15.0,
    ) -> None:
        env = (environment or "sandbox").lower().strip()
        if env not in ("sandbox", "prod"):
            raise ValueError(
                f"ETradeExecutor environment must be 'sandbox' or 'prod', got {environment!r}"
            )
        if env == "prod" and not bool(getattr(settings, "ETRADE_ALLOW_LIVE", False)):
            raise RuntimeError("E*TRADE live orders disabled; set ETRADE_ALLOW_LIVE=true")

        self._environment = env
        self._base_url = SANDBOX_BASE if env == "sandbox" else PROD_BASE
        # Sandbox keys are the only ones plumbed through config today
        # (F2 is deliberately scoped to the feature flag + executor; prod
        # credential provisioning is a follow-up). Explicit consumer_key /
        # consumer_secret wins so operators can inject prod creds at
        # registration time without touching settings.
        self._consumer_key = consumer_key or getattr(settings, "ETRADE_SANDBOX_KEY", None)
        self._consumer_secret = consumer_secret or getattr(settings, "ETRADE_SANDBOX_SECRET", None)
        self._resolver = connection_resolver
        self._session = session or requests.Session()
        self._timeout_s = timeout_s

        logger.info(
            "ETradeExecutor initialized environment=%s base_url=%s resolver=%s",
            self._environment,
            self._base_url,
            "present" if self._resolver is not None else "missing",
        )

    # ------------------------------------------------------------------
    # BrokerExecutor surface (protocol)
    # ------------------------------------------------------------------
    @property
    def broker_name(self) -> str:
        return "etrade" if self._environment == "prod" else "etrade_sandbox"

    async def connect(self) -> bool:
        # OAuth 1.0a executors are stateless w.r.t. HTTP connections; we
        # lean on the requests.Session keep-alive pool. The real
        # readiness check is a successful signed call, which we exercise
        # on every order.
        return True

    async def disconnect(self) -> None:
        try:
            self._session.close()
        except Exception as exc:  # pragma: no cover
            logger.warning("ETradeExecutor session close failed: %s", exc)

    def is_paper_trading(self) -> bool:
        # Sandbox is a real broker sandbox (not a paper-fill simulator),
        # but orders there never hit a real account — treat it as paper
        # for accounting tagging so nothing downstream mistakes a
        # sandbox fill for a live one.
        return self._environment == "sandbox"

    # ------------------------------------------------------------------
    # Public async broker operations
    # ------------------------------------------------------------------
    async def preview_order(self, req: OrderRequest) -> PreviewResult:
        try:
            db, conn, account_id_key = self._require_context(req)
        except RuntimeError as exc:
            return PreviewResult(error=str(exc))

        try:
            await self._ensure_token_async(db, conn)
        except TokenRefreshError as exc:
            return PreviewResult(
                error=f"token refresh failed: {exc}",
                raw={"broker": self.broker_name},
            )

        payload = self._build_order_payload(req, wrapper="PreviewOrderRequest")
        path = f"/v1/accounts/{account_id_key}/orders/preview.json"

        try:
            body = await self._signed_json_request("POST", path, conn, json_body=payload)
        except _ETradeHTTPError as exc:
            logger.warning("E*TRADE preview HTTP %s on %s: %s", exc.status, path, exc.detail)
            return PreviewResult(
                error=f"E*TRADE preview failed: HTTP {exc.status} {exc.detail[:200]}",
                raw={"broker": self.broker_name, "status": exc.status},
            )

        preview_id = _extract_preview_id(body)
        if preview_id is None:
            return PreviewResult(
                error="E*TRADE preview response missing previewId",
                raw={"broker": self.broker_name, "response": body},
            )
        return PreviewResult(
            raw={
                "broker": self.broker_name,
                "preview_id": preview_id,
                "response": body,
            },
        )

    async def place_order(self, req: OrderRequest) -> OrderResult:
        try:
            db, conn, account_id_key = self._require_context(req)
        except RuntimeError as exc:
            return OrderResult(error=str(exc))

        try:
            await self._ensure_token_async(db, conn)
        except TokenRefreshError as exc:
            return OrderResult(
                error=f"token refresh failed: {exc}",
                raw={"broker": self.broker_name},
            )

        # Step 1: preview to obtain previewId. We share the same
        # clientOrderId across both calls so E*TRADE ties them.
        client_order_id = _client_order_id()

        preview_payload = self._build_order_payload(
            req,
            wrapper="PreviewOrderRequest",
            client_order_id=client_order_id,
        )
        preview_path = f"/v1/accounts/{account_id_key}/orders/preview.json"
        try:
            preview_body = await self._signed_json_request(
                "POST", preview_path, conn, json_body=preview_payload
            )
        except _ETradeHTTPError as exc:
            logger.warning(
                "E*TRADE place (preview step) HTTP %s on %s: %s",
                exc.status,
                preview_path,
                exc.detail,
            )
            return OrderResult(
                error=f"E*TRADE preview failed: HTTP {exc.status} {exc.detail[:200]}",
                raw={"broker": self.broker_name, "status": exc.status, "stage": "preview"},
            )

        preview_id = _extract_preview_id(preview_body)
        if preview_id is None:
            return OrderResult(
                error="E*TRADE preview response missing previewId",
                raw={"broker": self.broker_name, "response": preview_body, "stage": "preview"},
            )

        # Step 2: place with the echoed previewId.
        place_payload = self._build_order_payload(
            req,
            wrapper="PlaceOrderRequest",
            client_order_id=client_order_id,
            preview_id=preview_id,
        )
        place_path = f"/v1/accounts/{account_id_key}/orders/place.json"
        try:
            place_body = await self._signed_json_request(
                "POST", place_path, conn, json_body=place_payload
            )
        except _ETradeHTTPError as exc:
            logger.warning(
                "E*TRADE place HTTP %s on %s: %s",
                exc.status,
                place_path,
                exc.detail,
            )
            return OrderResult(
                error=f"E*TRADE place failed: HTTP {exc.status} {exc.detail[:200]}",
                raw={
                    "broker": self.broker_name,
                    "status": exc.status,
                    "stage": "place",
                    "preview_id": preview_id,
                },
            )

        order_id = _extract_order_id(place_body)
        if order_id is None:
            return OrderResult(
                error="E*TRADE place response missing orderId",
                raw={
                    "broker": self.broker_name,
                    "response": place_body,
                    "preview_id": preview_id,
                },
            )
        return OrderResult(
            broker_order_id=str(order_id),
            status="submitted",
            raw={
                "broker": self.broker_name,
                "preview_id": preview_id,
                "client_order_id": client_order_id,
                "response": place_body,
            },
        )

    async def cancel_order(self, broker_order_id: str) -> OrderResult:
        if not broker_order_id:
            return OrderResult(error="cancel_order requires a broker_order_id")

        try:
            db, conn, account_id_key = self._require_context_for_id(broker_order_id)
        except RuntimeError as exc:
            return OrderResult(error=str(exc))

        try:
            await self._ensure_token_async(db, conn)
        except TokenRefreshError as exc:
            return OrderResult(
                error=f"token refresh failed: {exc}",
                raw={"broker": self.broker_name, "broker_order_id": broker_order_id},
            )

        payload = {
            "CancelOrderRequest": {
                "orderId": _coerce_int(broker_order_id, broker_order_id),
            }
        }
        path = f"/v1/accounts/{account_id_key}/orders/cancel.json"
        try:
            body = await self._signed_json_request("PUT", path, conn, json_body=payload)
        except _ETradeHTTPError as exc:
            logger.warning(
                "E*TRADE cancel HTTP %s on %s: %s",
                exc.status,
                path,
                exc.detail,
            )
            return OrderResult(
                error=f"E*TRADE cancel failed: HTTP {exc.status} {exc.detail[:200]}",
                raw={
                    "broker": self.broker_name,
                    "broker_order_id": broker_order_id,
                    "status": exc.status,
                },
            )
        return OrderResult(
            broker_order_id=broker_order_id,
            status="cancelled",
            raw={"broker": self.broker_name, "response": body},
        )

    async def get_order_status(self, broker_order_id: str) -> OrderResult:
        if not broker_order_id:
            return OrderResult(error="get_order_status requires a broker_order_id")

        try:
            db, conn, account_id_key = self._require_context_for_id(broker_order_id)
        except RuntimeError as exc:
            return OrderResult(error=str(exc))

        try:
            await self._ensure_token_async(db, conn)
        except TokenRefreshError as exc:
            return OrderResult(
                error=f"token refresh failed: {exc}",
                raw={"broker": self.broker_name, "broker_order_id": broker_order_id},
            )

        path = f"/v1/accounts/{account_id_key}/orders/{broker_order_id}.json"
        try:
            body = await self._signed_json_request("GET", path, conn)
        except _ETradeHTTPError as exc:
            logger.warning(
                "E*TRADE status HTTP %s on %s: %s",
                exc.status,
                path,
                exc.detail,
            )
            return OrderResult(
                error=f"E*TRADE status failed: HTTP {exc.status} {exc.detail[:200]}",
                raw={
                    "broker": self.broker_name,
                    "broker_order_id": broker_order_id,
                    "status": exc.status,
                },
            )

        status, filled_qty, avg_price = _extract_status_fields(body)
        return OrderResult(
            broker_order_id=broker_order_id,
            status=status or "unknown",
            filled_quantity=float(filled_qty or 0),
            avg_fill_price=avg_price,
            raw={"broker": self.broker_name, "response": body},
        )

    # ------------------------------------------------------------------
    # Context resolution
    # ------------------------------------------------------------------
    def _require_context(self, req: OrderRequest) -> tuple[Session, BrokerOAuthConnection, str]:
        if self._resolver is None:
            raise RuntimeError(
                "ETradeExecutor.connection_resolver is not configured; "
                "OrderManager must inject (Session, BrokerOAuthConnection, "
                "accountIdKey) before placing an E*TRADE order"
            )
        try:
            ctx = self._resolver(req)
        except Exception as exc:
            raise RuntimeError(f"ETradeExecutor connection_resolver raised: {exc}") from exc
        return _validate_context(ctx)

    def _require_context_for_id(
        self, broker_order_id: str
    ) -> tuple[Session, BrokerOAuthConnection, str]:
        """Variant used by cancel / status where we only have an order id.

        The resolver receives a synthetic :class:`OrderRequest` carrying
        the ``broker_order_id`` in ``account_id`` so callers can pick
        the right ``BrokerOAuthConnection`` and ``accountIdKey``.
        """
        synthetic = OrderRequest(
            symbol="",
            side=ActionSide.BUY,
            order_type=IBOrderType.MKT,
            quantity=0,
            account_id=broker_order_id,
        )
        return self._require_context(synthetic)

    # ------------------------------------------------------------------
    # Token freshness (per-connection OAuth refresh lock)
    # ------------------------------------------------------------------
    async def _ensure_token_async(self, db: Session, conn: BrokerOAuthConnection) -> None:
        """Run the sync ensure_broker_token mixin in a worker thread.

        The mixin is intentionally sync (Redis + SQLAlchemy). Wrapping in
        ``asyncio.to_thread`` keeps the executor's async surface honest
        without requiring an async Redis client here.
        """
        await asyncio.to_thread(ensure_broker_token, db, conn)

    # ------------------------------------------------------------------
    # HTTP signing & transport
    # ------------------------------------------------------------------
    async def _signed_json_request(
        self,
        method: str,
        path: str,
        conn: BrokerOAuthConnection,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        access_token, token_secret = self._decrypt_tokens(conn)
        url = f"{self._base_url}{path}"
        headers = self._build_auth_header(
            method=method,
            url=url,
            access_token=access_token,
            token_secret=token_secret,
        )
        headers["Accept"] = "application/json"
        if json_body is not None:
            headers["Content-Type"] = "application/json"

        def _do_request() -> requests.Response:
            return self._session.request(
                method.upper(),
                url,
                headers=headers,
                json=json_body if json_body is not None else None,
                timeout=self._timeout_s,
            )

        try:
            resp = await asyncio.to_thread(_do_request)
        except requests.RequestException as exc:
            raise _ETradeHTTPError(status=0, detail=f"network error: {exc}") from exc

        status = resp.status_code
        if status >= 400:
            raise _ETradeHTTPError(status=status, detail=(resp.text or "")[:500])
        try:
            parsed = resp.json() if resp.content else {}
        except ValueError as exc:
            raise _ETradeHTTPError(
                status=status,
                detail=f"non-JSON body: {(resp.text or '')[:200]}",
            ) from exc
        if not isinstance(parsed, dict):
            raise _ETradeHTTPError(
                status=status,
                detail=f"unexpected JSON root: {type(parsed).__name__}",
            )
        return parsed

    def _build_auth_header(
        self,
        *,
        method: str,
        url: str,
        access_token: str,
        token_secret: str,
    ) -> dict[str, str]:
        if not self._consumer_key or not self._consumer_secret:
            raise RuntimeError(
                "ETradeExecutor missing consumer_key / consumer_secret; "
                "configure ETRADE_SANDBOX_KEY/SECRET or inject explicitly"
            )
        params: dict[str, str] = {
            "oauth_consumer_key": self._consumer_key,
            "oauth_nonce": _nonce(),
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": _timestamp(),
            "oauth_token": access_token,
            "oauth_version": "1.0",
        }
        base = build_signature_base_string(method, url, params)
        params["oauth_signature"] = sign_hmac_sha1(base, self._consumer_secret, token_secret)
        return {"Authorization": _build_oauth_header(params)}

    def _decrypt_tokens(self, conn: BrokerOAuthConnection) -> tuple[str, str]:
        """Return ``(access_token, token_secret)`` from an OAuth connection.

        For OAuth 1.0a brokers (E*TRADE) the ``refresh_token_encrypted``
        column stores the access token secret — see the model docstring.
        """
        if not conn.access_token_encrypted or not conn.refresh_token_encrypted:
            raise RuntimeError(
                f"E*TRADE connection {conn.id} missing access_token or "
                f"token_secret; re-authorize the account"
            )
        try:
            access = decrypt(conn.access_token_encrypted)
            secret = decrypt(conn.refresh_token_encrypted)
        except Exception as exc:
            raise RuntimeError(f"E*TRADE connection {conn.id} token decrypt failed: {exc}") from exc
        if not access or not secret:
            raise RuntimeError(f"E*TRADE connection {conn.id} decrypted token is empty")
        return access, secret

    # ------------------------------------------------------------------
    # Order payload construction
    # ------------------------------------------------------------------
    def _build_order_payload(
        self,
        req: OrderRequest,
        *,
        wrapper: str,
        client_order_id: str | None = None,
        preview_id: int | None = None,
    ) -> dict[str, Any]:
        """Build an E*TRADE Order payload wrapped in the appropriate envelope.

        ``wrapper`` is ``PreviewOrderRequest`` for step 1 and
        ``PlaceOrderRequest`` for step 2. The place request echoes the
        preview id; everything else is identical.
        """
        price_type = _PRICE_TYPE_MAP.get(req.order_type, "MARKET")
        order: dict[str, Any] = {
            "allOrNone": False,
            "priceType": price_type,
            "orderTerm": "GOOD_FOR_DAY",
            "marketSession": "REGULAR",
            "Instrument": [
                {
                    "Product": {"securityType": "EQ", "symbol": req.symbol},
                    "orderAction": req.side.value,
                    "quantityType": "QUANTITY",
                    "quantity": req.quantity,
                }
            ],
        }
        if req.limit_price is not None and price_type in ("LIMIT", "STOP_LIMIT"):
            order["limitPrice"] = req.limit_price
        if req.stop_price is not None and price_type in ("STOP", "STOP_LIMIT"):
            order["stopPrice"] = req.stop_price

        envelope: dict[str, Any] = {
            "orderType": "EQ",
            "clientOrderId": client_order_id or _client_order_id(),
            "Order": [order],
        }
        if preview_id is not None:
            envelope["PreviewIds"] = [{"previewId": preview_id}]
        return {wrapper: envelope}


# ----------------------------------------------------------------------
# Module-level helpers (kept out of the class for testability)
# ----------------------------------------------------------------------


class _ETradeHTTPError(Exception):
    """Signals a non-2xx (or network) response from E*TRADE.

    Kept module-private; callers inside this file translate into
    ``OrderResult.error`` / ``PreviewResult.error`` so upstream never sees
    a raw HTTP object.
    """

    def __init__(self, *, status: int, detail: str) -> None:
        super().__init__(f"E*TRADE HTTP {status}: {detail[:200]}")
        self.status = status
        self.detail = detail


def _client_order_id() -> str:
    """E*TRADE allows up to 20 alphanumeric chars; uuid4 hex ≤ 20 is fine."""

    return uuid.uuid4().hex[:20]


def _coerce_int(value: Any, fallback: Any) -> Any:
    """Return ``int(value)`` when possible, else ``fallback``."""

    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _validate_context(
    ctx: tuple[Any, Any, Any],
) -> tuple[Session, BrokerOAuthConnection, str]:
    if not isinstance(ctx, tuple) or len(ctx) != 3:
        raise RuntimeError(
            "connection_resolver must return (Session, BrokerOAuthConnection, account_id_key)"
        )
    db, conn, account_id_key = ctx
    if conn is None:
        raise RuntimeError("connection_resolver returned None for BrokerOAuthConnection")
    if not account_id_key:
        raise RuntimeError("connection_resolver returned empty accountIdKey")
    return db, conn, str(account_id_key)


def _extract_preview_id(body: dict[str, Any]) -> int | None:
    """Pick the first ``previewId`` out of E*TRADE's nested response.

    Shape: ``PreviewOrderResponse.PreviewIds[].previewId``.
    """
    resp = body.get("PreviewOrderResponse") or {}
    ids = resp.get("PreviewIds") or []
    if isinstance(ids, dict):
        ids = [ids]
    for entry in ids:
        if isinstance(entry, dict) and "previewId" in entry:
            return _coerce_int(entry["previewId"], entry["previewId"])
    return None


def _extract_order_id(body: dict[str, Any]) -> Any | None:
    """Pick the first ``orderId`` from a PlaceOrderResponse.

    Shape: ``PlaceOrderResponse.OrderIds[].orderId``.
    """
    resp = body.get("PlaceOrderResponse") or {}
    ids = resp.get("OrderIds") or []
    if isinstance(ids, dict):
        ids = [ids]
    for entry in ids:
        if isinstance(entry, dict) and "orderId" in entry:
            return entry["orderId"]
    return None


def _extract_status_fields(
    body: dict[str, Any],
) -> tuple[str | None, float | None, float | None]:
    """Return ``(status, filled_quantity, avg_fill_price)`` from an
    OrdersResponse payload. Best-effort — E*TRADE's schema nests an
    ``OrderDetail`` list under each order; we pick the first detail.
    """
    resp = body.get("OrdersResponse") or {}
    orders = resp.get("Order") or []
    if isinstance(orders, dict):
        orders = [orders]
    if not orders:
        return None, None, None
    first = orders[0]
    details = first.get("OrderDetail") or []
    if isinstance(details, dict):
        details = [details]
    detail = details[0] if details else {}
    status = detail.get("status") or first.get("status")
    filled_qty: float | None
    try:
        filled_qty = (
            float(detail.get("filledQuantity"))
            if detail.get("filledQuantity") is not None
            else None
        )
    except (TypeError, ValueError):
        filled_qty = None
    avg_price: float | None
    try:
        avg_price = (
            float(detail.get("averageExecutionPrice"))
            if detail.get("averageExecutionPrice") is not None
            else None
        )
    except (TypeError, ValueError):
        avg_price = None
    return status, filled_qty, avg_price


__all__ = ["ETradeExecutor"]
