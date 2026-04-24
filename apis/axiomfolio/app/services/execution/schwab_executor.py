"""Schwab live executor.

Adapts :class:`~app.services.clients.schwab_client.SchwabClient` to the
:class:`~app.services.execution.broker_base.BrokerExecutor` protocol.
Together with the write-path methods on ``SchwabClient`` this replaces
the ``not_implemented`` stub that was previously the only trading path
to Schwab.

Schwab-specific behavior
------------------------
* **``account_hash`` is resolved per write call.** Schwab Trader API requires
  the opaque ``accountHash`` rather than the plain account number. The hash
  is rotated whenever the user re-authorizes or links/unlinks accounts, so
  caching it across calls is unsafe (see `.cursor/rules/no-silent-fallback`).
  Every ``place_order`` / ``cancel_order`` / ``get_order_status`` /
  ``preview_order`` hits :meth:`SchwabClient.resolve_account_hash_fresh` so
  one ``GET /accounts/accountNumbers`` lookup occurs per write.
* **``ensure_broker_token`` runs first.** Every write path uses the
  shared OAuth-refresh helper so the access token is refreshed under a
  Redis lock before any Schwab HTTPS call. A failed refresh is surfaced
  as ``OrderResult.error`` (never silently swallowed).
* **Status is polled, not pushed.** Schwab does not send async order status
  updates, so :meth:`SchwabExecutor.get_order_status` hits the order
  endpoint each call; callers that need live updates must poll.

Context binding
---------------
Because :class:`BrokerExecutor` methods accept only the ``OrderRequest`` /
``broker_order_id`` arguments, OAuth connection resolution is injected at
construction time via ``context_resolver``. ``context_resolver()`` returns
``(Session, BrokerOAuthConnection)`` for the current caller. The default
resolver raises -- the router-registered singleton is not callable until
``order_manager`` wires a real resolver in a follow-up PR (this is the
same pattern F1/F2/F4 will use).

medallion: execution
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.models.broker_oauth_connection import BrokerOAuthConnection
from app.services.execution.broker_base import (
    OrderRequest,
    OrderResult,
    PreviewResult,
)
from app.services.execution.oauth_executor_mixin import (
    TokenRefreshError,
    ensure_broker_token,
)
from app.services.oauth.encryption import decrypt

logger = logging.getLogger(__name__)


ContextResolver = Callable[[], tuple[Session, BrokerOAuthConnection]]
ClientFactory = Callable[[], Any]


class SchwabExecutor:
    """BrokerExecutor implementation backed by the Schwab Trader API client."""

    def __init__(
        self,
        context_resolver: ContextResolver | None = None,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self._context_resolver = context_resolver
        self._client_factory = client_factory

    # -- Protocol metadata --------------------------------------------------

    @property
    def broker_name(self) -> str:
        return "schwab"

    async def connect(self) -> bool:
        # No persistent connection -- credentials are resolved per-call.
        return True

    async def disconnect(self) -> None:
        return None

    def is_paper_trading(self) -> bool:
        return False

    def bind_context_resolver(self, resolver: ContextResolver) -> None:
        """Wire a resolver after construction.

        Lets the registered singleton in ``broker_router.create_default_router``
        be upgraded at runtime once :mod:`app.services.execution.order_manager`
        provides a per-request user/connection context (follow-up PR).
        """
        self._context_resolver = resolver

    # -- Internal helpers ---------------------------------------------------

    def _build_client(self):
        """Instantiate a fresh ``SchwabClient``.

        We deliberately do NOT keep a long-lived client around: every call
        re-decrypts tokens, re-resolves the account hash, and opens a fresh
        aiohttp session. This eliminates cross-user token bleed, stale-hash
        reuse, and guarantees the "one hash lookup per write" property the
        F3 acceptance tests assert.
        """
        if self._client_factory is not None:
            return self._client_factory()
        # Lazy import to avoid circulars: SchwabClient imports settings.
        from app.services.clients.schwab_client import SchwabClient

        return SchwabClient()

    async def _prepare(
        self,
        account_id_override: str | None = None,
    ) -> tuple[Any, str, dict[str, Any]]:
        """Resolve context + credentials + a fresh account hash.

        Returns a triple ``(client, account_hash, raw_context)`` where
        ``raw_context`` is attached to error payloads for observability.

        Raises a plain :class:`RuntimeError` when the resolver / token
        pipeline fails. Callers translate that into an ``OrderResult`` with
        a populated ``error`` field.
        """
        if self._context_resolver is None:
            raise RuntimeError(
                "SchwabExecutor is not bound to an OAuth context resolver; "
                "call bind_context_resolver() before invoking a write method"
            )

        try:
            db, connection = self._context_resolver()
        except Exception as exc:
            logger.warning("SchwabExecutor context resolver failed: %s", exc)
            raise RuntimeError(f"context resolver failed: {exc}") from exc

        if connection is None:
            raise RuntimeError("SchwabExecutor: context resolver returned no connection")

        try:
            ensure_broker_token(db, connection)
        except TokenRefreshError as exc:
            logger.warning(
                "SchwabExecutor token refresh failed for connection=%s: %s",
                connection.id,
                exc,
            )
            raise RuntimeError(f"token refresh failed: {exc}") from exc

        try:
            access_token = decrypt(connection.access_token_encrypted)
            refresh_token = decrypt(connection.refresh_token_encrypted)
        except Exception as exc:
            logger.warning(
                "SchwabExecutor token decrypt failed for connection=%s: %s",
                connection.id,
                exc,
            )
            raise RuntimeError(f"token decrypt failed: {exc}") from exc

        account_id = account_id_override or connection.provider_account_id
        if not account_id:
            raise RuntimeError(
                "SchwabExecutor: no account_id available (neither OrderRequest "
                "nor BrokerOAuthConnection.provider_account_id set)"
            )

        client = self._build_client()
        connected = await client.connect_with_credentials(access_token, refresh_token)
        if not connected:
            raise RuntimeError("SchwabExecutor: schwab client failed to connect with credentials")

        account_hash = await client.resolve_account_hash_fresh(account_id)
        if not account_hash:
            raise RuntimeError(
                f"SchwabExecutor: could not resolve account_hash for account_id={account_id!r}"
            )

        return (
            client,
            account_hash,
            {
                "connection_id": connection.id,
                "account_id": account_id,
            },
        )

    # Map our internal IBKR-style IBOrderType enum to Schwab's vocabulary.
    # IBKR style is the canonical one in OrderRequest (see
    # app/services/execution/broker_base.py ``IBOrderType``).
    _SCHWAB_ORDER_TYPE_MAP: dict[str, str] = {
        "MKT": "MARKET",
        "LMT": "LIMIT",
        "STP": "STOP",
        "STP_LMT": "STOP_LIMIT",
    }

    @classmethod
    def _payload_for(cls, req: OrderRequest) -> dict[str, Any]:
        from app.services.clients.schwab_client import SchwabClient

        schwab_type = cls._SCHWAB_ORDER_TYPE_MAP.get(req.order_type.value)
        if schwab_type is None:
            raise ValueError(f"unsupported Schwab orderType: {req.order_type.value!r}")
        return SchwabClient.build_order_payload(
            symbol=req.symbol,
            side=req.side.value,
            quantity=req.quantity,
            order_type=schwab_type,
            limit_price=req.limit_price,
            stop_price=req.stop_price,
        )

    # -- BrokerExecutor surface --------------------------------------------

    async def preview_order(self, req: OrderRequest) -> PreviewResult:
        try:
            client, account_hash, ctx = await self._prepare(
                account_id_override=req.account_id,
            )
        except RuntimeError as exc:
            return PreviewResult(error=str(exc), raw={"broker": "schwab"})

        try:
            payload = self._payload_for(req)
        except ValueError as exc:
            return PreviewResult(error=str(exc), raw={"broker": "schwab", **ctx})

        raw = await client.preview_order(account_hash, payload)
        if raw.get("error"):
            return PreviewResult(
                error=raw["error"],
                raw={"broker": "schwab", **ctx, **raw},
            )
        return PreviewResult(
            estimated_commission=raw.get("estimated_commission"),
            estimated_margin_impact=raw.get("estimated_margin_impact"),
            estimated_equity_with_loan=raw.get("estimated_equity_with_loan"),
            raw={"broker": "schwab", **ctx, **raw},
        )

    async def place_order(self, req: OrderRequest) -> OrderResult:
        try:
            client, account_hash, ctx = await self._prepare(
                account_id_override=req.account_id,
            )
        except RuntimeError as exc:
            return OrderResult(error=str(exc), raw={"broker": "schwab"})

        try:
            payload = self._payload_for(req)
        except ValueError as exc:
            return OrderResult(error=str(exc), raw={"broker": "schwab", **ctx})

        raw = await client.place_order(account_hash, payload)
        if raw.get("error"):
            return OrderResult(
                status="error",
                error=raw["error"],
                raw={"broker": "schwab", **ctx, **raw},
            )
        return OrderResult(
            broker_order_id=raw.get("broker_order_id"),
            status=raw.get("status", "submitted"),
            raw={"broker": "schwab", **ctx, **raw},
        )

    async def cancel_order(self, broker_order_id: str) -> OrderResult:
        try:
            client, account_hash, ctx = await self._prepare()
        except RuntimeError as exc:
            return OrderResult(error=str(exc), raw={"broker": "schwab"})

        raw = await client.cancel_order(account_hash, broker_order_id)
        if raw.get("error"):
            return OrderResult(
                broker_order_id=broker_order_id,
                status="error",
                error=raw["error"],
                raw={"broker": "schwab", **ctx, **raw},
            )
        return OrderResult(
            broker_order_id=broker_order_id,
            status=raw.get("status", "cancelled"),
            raw={"broker": "schwab", **ctx, **raw},
        )

    async def get_order_status(self, broker_order_id: str) -> OrderResult:
        """Poll Schwab for the latest order status.

        Schwab does not push status; every call hits the order endpoint.
        """
        try:
            client, account_hash, ctx = await self._prepare()
        except RuntimeError as exc:
            return OrderResult(
                broker_order_id=broker_order_id,
                error=str(exc),
                raw={"broker": "schwab"},
            )

        raw = await client.get_order_status(account_hash, broker_order_id)
        if raw.get("error"):
            return OrderResult(
                broker_order_id=broker_order_id,
                status="error",
                error=raw["error"],
                raw={"broker": "schwab", **ctx, **raw},
            )
        return OrderResult(
            broker_order_id=broker_order_id,
            status=raw.get("status", "unknown"),
            filled_quantity=float(raw.get("filled_quantity") or 0.0),
            avg_fill_price=raw.get("avg_fill_price"),
            raw={"broker": "schwab", **ctx, **raw},
        )


__all__ = ["SchwabExecutor"]
