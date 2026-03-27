"""Alpaca broker adapter.

Implements :class:`~backend.services.execution.broker_adapter.BrokerAdapter`
for Alpaca trading via the ``alpaca-py`` SDK (sync client wrapped with
``asyncio.to_thread``).
"""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from backend.config import settings
from backend.services.execution.broker_adapter import (
    BrokerAdapter,
    BrokerBalance,
    BrokerOrder,
    BrokerPosition,
    OrderRequest,
    OrderResult,
)

logger = logging.getLogger(__name__)

# Alpaca returns fractional P/L percent as a decimal (e.g. 0.012 = 1.2%).
_PLPC_RATIO_MAX_ABS = 1.0001


def _pydantic_dump(obj: Any) -> Dict[str, Any]:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return {}


def _dec(raw: Optional[str]) -> Decimal:
    if raw is None or raw == "":
        return Decimal("0")
    return Decimal(str(raw))


def _dec_opt(raw: Optional[str]) -> Optional[Decimal]:
    if raw is None or raw == "":
        return None
    return Decimal(str(raw))


def _plpc_to_pct(raw: Optional[str]) -> Optional[float]:
    if raw is None or raw == "":
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if abs(v) <= _PLPC_RATIO_MAX_ABS:
        return v * 100.0
    return v


def _normalize_order_type(order_type: str) -> str:
    ot = order_type.strip().lower()
    if ot in ("mkt", "market"):
        return "market"
    if ot in ("lmt", "limit"):
        return "limit"
    if ot in ("stp", "stop"):
        return "stop"
    if ot in ("stp_lmt", "stop_limit", "stop-limit"):
        return "stop_limit"
    return ot


class AlpacaAdapter(BrokerAdapter):
    """Alpaca trading adapter using alpaca-py ``TradingClient``."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        paper: Optional[bool] = None,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.api_secret = (api_secret or "").strip()
        if paper is not None:
            self.paper = paper
        else:
            self.paper = (
                getattr(settings, "ALPACA_TRADING_MODE", "paper").lower() != "live"
            )
        self._client: Any = None

    def _merge_credentials(self, **kwargs: Any) -> None:
        key = kwargs.get("api_key")
        secret = kwargs.get("api_secret") or kwargs.get("secret_key")
        if key is not None:
            self.api_key = str(key).strip()
        if secret is not None:
            self.api_secret = str(secret).strip()
        if not self.api_key:
            self.api_key = (getattr(settings, "ALPACA_API_KEY", "") or "").strip()
        if not self.api_secret:
            self.api_secret = (getattr(settings, "ALPACA_API_SECRET", "") or "").strip()
        if "paper" in kwargs and kwargs["paper"] is not None:
            self.paper = bool(kwargs["paper"])
        elif hasattr(settings, "ALPACA_TRADING_MODE"):
            self.paper = (
                getattr(settings, "ALPACA_TRADING_MODE", "paper").lower() != "live"
            )

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from alpaca.trading.client import TradingClient
            except ImportError:
                logger.error(
                    "alpaca-py is not installed. Add alpaca-py to requirements and install."
                )
                raise
            if not self.api_key or not self.api_secret:
                raise ValueError("Alpaca API key and secret are required")
            self._client = TradingClient(
                api_key=self.api_key,
                secret_key=self.api_secret,
                paper=self.paper,
            )
        return self._client

    async def connect(self, **kwargs: Any) -> bool:
        self._merge_credentials(**kwargs)
        self._client = None

        def _ping() -> None:
            self._get_client().get_account()

        try:
            await asyncio.to_thread(_ping)
            return True
        except Exception as e:
            logger.error("Alpaca connect failed: %s", e)
            self._client = None
            return False

    async def disconnect(self) -> None:
        self._client = None

    def _signed_qty(self, p: Any) -> Decimal:
        qty = _dec(getattr(p, "qty", None))
        side = getattr(p, "side", None)
        side_val = getattr(side, "value", side)
        if isinstance(side_val, str) and side_val.lower() == "short":
            return -qty
        return qty

    async def get_positions(self, account_id: str) -> List[Dict]:
        def _load() -> List[BrokerPosition]:
            client = self._get_client()
            raw_positions = client.get_all_positions()
            out: List[BrokerPosition] = []
            for p in raw_positions:
                sym = getattr(p, "symbol", None) or ""
                qty = self._signed_qty(p)
                out.append(
                    BrokerPosition(
                        symbol=sym,
                        quantity=qty,
                        average_cost=_dec(getattr(p, "avg_entry_price", None)),
                        current_price=_dec_opt(getattr(p, "current_price", None)),
                        market_value=_dec_opt(getattr(p, "market_value", None)),
                        unrealized_pnl=_dec_opt(getattr(p, "unrealized_pl", None)),
                        unrealized_pnl_pct=_plpc_to_pct(getattr(p, "unrealized_plpc", None)),
                    )
                )
            return out

        try:
            positions = await asyncio.to_thread(_load)
            return [bp.to_dict(account_id) for bp in positions]
        except Exception as e:
            logger.error("Alpaca get_positions failed: %s", e)
            return []

    async def get_balances(self, account_id: str) -> Dict:
        del account_id  # Single account per API key

        def _load() -> BrokerBalance:
            account = self._get_client().get_account()
            equity = _dec(getattr(account, "equity", None))
            cash = _dec(getattr(account, "cash", None))
            bp = _dec(getattr(account, "buying_power", None))
            margin = _dec_opt(getattr(account, "initial_margin", None))
            return BrokerBalance(
                total_value=equity,
                cash=cash,
                buying_power=bp,
                margin_used=margin if margin is not None else Decimal("0"),
            )

        try:
            bal = await asyncio.to_thread(_load)
            d = bal.to_dict()
            return d
        except Exception as e:
            logger.error("Alpaca get_balances failed: %s", e)
            return {}

    def _build_submit_request(
        self,
        symbol: str,
        action: str,
        quantity: float,
        order_type: str,
        limit_price: Optional[float],
        stop_price: Optional[float],
    ) -> Any:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import (
            LimitOrderRequest,
            MarketOrderRequest,
            StopLimitOrderRequest,
            StopOrderRequest,
        )

        side = (
            OrderSide.BUY if str(action).lower() in ("buy", "b") else OrderSide.SELL
        )
        ot = _normalize_order_type(order_type)
        qty = float(quantity)
        tif = TimeInForce.DAY
        sym = symbol.upper()

        if ot == "market":
            return MarketOrderRequest(
                symbol=sym, qty=qty, side=side, time_in_force=tif
            )
        if ot == "limit":
            if limit_price is None:
                raise ValueError("limit_price is required for limit orders")
            return LimitOrderRequest(
                symbol=sym,
                qty=qty,
                side=side,
                time_in_force=tif,
                limit_price=float(limit_price),
            )
        if ot == "stop":
            if stop_price is None:
                raise ValueError("stop_price is required for stop orders")
            return StopOrderRequest(
                symbol=sym,
                qty=qty,
                side=side,
                time_in_force=tif,
                stop_price=float(stop_price),
            )
        if ot == "stop_limit":
            if limit_price is None or stop_price is None:
                raise ValueError(
                    "limit_price and stop_price are required for stop_limit orders"
                )
            return StopLimitOrderRequest(
                symbol=sym,
                qty=qty,
                side=side,
                time_in_force=tif,
                stop_price=float(stop_price),
                limit_price=float(limit_price),
            )
        raise ValueError(f"Unsupported order_type for Alpaca: {order_type!r}")

    def _order_status_value(self, o: Any) -> str:
        st = getattr(o, "status", None)
        return st.value if st is not None and hasattr(st, "value") else str(st or "")

    def _order_type_value(self, o: Any) -> str:
        t = getattr(o, "type", None) or getattr(o, "order_type", None)
        return t.value if t is not None and hasattr(t, "value") else str(t or "")

    def _order_side_value(self, o: Any) -> str:
        s = getattr(o, "side", None)
        return s.value if s is not None and hasattr(s, "value") else str(s or "")

    async def submit_order(
        self,
        symbol: str,
        action: str,
        quantity: float,
        order_type: str,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict:
        del kwargs

        def _submit() -> Dict[str, Any]:
            client = self._get_client()
            req = self._build_submit_request(
                symbol, action, quantity, order_type, limit_price, stop_price
            )
            order = client.submit_order(req)
            return {
                "broker_order_id": str(order.id),
                "status": self._order_status_value(order),
                "raw": _pydantic_dump(order),
            }

        try:
            return await asyncio.to_thread(_submit)
        except Exception as e:
            logger.error("Alpaca submit_order failed: %s", e)
            return {"error": str(e)}

    async def cancel_order(self, broker_order_id: str) -> Dict:

        def _cancel() -> None:
            self._get_client().cancel_order_by_id(broker_order_id)

        try:
            await asyncio.to_thread(_cancel)
            return {"broker_order_id": broker_order_id, "status": "cancelled"}
        except Exception as e:
            logger.error("Alpaca cancel_order failed for %s: %s", broker_order_id, e)
            return {"broker_order_id": broker_order_id, "error": str(e)}

    async def get_order_status(self, broker_order_id: str) -> Dict:

        def _status() -> Dict[str, Any]:
            o = self._get_client().get_order_by_id(broker_order_id)
            filled_qty = _dec(getattr(o, "filled_qty", None) or "0")
            fap = _dec_opt(getattr(o, "filled_avg_price", None))
            return {
                "broker_order_id": broker_order_id,
                "status": self._order_status_value(o),
                "filled_quantity": float(filled_qty),
                "avg_fill_price": float(fap) if fap is not None else None,
                "raw": _pydantic_dump(o),
            }

        try:
            return await asyncio.to_thread(_status)
        except Exception as e:
            logger.error(
                "Alpaca get_order_status failed for %s: %s", broker_order_id, e
            )
            return {"broker_order_id": broker_order_id, "error": str(e)}

    async def get_orders(self, status: Optional[str] = None) -> List[BrokerOrder]:
        """List orders (open / closed / all). Not part of the BrokerAdapter ABC."""

        def _list() -> List[BrokerOrder]:
            from alpaca.trading.enums import QueryOrderStatus
            from alpaca.trading.requests import GetOrdersRequest

            client = self._get_client()
            request = GetOrdersRequest()
            if status:
                status_map = {
                    "open": QueryOrderStatus.OPEN,
                    "closed": QueryOrderStatus.CLOSED,
                    "all": QueryOrderStatus.ALL,
                }
                request.status = status_map.get(
                    status.lower(), QueryOrderStatus.ALL
                )
            else:
                request.status = QueryOrderStatus.ALL
            orders = client.get_orders(filter=request)
            out: List[BrokerOrder] = []
            for o in orders:
                oid = str(o.id)
                sym = getattr(o, "symbol", None)
                qty_raw = getattr(o, "qty", None) or "0"
                fq_raw = getattr(o, "filled_qty", None) or "0"
                fap = _dec_opt(getattr(o, "filled_avg_price", None))
                out.append(
                    BrokerOrder(
                        order_id=oid,
                        symbol=sym,
                        side=self._order_side_value(o),
                        quantity=_dec(qty_raw),
                        order_type=self._order_type_value(o),
                        status=self._order_status_value(o),
                        filled_quantity=_dec(fq_raw),
                        filled_price=fap,
                        submitted_at=getattr(o, "submitted_at", None),
                        filled_at=getattr(o, "filled_at", None),
                    )
                )
            return out

        try:
            return await asyncio.to_thread(_list)
        except Exception as e:
            logger.error("Alpaca get_orders failed: %s", e)
            return []

    async def place_order(self, request: OrderRequest) -> OrderResult:
        """Submit using adapter-layer :class:`OrderRequest` (decimal/string fields)."""

        lp = float(request.limit_price) if request.limit_price is not None else None
        sp = float(request.stop_price) if request.stop_price is not None else None
        payload = await self.submit_order(
            symbol=request.symbol,
            action=request.side,
            quantity=float(request.quantity),
            order_type=request.order_type,
            limit_price=lp,
            stop_price=sp,
        )
        if payload.get("error"):
            return OrderResult(success=False, message=str(payload["error"]))
        return OrderResult(
            success=True,
            order_id=payload.get("broker_order_id"),
            message=str(payload.get("status", "submitted")),
        )

    async def cancel_order_by_id(self, order_id: str) -> bool:
        """Return True if Alpaca accepted the cancel request."""
        result = await self.cancel_order(order_id)
        return "error" not in result

    async def get_account_info(self) -> Dict[str, Any]:
        """Trading account flags and metadata."""

        def _info() -> Dict[str, Any]:
            account = self._get_client().get_account()
            st = getattr(account, "status", None)
            status_val = st.value if st is not None and hasattr(st, "value") else None
            return {
                "account_number": getattr(account, "account_number", None),
                "status": status_val or "unknown",
                "currency": getattr(account, "currency", None),
                "pattern_day_trader": getattr(account, "pattern_day_trader", None),
                "trading_blocked": getattr(account, "trading_blocked", None),
                "transfers_blocked": getattr(account, "transfers_blocked", None),
                "account_blocked": getattr(account, "account_blocked", None),
                "created_at": str(getattr(account, "created_at", None))
                if getattr(account, "created_at", None)
                else None,
            }

        try:
            return await asyncio.to_thread(_info)
        except Exception as e:
            logger.error("Alpaca get_account_info failed: %s", e)
            return {"error": str(e)}
