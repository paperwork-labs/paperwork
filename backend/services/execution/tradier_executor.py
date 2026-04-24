"""Tradier live executor — satisfies the :class:`BrokerExecutor` protocol.

The first OAuth-backed live executor in the codebase. It uses the
per-connection token-refresh lock from
:mod:`backend.services.execution.oauth_executor_mixin` and the extended
Tradier HTTP helpers from :mod:`backend.services.bronze.tradier.client`.

Design notes
------------
* One class, two registrations. ``TradierExecutor(environment="prod")`` is
  registered as ``tradier``; ``TradierExecutor(environment="sandbox")`` is
  registered as ``tradier_sandbox``. The only difference is the base URL,
  the ``_broker_slug`` used to look up OAuth connections, and the
  ``is_paper_trading()`` return value (sandbox is "paper-ish" — no real
  capital moves).
* Per-call DB + connection load. Tradier is multi-user: each order is
  scoped to a ``BrokerOAuthConnection`` row keyed by ``(user_id, broker,
  provider_account_id)``. ``preview_order`` and ``place_order`` use
  ``req.account_id`` (the Tradier ``VA...`` account number) as the
  ``provider_account_id`` lookup key. ``cancel_order`` and
  ``get_order_status`` resolve the account via the persisted
  :class:`backend.models.order.Order` row keyed by ``broker_order_id``.
* Token freshness. Every write method calls :func:`ensure_broker_token`
  *first* so an expired access-token never reaches Tradier. The mixin
  serializes refresh attempts under a Redis lock to prevent a thundering
  herd during burst trading.
* Error surface. :class:`TradierAPIError`, :class:`TokenRefreshError`,
  and :class:`EncryptionDecryptError` are caught at the executor edge and
  converted into ``OrderResult(error=...)`` / ``PreviewResult(error=...)``
  so the caller (OrderManager) sees a typed failure rather than a raw
  ``requests`` exception. There are no silent empty-success fallbacks —
  every failure path logs at WARN with provider context.

This executor does **not** touch any DANGER ZONE file (risk_gate,
order_manager, exit_cascade, circuit_breaker, auth).

medallion: execution
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, Tuple

import requests
from sqlalchemy.orm import Session

from backend.models.broker_oauth_connection import (
    BrokerOAuthConnection,
    OAuthConnectionStatus,
)
from backend.models.order import Order
from backend.services.bronze.tradier.client import (
    TradierAPIError,
    TradierBronzeClient,
    build_tradier_order_payload,
)
from backend.services.execution.broker_base import (
    ActionSide,
    IBOrderType,
    OrderRequest,
    OrderResult,
    PreviewResult,
)
from backend.services.execution.oauth_executor_mixin import (
    TokenRefreshError,
    ensure_broker_token,
)
from backend.services.oauth.encryption import (
    EncryptionDecryptError,
    EncryptionUnavailableError,
    decrypt,
)

logger = logging.getLogger(__name__)


# Tradier's order ``type`` vocabulary maps from our ``IBOrderType`` enum.
_TRADIER_ORDER_TYPE = {
    IBOrderType.MKT: "market",
    IBOrderType.LMT: "limit",
    IBOrderType.STP: "stop",
    IBOrderType.STP_LMT: "stop_limit",
}


def _tradier_side(side: ActionSide) -> str:
    """Map our buy/sell enum onto Tradier's equity ``side`` values.

    Tradier supports ``buy|buy_to_cover|sell|sell_short`` for equity; we
    default to ``buy`` / ``sell``. Short-sell / cover routing is a later-
    wave concern.
    """

    return "buy" if side == ActionSide.BUY else "sell"


def _default_session_factory() -> Session:
    """Lazy session factory so importing this module doesn't touch the DB."""

    from backend.database import SessionLocal

    return SessionLocal()


def _as_float(value: Any) -> Optional[float]:
    """Coerce Tradier's string/number fields to float, None on failure."""

    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class TradierExecutor:
    """``BrokerExecutor`` implementation that talks to Tradier's v1 REST API."""

    def __init__(
        self,
        *,
        environment: str = "sandbox",
        session_factory: Optional[Callable[[], Session]] = None,
        http_session: Optional[requests.Session] = None,
    ) -> None:
        if environment not in ("sandbox", "prod"):
            raise ValueError(
                f"TradierExecutor environment must be 'sandbox' or 'prod'; "
                f"got {environment!r}"
            )
        self._environment = environment
        self._session_factory = session_factory or _default_session_factory
        self._http_session = http_session

    # ------------------------------------------------------------------
    # BrokerExecutor identity
    # ------------------------------------------------------------------
    @property
    def broker_name(self) -> str:
        return "tradier" if self._environment == "prod" else "tradier_sandbox"

    @property
    def _broker_slug(self) -> str:
        """OAuth broker slug stored in ``BrokerOAuthConnection.broker``."""

        return "tradier" if self._environment == "prod" else "tradier_sandbox"

    @property
    def _is_sandbox(self) -> bool:
        return self._environment == "sandbox"

    def is_paper_trading(self) -> bool:
        # Tradier sandbox is a realistic execution sim with no real capital
        # at risk; surface it as paper so downstream accounting (P&L, tax
        # lots, journal) can flag it the same way it flags PaperExecutor.
        return self._is_sandbox

    async def connect(self) -> bool:  # pragma: no cover - REST is stateless
        return True

    async def disconnect(self) -> None:  # pragma: no cover
        return None

    # ------------------------------------------------------------------
    # Connection + client plumbing
    # ------------------------------------------------------------------
    def _open_db(self) -> Session:
        return self._session_factory()

    def _load_connection_by_account(
        self,
        db: Session,
        account_id: Optional[str],
    ) -> BrokerOAuthConnection:
        """Resolve the OAuth connection for ``(broker, provider_account_id)``.

        Tradier stores the account number (``VA...``) as
        ``provider_account_id`` on the connection row. The unique index on
        ``(user_id, broker, COALESCE(provider_account_id, ''))`` means
        there's at most one match per user per account; we return the most
        recently updated one so a stale pre-reauth row cannot shadow the
        active connection.
        """

        if not account_id:
            raise ValueError(
                f"{self._broker_slug} executor requires req.account_id "
                "(Tradier account number) to resolve an OAuth connection"
            )
        conn: Optional[BrokerOAuthConnection] = (
            db.query(BrokerOAuthConnection)
            .filter(
                BrokerOAuthConnection.broker == self._broker_slug,
                BrokerOAuthConnection.provider_account_id == account_id,
            )
            .order_by(BrokerOAuthConnection.updated_at.desc())
            .first()
        )
        if conn is None:
            raise ValueError(
                f"No {self._broker_slug} OAuth connection for account "
                f"{account_id!r}; user must link the broker first"
            )
        if conn.status == OAuthConnectionStatus.REVOKED.value:
            raise ValueError(
                f"{self._broker_slug} connection {conn.id} is REVOKED; "
                "user must re-authorize"
            )
        if not conn.access_token_encrypted:
            raise ValueError(
                f"{self._broker_slug} connection {conn.id} is missing an "
                "access token; re-link on the Connections page"
            )
        return conn

    def _load_connection_by_order_id(
        self,
        db: Session,
        broker_order_id: str,
    ) -> Tuple[BrokerOAuthConnection, str]:
        """Find the OAuth connection for a previously-placed order.

        The executor persists ``Order.broker_order_id`` alongside
        ``Order.account_id`` and ``Order.broker_type``; looking the order
        up by the Tradier-assigned ID is the only way to recover the
        account number for cancel / status calls whose public signature
        only carries ``broker_order_id``.
        """

        if not broker_order_id:
            raise ValueError(
                f"{self._broker_slug} cancel/get_status requires a non-empty "
                "broker_order_id"
            )
        order: Optional[Order] = (
            db.query(Order)
            .filter(
                Order.broker_order_id == broker_order_id,
                Order.broker_type == self._broker_slug,
            )
            .order_by(Order.created_at.desc())
            .first()
        )
        if order is None:
            raise ValueError(
                f"No {self._broker_slug} order with broker_order_id="
                f"{broker_order_id!r} — cannot resolve OAuth connection"
            )
        if not order.account_id:
            raise ValueError(
                f"{self._broker_slug} order {order.id} has no account_id; "
                "cannot resolve OAuth connection"
            )
        conn = self._load_connection_by_account(db, order.account_id)
        return conn, order.account_id

    def _build_client(self, conn: BrokerOAuthConnection) -> TradierBronzeClient:
        """Decrypt the stored access token and build a :class:`TradierBronzeClient`."""

        try:
            access = decrypt(conn.access_token_encrypted)
        except (EncryptionUnavailableError, EncryptionDecryptError) as exc:
            raise ValueError(
                f"Failed to decrypt Tradier access token for connection "
                f"{conn.id}: {exc}. Re-link the account."
            ) from exc
        return TradierBronzeClient(
            access_token=access,
            sandbox=self._is_sandbox,
            session=self._http_session,
        )

    # ------------------------------------------------------------------
    # BrokerExecutor protocol: preview / place / cancel / status
    # ------------------------------------------------------------------
    async def preview_order(self, req: OrderRequest) -> PreviewResult:
        """Tradier ``POST /v1/accounts/{id}/orders?preview=true``.

        Tradier's preview response lives at ``body.order``; the fields we
        surface (``commission``, ``cost``, ``margin_change``) are the
        equity-order shape. We never silently swallow missing fields — if
        the provider returns ``status != "ok"`` we convert the response
        verbatim into ``PreviewResult.error``.
        """

        db: Optional[Session] = None
        try:
            db = self._open_db()
            conn = self._load_connection_by_account(db, req.account_id)
            # The mixin refreshes under a per-connection Redis lock and
            # commits the refreshed ciphertext before we decrypt it.
            ensure_broker_token(db, conn)
            client = self._build_client(conn)
            payload = self._build_payload(req)
            assert req.account_id is not None  # _load_connection_by_account enforced this
            raw = client.preview_order(
                account_id=req.account_id,
                payload=payload,
            )
            return self._parse_preview(raw)
        except (TradierAPIError, TokenRefreshError) as exc:
            logger.warning(
                "tradier executor: preview_order failed broker=%s account=%s symbol=%s err=%s",
                self._broker_slug, req.account_id, req.symbol, exc,
            )
            return PreviewResult(error=str(exc), raw={"broker": self._broker_slug})
        except ValueError as exc:
            # Missing account, missing token, wrong environment — these
            # are caller-side misconfigurations; log WARN and surface.
            logger.warning(
                "tradier executor: preview_order refused broker=%s account=%s err=%s",
                self._broker_slug, req.account_id, exc,
            )
            return PreviewResult(error=str(exc), raw={"broker": self._broker_slug})
        finally:
            self._safe_close(db)

    async def place_order(self, req: OrderRequest) -> OrderResult:
        """Tradier ``POST /v1/accounts/{id}/orders`` (live placement)."""

        db: Optional[Session] = None
        try:
            db = self._open_db()
            conn = self._load_connection_by_account(db, req.account_id)
            ensure_broker_token(db, conn)
            client = self._build_client(conn)
            payload = self._build_payload(req)
            assert req.account_id is not None
            raw = client.place_order(
                account_id=req.account_id,
                payload=payload,
            )
            return self._parse_place(raw)
        except (TradierAPIError, TokenRefreshError) as exc:
            logger.warning(
                "tradier executor: place_order failed broker=%s account=%s symbol=%s err=%s",
                self._broker_slug, req.account_id, req.symbol, exc,
            )
            return OrderResult(
                status="error",
                error=str(exc),
                raw={"broker": self._broker_slug},
            )
        except ValueError as exc:
            logger.warning(
                "tradier executor: place_order refused broker=%s account=%s err=%s",
                self._broker_slug, req.account_id, exc,
            )
            return OrderResult(
                status="error",
                error=str(exc),
                raw={"broker": self._broker_slug},
            )
        finally:
            self._safe_close(db)

    async def cancel_order(self, broker_order_id: str) -> OrderResult:
        """Tradier ``DELETE /v1/accounts/{id}/orders/{order_id}``.

        Tradier returns ``status="ok"`` on a successful cancel request —
        even if the order was already filled, in which case the final
        state comes from a subsequent GET. We return ``status="cancelled"``
        here (the round-trip contract); the caller can reconcile via
        ``get_order_status`` if needed.
        """

        db: Optional[Session] = None
        try:
            db = self._open_db()
            conn, account_id = self._load_connection_by_order_id(db, broker_order_id)
            ensure_broker_token(db, conn)
            client = self._build_client(conn)
            raw = client.cancel_order(
                account_id=account_id,
                order_id=broker_order_id,
            )
            order_body = raw.get("order") if isinstance(raw, dict) else None
            if not isinstance(order_body, dict) or order_body.get("status") != "ok":
                # Tradier returned 2xx but the envelope is not the
                # happy-path shape — surface as an error rather than
                # silently claim the cancel succeeded.
                return OrderResult(
                    status="error",
                    error=f"Tradier cancel response malformed: {raw!r}",
                    raw={"broker": self._broker_slug, "provider_raw": raw},
                )
            return OrderResult(
                broker_order_id=broker_order_id,
                status="cancelled",
                raw={"broker": self._broker_slug, "provider_raw": raw},
            )
        except (TradierAPIError, TokenRefreshError) as exc:
            logger.warning(
                "tradier executor: cancel_order failed broker=%s order_id=%s err=%s",
                self._broker_slug, broker_order_id, exc,
            )
            return OrderResult(
                status="error",
                error=str(exc),
                raw={"broker": self._broker_slug},
            )
        except ValueError as exc:
            logger.warning(
                "tradier executor: cancel_order refused broker=%s order_id=%s err=%s",
                self._broker_slug, broker_order_id, exc,
            )
            return OrderResult(
                status="error",
                error=str(exc),
                raw={"broker": self._broker_slug},
            )
        finally:
            self._safe_close(db)

    async def get_order_status(self, broker_order_id: str) -> OrderResult:
        """Tradier ``GET /v1/accounts/{id}/orders/{order_id}``."""

        db: Optional[Session] = None
        try:
            db = self._open_db()
            conn, account_id = self._load_connection_by_order_id(db, broker_order_id)
            ensure_broker_token(db, conn)
            client = self._build_client(conn)
            raw = client.get_order(
                account_id=account_id,
                order_id=broker_order_id,
            )
            return self._parse_status(broker_order_id, raw)
        except (TradierAPIError, TokenRefreshError) as exc:
            logger.warning(
                "tradier executor: get_order_status failed broker=%s order_id=%s err=%s",
                self._broker_slug, broker_order_id, exc,
            )
            return OrderResult(
                broker_order_id=broker_order_id,
                status="error",
                error=str(exc),
                raw={"broker": self._broker_slug},
            )
        except ValueError as exc:
            logger.warning(
                "tradier executor: get_order_status refused broker=%s order_id=%s err=%s",
                self._broker_slug, broker_order_id, exc,
            )
            return OrderResult(
                broker_order_id=broker_order_id,
                status="error",
                error=str(exc),
                raw={"broker": self._broker_slug},
            )
        finally:
            self._safe_close(db)

    # ------------------------------------------------------------------
    # Payload + response shaping
    # ------------------------------------------------------------------
    def _build_payload(self, req: OrderRequest) -> Dict[str, Any]:
        tradier_type = _TRADIER_ORDER_TYPE.get(req.order_type)
        if tradier_type is None:
            raise ValueError(
                f"Tradier executor does not support order type {req.order_type!r}"
            )
        return build_tradier_order_payload(
            symbol=req.symbol,
            side=_tradier_side(req.side),
            quantity=req.quantity,
            order_type=tradier_type,
            limit_price=req.limit_price,
            stop_price=req.stop_price,
        )

    def _parse_preview(self, raw: Dict[str, Any]) -> PreviewResult:
        order_body = raw.get("order") if isinstance(raw, dict) else None
        if not isinstance(order_body, dict):
            return PreviewResult(
                error=f"Tradier preview response malformed: {raw!r}",
                raw={"broker": self._broker_slug, "provider_raw": raw},
            )
        if order_body.get("status") != "ok":
            # Tradier may return a 200 with status="rejected" and a
            # message. Surface it rather than pretend preview succeeded.
            message = (
                order_body.get("message")
                or order_body.get("description")
                or f"status={order_body.get('status')!r}"
            )
            return PreviewResult(
                error=f"Tradier preview rejected: {message}",
                raw={"broker": self._broker_slug, "provider_raw": raw},
            )
        return PreviewResult(
            estimated_commission=_as_float(order_body.get("commission")),
            estimated_margin_impact=_as_float(order_body.get("margin_change")),
            raw={"broker": self._broker_slug, "provider_raw": raw},
        )

    def _parse_place(self, raw: Dict[str, Any]) -> OrderResult:
        order_body = raw.get("order") if isinstance(raw, dict) else None
        if not isinstance(order_body, dict):
            return OrderResult(
                status="error",
                error=f"Tradier place response malformed: {raw!r}",
                raw={"broker": self._broker_slug, "provider_raw": raw},
            )
        if order_body.get("status") != "ok":
            message = (
                order_body.get("message")
                or order_body.get("description")
                or f"status={order_body.get('status')!r}"
            )
            return OrderResult(
                status="error",
                error=f"Tradier place rejected: {message}",
                raw={"broker": self._broker_slug, "provider_raw": raw},
            )
        broker_id = order_body.get("id")
        if broker_id in (None, ""):
            # Protocol requires ``broker_order_id`` populated on a
            # successful placement. Treat missing id as an error so the
            # cancel round-trip cannot silently become a no-op.
            return OrderResult(
                status="error",
                error=f"Tradier place response missing order.id: {raw!r}",
                raw={"broker": self._broker_slug, "provider_raw": raw},
            )
        return OrderResult(
            broker_order_id=str(broker_id),
            status="submitted",
            raw={"broker": self._broker_slug, "provider_raw": raw},
        )

    def _parse_status(
        self, broker_order_id: str, raw: Dict[str, Any]
    ) -> OrderResult:
        order_body = raw.get("order") if isinstance(raw, dict) else None
        if not isinstance(order_body, dict):
            return OrderResult(
                broker_order_id=broker_order_id,
                status="error",
                error=f"Tradier get_order response malformed: {raw!r}",
                raw={"broker": self._broker_slug, "provider_raw": raw},
            )
        status = order_body.get("status") or "unknown"
        exec_qty = _as_float(order_body.get("exec_quantity")) or 0.0
        avg_price = _as_float(order_body.get("avg_fill_price"))
        return OrderResult(
            broker_order_id=broker_order_id,
            status=str(status),
            filled_quantity=exec_qty,
            avg_fill_price=avg_price,
            raw={"broker": self._broker_slug, "provider_raw": raw},
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _safe_close(db: Optional[Session]) -> None:
        if db is None:
            return
        try:
            db.close()
        except Exception as exc:  # pragma: no cover — best-effort teardown
            logger.warning("tradier executor: db close failed err=%s", exc)


__all__ = ["TradierExecutor"]
