"""Shadow (paper) order recorder.

When ``settings.SHADOW_TRADING_MODE`` is True (default-on safety; see D137),
``OrderManager.submit`` diverts into :meth:`ShadowOrderRecorder.record` instead
of calling any broker executor. This recorder persists the intended order to
the ``shadow_orders`` table with the current risk-gate verdict and the
estimated fill price, so we can later compute simulated P&L without ever
risking real capital.

The recorder is deliberately conservative:
  * It never mutates the existing :class:`backend.models.order.Order` row —
    the intent captured at preview time is preserved verbatim.
  * It runs the exact same :class:`RiskGate` the live path would have used.
    If the gate raises, the shadow order is still persisted (status =
    ``would_deny_by_risk_gate``) so we keep a ledger of rejected intents.
  * It never swallows unexpected exceptions (see no-silent-fallback rule).

A separate :func:`POST /api/v1/shadow-trades/submit` route exists for direct
entry (bypassing ``OrderManager``) so clients can exercise this recorder
without going through the preview step.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from backend.models.order import Order
from backend.models.shadow_order import ShadowOrder, ShadowOrderStatus
from backend.services.execution.broker_base import OrderRequest
from backend.services.execution.risk_gate import RiskGate, RiskViolation

logger = logging.getLogger(__name__)


def _to_decimal(value: Any) -> Optional[Decimal]:
    """Best-effort conversion to Decimal.

    Returns ``None`` when the value cannot be represented cleanly, so callers
    can persist ``NULL`` rather than a lossy float. Never silently replaces a
    bad input with 0 (see .cursor/rules/no-silent-fallback.mdc).
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        logger.warning(
            "shadow_order_recorder: cannot convert %r to Decimal; storing NULL",
            value,
        )
        return None


class ShadowOrderRecorder:
    """Persists intended orders to the ``shadow_orders`` table.

    Shape matches the real :class:`OrderManager` entry point so the
    flag-gated branch in ``order_manager.py`` can divert with no signature
    change.
    """

    def __init__(
        self,
        session: Session,
        risk_gate: Optional[RiskGate] = None,
    ) -> None:
        self.session = session
        self.risk_gate = risk_gate or RiskGate()

    # ------------------------------------------------------------------
    # Primary entry point: matches ``OrderManager.submit`` signature.
    # ------------------------------------------------------------------
    def record(
        self,
        *,
        order_id: int,
        user_id: int,
    ) -> Dict[str, Any]:
        """Persist a ``ShadowOrder`` for the given previewed order row.

        The caller (``OrderManager.submit``) has already loaded the
        ``Order`` into its scoped session. We look it up again (scoped to
        ``user_id``) so cross-tenant access is structurally impossible.
        """
        order = (
            self.session.query(Order)
            .filter(Order.id == order_id, Order.user_id == user_id)
            .first()
        )
        if order is None:
            logger.warning(
                "shadow_order_recorder: order_id=%s user_id=%s not found",
                order_id,
                user_id,
            )
            return {"error": "Order not found"}

        return self._record_for_order(order=order, user_id=user_id)

    # ------------------------------------------------------------------
    # Direct entry point for the ``POST /shadow-trades/submit`` route —
    # bypasses OrderManager entirely so clients can exercise the recorder
    # without persisting a full ``Order`` row first.
    # ------------------------------------------------------------------
    def record_direct(
        self,
        *,
        user_id: int,
        symbol: str,
        side: str,
        quantity: Decimal,
        order_type: str = "market",
        limit_price: Optional[Decimal] = None,
        tif: Optional[str] = None,
        account_id: Optional[str] = None,
    ) -> ShadowOrder:
        """Persist a ``ShadowOrder`` from raw inputs (no existing ``Order``)."""
        symbol_upper = (symbol or "").upper().strip()
        side_lower = (side or "").lower().strip()
        if symbol_upper == "" or side_lower not in {"buy", "sell"}:
            raise ValueError(
                f"invalid shadow order request: symbol={symbol!r} side={side!r}"
            )
        if quantity is None or quantity <= 0:
            raise ValueError(f"invalid shadow order quantity: {quantity!r}")

        req = OrderRequest.from_user_input(
            symbol=symbol_upper,
            side=side_lower,
            order_type=order_type,
            quantity=float(quantity),
            limit_price=float(limit_price) if limit_price is not None else None,
            account_id=account_id,
        )

        verdict, estimated_price = self._run_risk_gate(
            req=req, user_id=user_id
        )

        status = (
            ShadowOrderStatus.WOULD_DENY_BY_RISK_GATE
            if verdict.get("allowed") is False
            else ShadowOrderStatus.EXECUTED_AT_SIMULATION_TIME
        )

        row = ShadowOrder(
            user_id=user_id,
            account_id=account_id,
            symbol=symbol_upper,
            side=side_lower,
            order_type=order_type.lower(),
            qty=quantity,
            limit_price=limit_price,
            tif=tif,
            status=status.value,
            risk_gate_verdict=verdict,
            intended_fill_price=_to_decimal(estimated_price)
            if status == ShadowOrderStatus.EXECUTED_AT_SIMULATION_TIME
            else None,
            intended_fill_at=datetime.now(timezone.utc)
            if status == ShadowOrderStatus.EXECUTED_AT_SIMULATION_TIME
            else None,
            source_order_id=None,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        logger.info(
            "shadow_order_recorder: recorded direct %s %s %s qty=%s status=%s id=%s",
            side_lower,
            quantity,
            symbol_upper,
            "limit" if limit_price is not None else "market",
            status.value,
            row.id,
        )
        return row

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _record_for_order(
        self, *, order: Order, user_id: int
    ) -> Dict[str, Any]:
        qty = _to_decimal(order.quantity)
        if qty is None or qty <= 0:
            logger.warning(
                "shadow_order_recorder: order_id=%s has invalid qty=%r",
                order.id,
                order.quantity,
            )
            return {"error": "invalid order quantity for shadow recorder"}

        req = OrderRequest.from_user_input(
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=float(qty),
            limit_price=order.limit_price,
            stop_price=order.stop_price,
            account_id=order.account_id,
        )

        verdict, estimated_price = self._run_risk_gate(
            req=req, user_id=user_id
        )

        status = (
            ShadowOrderStatus.WOULD_DENY_BY_RISK_GATE
            if verdict.get("allowed") is False
            else ShadowOrderStatus.EXECUTED_AT_SIMULATION_TIME
        )

        row = ShadowOrder(
            user_id=user_id,
            account_id=order.account_id,
            symbol=(order.symbol or "").upper(),
            side=(order.side or "").lower(),
            order_type=(order.order_type or "market").lower(),
            qty=qty,
            limit_price=_to_decimal(order.limit_price),
            tif=None,
            status=status.value,
            risk_gate_verdict=verdict,
            intended_fill_price=_to_decimal(estimated_price)
            if status == ShadowOrderStatus.EXECUTED_AT_SIMULATION_TIME
            else None,
            intended_fill_at=datetime.now(timezone.utc)
            if status == ShadowOrderStatus.EXECUTED_AT_SIMULATION_TIME
            else None,
            source_order_id=order.id,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)

        logger.info(
            "shadow_order_recorder: diverted order_id=%s user_id=%s shadow_id=%s status=%s",
            order.id,
            user_id,
            row.id,
            status.value,
        )

        return {
            "shadow": True,
            "shadow_order_id": row.id,
            "source_order_id": order.id,
            "status": row.status,
            "risk_gate": verdict,
            "intended_fill_price": (
                str(row.intended_fill_price)
                if row.intended_fill_price is not None
                else None
            ),
            "intended_fill_at": (
                row.intended_fill_at.isoformat()
                if row.intended_fill_at is not None
                else None
            ),
        }

    def _run_risk_gate(
        self, *, req: OrderRequest, user_id: int
    ) -> tuple[Dict[str, Any], Optional[float]]:
        """Run the real RiskGate and return a JSON-safe verdict + est. price.

        The verdict is stored verbatim on the shadow row so downstream
        observers can tell why a paper order would (not) have been allowed.
        """
        estimated_price: Optional[float]
        try:
            _stop = getattr(req, "stop_price", None)
            estimated_price = self.risk_gate.estimate_price(
                self.session, req.symbol, req.limit_price, _stop
            )
        except RiskViolation as e:
            logger.info(
                "shadow_order_recorder: risk_gate.estimate_price blocked %s: %s",
                req.symbol,
                e,
            )
            return (
                {
                    "allowed": False,
                    "stage": "estimate_price",
                    "reason": str(e),
                    "user_id": user_id,
                },
                None,
            )

        try:
            warnings = self.risk_gate.check(req, estimated_price, self.session)
        except RiskViolation as e:
            return (
                {
                    "allowed": False,
                    "stage": "check",
                    "reason": str(e),
                    "estimated_price": estimated_price,
                    "user_id": user_id,
                },
                estimated_price,
            )

        return (
            {
                "allowed": True,
                "stage": "check",
                "warnings": list(warnings or []),
                "estimated_price": estimated_price,
                "user_id": user_id,
            },
            estimated_price,
        )
