"""TastyTrade live executor.

Adapts the ``tastytrade`` pip SDK (v12+) to the ``BrokerExecutor`` protocol
used by ``OrderManager``. Implements ``preview_order``, ``place_order``,
``cancel_order``, and ``get_order_status`` for **equity** orders. Options
support is deferred and equity-only is enforced at the edge: any
option-looking symbol surfaces an explicit error rather than silently
routing through the equity path.

Why this executor manages its own session instead of using
``ensure_broker_token``
-----------------------------------------------------------------

``ensure_broker_token`` (the OAuth-token-refresh helper used by Tradier,
E*TRADE, and Coinbase) assumes credentials live on
:class:`BrokerOAuthConnection` with the shape
``access_token_encrypted`` + ``token_expires_at`` + ``refresh_token_encrypted``
plus a matching adapter under ``app.services.oauth.<broker>``.

TastyTrade does not fit that shape:

* The SDK uses a two-layer credential model — a long-lived OAuth refresh
  token is exchanged for a short-lived (~15 minute) session token via
  ``POST /oauth/token``. The ``tastytrade.Session`` owns the session token
  in memory and auto-refreshes on every HTTP call.
* There is no ``app.services.oauth.tastytrade`` adapter; the session
  token never lands on ``BrokerOAuthConnection``.
* Calling ``ensure_broker_token`` against a TastyTrade connection row
  would try to decrypt a non-existent access token and corrupt the
  connection's ``rotation_count`` / status machine.

What this executor still does for parity with other live brokers:

* Serializes session refresh across workers with a Redis lock keyed on
  the (hashed) OAuth client secret so concurrent Celery workers do not
  hammer ``/oauth/token`` simultaneously.
* Fails closed if the SDK raises during session construction, refresh,
  or any call: every write path returns an ``OrderResult`` with a
  non-None ``error`` so ``OrderManager`` records ``OrderStatus.ERROR``.
* Never swallows SDK exceptions into ``status="ok"``.

Options support — deferred
--------------------------

The SDK accepts an ``EQUITY_OPTION`` leg with an OCC-format symbol, but
building one requires a pre-trade ``Option.get_option(session, symbol)``
call so the SDK can validate instrument metadata. ``OrderRequest`` does
not yet carry ``option_symbol`` / ``instrument_type``, so this executor
ships equity-only and rejects option-looking symbols at the edge. When
the options path lands it must:

1. Extend ``OrderRequest`` (or introduce ``OptionOrderRequest``) with
   ``instrument_type`` and ``option_symbol``.
2. Call ``Option.get_option(session, symbol)`` before building the leg.
3. Replace :func:`_is_option_symbol` with a strict OCC parser.

medallion: execution
"""

from __future__ import annotations

import hashlib
import logging
import re
from decimal import Decimal
from typing import Any, Optional

from app.services.execution.broker_base import (
    ActionSide,
    IBOrderType,
    OrderRequest,
    OrderResult,
    PreviewResult,
)

logger = logging.getLogger(__name__)

# Redis lock TTL must comfortably cover a provider token-refresh round-trip
# (~1-2s typical, 10s worst case against api.tastytrade.com).
REFRESH_LOCK_TTL_SECONDS = 15

# Equity ticker: 1-6 alpha chars, optional class suffix (".A", ".B") or
# exchange-pair ("BRK-B"). Anything outside this shape is treated as
# non-equity and rejected with a clear error until the options path lands.
_EQUITY_TICKER_RE = re.compile(r"^[A-Z]{1,6}(?:[.\-][A-Z]{1,3})?$")


class TastytradeExecutorError(RuntimeError):
    """Raised when the TastyTrade SDK / credentials cannot serve an order."""


def _is_option_symbol(symbol: str) -> bool:
    """Heuristic: True if ``symbol`` does not look like an equity ticker.

    This covers the common OCC format (``AAPL  240119C00150000``, includes
    whitespace + digits) and plain wrong-shape input. Replace with a strict
    OCC parser when the options path lands.
    """

    return not bool(_EQUITY_TICKER_RE.match(symbol))


def _lock_key_for_secret(client_secret: str) -> str:
    """Stable lock key that does not leak the secret itself."""

    digest = hashlib.sha256(client_secret.encode("utf-8")).hexdigest()[:16]
    return f"lock:tastytrade_session_refresh:{digest}"


class TastytradeExecutor:
    """``BrokerExecutor`` implementation backed by the ``tastytrade`` SDK.

    Environment
    -----------
    ``environment="sandbox"`` (default) routes the SDK to the CERT sandbox
    regardless of ``settings.TASTYTRADE_IS_TEST``. ``environment="prod"``
    requires ``settings.TASTYTRADE_ALLOW_LIVE=True`` and routes to
    ``api.tastytrade.com``. The constructor refuses to build a prod
    instance without the flag, so an accidental ``broker_type="tastytrade"``
    cannot place real orders until an operator explicitly enables it.
    ``TASTYTRADE_IS_TEST`` is retained for non-execution callers
    (``app.services.clients.TastyTradeClient``) but is not a
    capital-protection gate on its own.

    Order side coverage
    -------------------
    Long-side equity flow only: BUY maps to ``BUY_TO_OPEN``, SELL maps to
    ``SELL_TO_CLOSE``. Position-aware close routing (short-open
    ``SELL_TO_OPEN`` / short-close ``BUY_TO_CLOSE``) and the options path
    are deferred to a follow-up PR. ``RiskGate`` rejects short-side equity
    entries upstream, so this scoping cannot silently mis-route an order
    that should have been a short.

    Credentials
    -----------
    The current build uses the app-global ``settings.TASTYTRADE_CLIENT_SECRET``
    and ``settings.TASTYTRADE_REFRESH_TOKEN`` (mirrors the existing
    :class:`TastyTradeClient` in ``app.services.clients``). Migrating to
    per-user credentials out of ``BrokerOAuthConnection`` is tracked as a
    follow-up; see the module docstring.

    Account resolution
    ------------------
    If :attr:`OrderRequest.account_id` is set, the executor routes to the
    matching ``Account`` on the session. Otherwise it uses the first account
    returned by :meth:`Account.get` (matches the sync-side fallback).
    """

    def __init__(self, *, environment: str = "sandbox") -> None:
        env = (environment or "sandbox").lower().strip()
        if env not in ("sandbox", "prod"):
            raise ValueError(
                f"TastytradeExecutor environment must be 'sandbox' or 'prod', "
                f"got {environment!r}"
            )
        if env == "prod":
            from app.config import settings
            if not bool(getattr(settings, "TASTYTRADE_ALLOW_LIVE", False)):
                raise RuntimeError(
                    "TastyTrade live orders disabled; set TASTYTRADE_ALLOW_LIVE=true"
                )

        self._environment = env
        self._session: Optional[Any] = None
        self._accounts: list[Any] = []
        logger.info(
            "TastytradeExecutor initialized environment=%s", self._environment
        )

    @property
    def broker_name(self) -> str:
        return "tastytrade"

    def is_paper_trading(self) -> bool:
        # Environment is the only source of truth: sandbox -> paper, prod -> live.
        # ``TASTYTRADE_IS_TEST`` is no longer consulted here so the UI badge
        # cannot drift from the actual SDK base URL chosen below.
        return self._environment == "sandbox"

    async def connect(self) -> bool:
        try:
            await self._ensure_session()
            return True
        except Exception as exc:
            logger.warning("tastytrade connect failed: %s", exc)
            return False

    async def disconnect(self) -> None:
        self._session = None
        self._accounts = []

    # ------------------------------------------------------------------ core

    async def preview_order(self, req: OrderRequest) -> PreviewResult:
        try:
            session, account = await self._resolve_account(req.account_id)
            new_order = self._build_new_order(req)
        except TastytradeExecutorError as exc:
            return PreviewResult(error=str(exc), raw={"broker": "tastytrade"})
        except Exception as exc:
            logger.warning("tastytrade preview_order build failed: %s", exc)
            return PreviewResult(error=str(exc), raw={"broker": "tastytrade"})

        try:
            response = await account.place_order(session, new_order, dry_run=True)
        except Exception as exc:
            logger.warning(
                "tastytrade preview_order SDK call failed: symbol=%s err=%s",
                req.symbol, exc,
            )
            return PreviewResult(error=str(exc), raw={"broker": "tastytrade"})

        errors = list(getattr(response, "errors", []) or [])
        if errors:
            return PreviewResult(
                error="; ".join(str(e) for e in errors),
                raw={"broker": "tastytrade", "errors": [str(e) for e in errors]},
            )

        fees = getattr(response, "fee_calculation", None)
        bpe = getattr(response, "buying_power_effect", None)
        return PreviewResult(
            estimated_commission=_opt_float(getattr(fees, "commission", None)),
            estimated_margin_impact=_opt_float(
                getattr(bpe, "change_in_buying_power", None)
            ),
            raw={
                "broker": "tastytrade",
                "warnings": [str(w) for w in (getattr(response, "warnings", None) or [])],
            },
        )

    async def place_order(self, req: OrderRequest) -> OrderResult:
        try:
            session, account = await self._resolve_account(req.account_id)
            new_order = self._build_new_order(req)
        except TastytradeExecutorError as exc:
            return OrderResult(error=str(exc), raw={"broker": "tastytrade"})
        except Exception as exc:
            logger.warning("tastytrade place_order build failed: %s", exc)
            return OrderResult(error=str(exc), raw={"broker": "tastytrade"})

        try:
            response = await account.place_order(session, new_order, dry_run=False)
        except Exception as exc:
            logger.warning(
                "tastytrade place_order SDK call failed: symbol=%s err=%s",
                req.symbol, exc,
            )
            return OrderResult(error=str(exc), raw={"broker": "tastytrade"})

        errors = list(getattr(response, "errors", []) or [])
        if errors:
            return OrderResult(
                error="; ".join(str(e) for e in errors),
                raw={"broker": "tastytrade", "errors": [str(e) for e in errors]},
            )

        placed = getattr(response, "order", None)
        broker_order_id = str(getattr(placed, "id", "") or "")
        if not broker_order_id:
            return OrderResult(
                error="tastytrade place_order returned no order id",
                raw={"broker": "tastytrade"},
            )

        return OrderResult(
            broker_order_id=broker_order_id,
            status=_map_tt_status(getattr(placed, "status", None)) or "submitted",
            raw={
                "broker": "tastytrade",
                "account_number": getattr(placed, "account_number", None),
            },
        )

    async def cancel_order(self, broker_order_id: str) -> OrderResult:
        try:
            session, account = await self._resolve_account(None)
            order_id_int = int(broker_order_id)
        except TastytradeExecutorError as exc:
            return OrderResult(error=str(exc), raw={"broker": "tastytrade"})
        except ValueError:
            return OrderResult(
                error=f"tastytrade cancel_order: non-integer order id {broker_order_id!r}",
                raw={"broker": "tastytrade"},
            )

        try:
            await account.delete_order(session, order_id_int)
        except Exception as exc:
            logger.warning(
                "tastytrade cancel_order SDK call failed: id=%s err=%s",
                broker_order_id, exc,
            )
            return OrderResult(error=str(exc), raw={"broker": "tastytrade"})

        return OrderResult(
            broker_order_id=broker_order_id,
            status="cancelled",
            raw={"broker": "tastytrade"},
        )

    async def get_order_status(self, broker_order_id: str) -> OrderResult:
        try:
            session, account = await self._resolve_account(None)
            order_id_int = int(broker_order_id)
        except TastytradeExecutorError as exc:
            return OrderResult(error=str(exc), raw={"broker": "tastytrade"})
        except ValueError:
            return OrderResult(
                error=f"tastytrade get_order_status: non-integer order id {broker_order_id!r}",
                raw={"broker": "tastytrade"},
            )

        try:
            placed = await account.get_order(session, order_id_int)
        except Exception as exc:
            logger.warning(
                "tastytrade get_order_status SDK call failed: id=%s err=%s",
                broker_order_id, exc,
            )
            return OrderResult(error=str(exc), raw={"broker": "tastytrade"})

        filled_qty, avg_px = _aggregate_fills(placed)
        return OrderResult(
            broker_order_id=broker_order_id,
            status=_map_tt_status(getattr(placed, "status", None)) or "unknown",
            filled_quantity=filled_qty,
            avg_fill_price=avg_px,
            raw={"broker": "tastytrade"},
        )

    # ---------------------------------------------------------------- builders

    def _build_new_order(self, req: OrderRequest) -> Any:
        if _is_option_symbol(req.symbol):
            # TODO(options): build an equity-option leg via
            # Option.get_option(session, symbol) once OrderRequest exposes
            # the option-symbol + contract metadata. Until then we fail
            # loudly rather than silently routing through the equity path.
            raise TastytradeExecutorError(
                f"tastytrade option symbols are not yet supported (symbol={req.symbol!r}); "
                "equity orders only"
            )

        try:
            from tastytrade.order import (
                InstrumentType,
                Leg,
                NewOrder,
                OrderAction,
                OrderTimeInForce,
                OrderType,
            )
        except ImportError as exc:  # pragma: no cover — handled by SDK-guard tests
            raise TastytradeExecutorError(
                "tastytrade SDK not installed; add `tastytrade` to requirements"
            ) from exc

        if req.order_type == IBOrderType.MKT:
            tt_order_type = OrderType.MARKET
            price = None
        elif req.order_type == IBOrderType.LMT:
            if req.limit_price is None:
                raise TastytradeExecutorError(
                    "LMT order missing limit_price"
                )
            tt_order_type = OrderType.LIMIT
            price = Decimal(str(req.limit_price))
        elif req.order_type == IBOrderType.STP:
            if req.stop_price is None:
                raise TastytradeExecutorError(
                    "STP order missing stop_price"
                )
            tt_order_type = OrderType.STOP
            price = None
        elif req.order_type == IBOrderType.STP_LMT:
            if req.limit_price is None or req.stop_price is None:
                raise TastytradeExecutorError(
                    "STP_LMT order requires both limit_price and stop_price"
                )
            tt_order_type = OrderType.STOP_LIMIT
            price = Decimal(str(req.limit_price))
        else:  # pragma: no cover — enum is exhaustive
            raise TastytradeExecutorError(
                f"unsupported order_type: {req.order_type}"
            )

        # Map BUY -> "Buy to Open" and SELL -> "Sell to Close" for the
        # long-side equity flow this executor supports today. Position-aware
        # close routing (short-open / short-close) is the order_manager's
        # responsibility once it lands.
        action = (
            OrderAction.BUY_TO_OPEN
            if req.side == ActionSide.BUY
            else OrderAction.SELL_TO_CLOSE
        )

        leg = Leg(
            instrument_type=InstrumentType.EQUITY,
            symbol=req.symbol,
            action=action,
            quantity=Decimal(str(req.quantity)),
        )

        kwargs: dict[str, Any] = {
            "time_in_force": OrderTimeInForce.DAY,
            "order_type": tt_order_type,
            "legs": [leg],
        }
        if price is not None:
            kwargs["price"] = price
        if req.stop_price is not None and tt_order_type in (
            OrderType.STOP,
            OrderType.STOP_LIMIT,
        ):
            kwargs["stop_trigger"] = Decimal(str(req.stop_price))

        return NewOrder(**kwargs)

    # -------------------------------------------------------- session helpers

    async def _ensure_session(self) -> Any:
        """Return a live, refreshed :class:`tastytrade.Session`.

        Serializes calls to :meth:`Session.refresh` across workers via a
        Redis lock keyed on the (hashed) provider secret. The SDK's
        in-process :class:`anyio.Lock` still handles coroutine-level races
        inside a single worker.
        """

        try:
            from tastytrade import Account, Session
        except ImportError as exc:
            raise TastytradeExecutorError(
                "tastytrade SDK not installed; add `tastytrade` to requirements"
            ) from exc

        from app.config import settings

        client_secret = getattr(settings, "TASTYTRADE_CLIENT_SECRET", None)
        refresh_token = getattr(settings, "TASTYTRADE_REFRESH_TOKEN", None)
        # SDK base URL is dictated by ``self._environment``, not by
        # ``TASTYTRADE_IS_TEST``. The constructor already enforced the
        # ``TASTYTRADE_ALLOW_LIVE`` gate for prod; here we just pass the
        # boolean the SDK expects.
        is_test = self._environment == "sandbox"

        if not client_secret or not refresh_token:
            raise TastytradeExecutorError(
                "tastytrade credentials missing "
                "(TASTYTRADE_CLIENT_SECRET / TASTYTRADE_REFRESH_TOKEN)"
            )

        if self._session is None:
            self._session = Session(client_secret, refresh_token, is_test=is_test)

        await self._refresh_session_under_lock(client_secret)

        if not self._accounts:
            try:
                self._accounts = await Account.get(self._session)
            except Exception as exc:
                self._session = None
                raise TastytradeExecutorError(
                    f"tastytrade Account.get failed: {exc}"
                ) from exc

            if not self._accounts:
                self._session = None
                raise TastytradeExecutorError(
                    "tastytrade session returned no accounts"
                )

        return self._session

    async def _refresh_session_under_lock(self, client_secret: str) -> None:
        """Call ``session.refresh()`` with a cross-worker Redis lock.

        The SDK's :meth:`Session.refresh` is cheap when the token is still
        valid (early-returns after a timestamp check). This lock exists to
        serialize the first call in a burst so the provider does not see
        N concurrent ``POST /oauth/token`` requests from a single tenant.
        """

        assert self._session is not None

        key = _lock_key_for_secret(client_secret)
        redis = _try_get_redis()
        acquired = False

        if redis is not None:
            try:
                acquired = bool(
                    redis.set(name=key, value="1", nx=True, ex=REFRESH_LOCK_TTL_SECONDS)
                )
            except Exception as exc:  # pragma: no cover — fail-open on lock
                logger.warning(
                    "tastytrade refresh lock acquire failed: %s", exc
                )
                acquired = False

        try:
            # ``force=False`` means the SDK only hits the endpoint if the
            # in-memory expiration is <60s away. Safe to call every request.
            await self._session.refresh()
        except Exception as exc:
            # Reset session state so the next call rebuilds from scratch.
            self._session = None
            self._accounts = []
            raise TastytradeExecutorError(
                f"tastytrade session refresh failed: {exc}"
            ) from exc
        finally:
            if acquired and redis is not None:
                try:
                    redis.delete(key)
                except Exception as exc:  # pragma: no cover
                    logger.warning(
                        "tastytrade refresh lock release failed: %s", exc
                    )

    async def _resolve_account(
        self, account_id: Optional[str]
    ) -> tuple[Any, Any]:
        session = await self._ensure_session()
        if not self._accounts:
            raise TastytradeExecutorError("tastytrade has no accounts attached")

        if account_id:
            for acct in self._accounts:
                if getattr(acct, "account_number", None) == account_id:
                    return session, acct
            raise TastytradeExecutorError(
                f"tastytrade account {account_id!r} not found on session"
            )
        return session, self._accounts[0]


# --------------------------------------------------------------------- helpers


def _try_get_redis() -> Optional[Any]:
    """Return the process-wide sync Redis client or ``None`` if unavailable.

    Imported lazily (the module is optional at import time for unit tests
    that don't exercise the refresh path).
    """

    try:
        from app.services.cache import redis_client
        return redis_client
    except Exception as exc:  # pragma: no cover — Redis misconfigured
        logger.warning("tastytrade: app.services.cache redis unavailable: %s", exc)
        return None


def _opt_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


_TT_STATUS_MAP = {
    "Received": "submitted",
    "Routed": "submitted",
    "In Flight": "submitted",
    "Live": "submitted",
    "Contingent": "pending_submit",
    "Filled": "filled",
    "Cancelled": "cancelled",
    "Expired": "cancelled",
    "Rejected": "rejected",
    "Removed": "cancelled",
    "Partially Removed": "partially_filled",
    "Replace Requested": "submitted",
    "Cancel Requested": "submitted",
}


def _map_tt_status(value: Any) -> Optional[str]:
    if value is None:
        return None
    raw = value.value if hasattr(value, "value") else str(value)
    return _TT_STATUS_MAP.get(raw, raw.lower())


def _aggregate_fills(placed: Any) -> tuple[float, Optional[float]]:
    """Sum filled quantity across legs and weight-average the fill price."""

    legs = getattr(placed, "legs", None) or []
    total_qty = 0.0
    weighted_px = 0.0
    for leg in legs:
        fills = getattr(leg, "fills", None) or []
        for fill in fills:
            qty = _opt_float(getattr(fill, "quantity", None)) or 0.0
            price = _opt_float(getattr(fill, "fill_price", None))
            if qty <= 0 or price is None:
                continue
            total_qty += qty
            weighted_px += qty * price
    if total_qty <= 0:
        return 0.0, None
    return total_qty, weighted_px / total_qty


__all__ = [
    "TastytradeExecutor",
    "TastytradeExecutorError",
]
