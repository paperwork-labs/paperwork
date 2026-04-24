"""Trade approval workflow service.

medallion: execution
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Optional

from sqlalchemy.orm import Session

from datetime import datetime, timedelta, timezone

from backend.config import settings
from backend.models.order import Order, OrderStatus
from backend.models.user import User, UserRole
from backend.services.brain import brain_webhook

logger = logging.getLogger(__name__)


class ApprovalMode(str, Enum):
    ALL = "all"  # All trades require approval
    THRESHOLD = "threshold"  # Only trades at/above threshold
    ANALYST_ONLY = "analyst_only"  # Only analyst-initiated trades
    NONE = "none"  # No approval required


def _user_role_str(user: User) -> str:
    r = user.role
    if isinstance(r, UserRole):
        return r.value
    return str(r or "")


def _estimated_order_value_usd(order: Order) -> float:
    """Best-effort notional for threshold checks and webhook payloads."""
    qty = abs(float(order.quantity or 0))
    for px in (order.limit_price, order.stop_price, order.decision_price):
        if px is not None and float(px) > 0:
            return qty * float(px)
    raw: Any = order.preview_data
    if isinstance(raw, dict):
        for key in ("last", "lastPrice", "bid", "ask", "marketPrice"):
            v = raw.get(key)
            if v is not None:
                try:
                    fv = float(v)
                    if fv > 0:
                        return qty * fv
                except (TypeError, ValueError):
                    continue
    return 0.0


def _approval_mode() -> ApprovalMode:
    try:
        return ApprovalMode(settings.TRADE_APPROVAL_MODE)
    except ValueError:
        logger.warning(
            "Invalid TRADE_APPROVAL_MODE=%r, defaulting to all",
            settings.TRADE_APPROVAL_MODE,
        )
        return ApprovalMode.ALL


APPROVAL_TIMEOUT_MINUTES = 30


class ApprovalService:
    """Handles trade approval workflow for Tier 3 actions."""

    @staticmethod
    def requires_approval(order: Order, user: User) -> bool:
        """Check if order requires human approval."""
        if order.approved_by is not None:
            return False

        mode = _approval_mode()

        if mode == ApprovalMode.NONE:
            return False

        if mode == ApprovalMode.ALL:
            return True

        if mode == ApprovalMode.ANALYST_ONLY:
            return _user_role_str(user) == UserRole.ANALYST.value

        if mode == ApprovalMode.THRESHOLD:
            estimated_value = _estimated_order_value_usd(order)
            return estimated_value >= float(settings.TRADE_APPROVAL_THRESHOLD)

        return True

    @staticmethod
    async def request_approval(
        db: Session,
        order: Order,
        user: User,
    ) -> dict:
        """Request approval for an order via Brain webhook."""
        order.status = OrderStatus.PENDING_APPROVAL.value
        db.commit()
        db.refresh(order)

        est = _estimated_order_value_usd(order)
        order_data = {
            "order_id": order.id,
            "symbol": order.symbol,
            "side": order.side,
            "quantity": order.quantity,
            "order_type": order.order_type,
            "limit_price": order.limit_price,
            "estimated_value": est,
            "requested_by": user.email,
            "user_role": _user_role_str(user),
        }

        await brain_webhook.approval_required(order_data, user.id)

        logger.info(
            "Approval requested for order %s: %s %s %s",
            order.id,
            order.side,
            order.quantity,
            order.symbol,
        )

        return {
            "status": "pending_approval",
            "order_id": order.id,
            "message": "Order requires approval. Notification sent.",
        }

    @staticmethod
    async def approve(
        db: Session,
        order_id: int,
        approver: User,
    ) -> dict:
        """Approve an order (called by Brain after Slack approval)."""
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {"error": "Order not found"}

        if order.status != OrderStatus.PENDING_APPROVAL.value:
            return {"error": f"Order is {order.status}, not pending approval"}

        if _user_role_str(approver) != UserRole.OWNER.value:
            return {"error": "Only owner can approve trades"}

        order.status = OrderStatus.PREVIEW.value
        order.approved_by = approver.id
        db.commit()
        db.refresh(order)

        logger.info("Order %s approved by %s", order_id, approver.email)

        return {
            "status": "approved",
            "order_id": order_id,
            "message": "Order approved, ready for execution",
        }

    @staticmethod
    async def reject(
        db: Session,
        order_id: int,
        rejector: User,
        reason: Optional[str] = None,
    ) -> dict:
        """Reject an order."""
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {"error": "Order not found"}

        allowed_statuses = {
            OrderStatus.PREVIEW.value,
            OrderStatus.PENDING_APPROVAL.value,
        }
        if order.status not in allowed_statuses:
            return {
                "error": f"Cannot reject order in status '{order.status}'. "
                f"Only PREVIEW or PENDING_APPROVAL orders can be rejected."
            }

        order.status = OrderStatus.REJECTED.value
        order.error_message = (
            f"Rejected by {rejector.email}: {reason or 'No reason given'}"
        )
        db.commit()
        db.refresh(order)

        logger.info(
            "Order %s rejected by %s: %s",
            order_id,
            rejector.email,
            reason,
        )

        return {
            "status": "rejected",
            "order_id": order_id,
            "reason": reason,
        }

    @staticmethod
    def expire_stale_approvals(db: Session) -> list[dict]:
        """Auto-reject orders stuck in PENDING_APPROVAL beyond timeout."""
        from sqlalchemy import update

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=APPROVAL_TIMEOUT_MINUTES)

        # Atomic conditional update - only affects rows still in PENDING_APPROVAL
        stmt = (
            update(Order)
            .where(
                Order.status == OrderStatus.PENDING_APPROVAL.value,
                Order.updated_at < cutoff,
            )
            .values(
                status=OrderStatus.REJECTED.value,
                error_message=f"Auto-rejected: approval timeout ({APPROVAL_TIMEOUT_MINUTES}m)",
            )
            .returning(Order.id, Order.symbol, Order.side, Order.quantity)
        )
        result = db.execute(stmt)
        expired = [
            {
                "order_id": row.id,
                "symbol": row.symbol,
                "side": row.side,
                "quantity": float(row.quantity or 0),
                "waited_minutes": APPROVAL_TIMEOUT_MINUTES,
            }
            for row in result
        ]

        if expired:
            db.commit()
            brain_webhook.notify_sync(
                "approval_expired",
                {"count": len(expired), "orders": expired},
            )
            logger.info("Expired %d stale approval(s)", len(expired))

        return expired

    @staticmethod
    def list_pending(db: Session, user_id: int) -> list[dict]:
        """List orders currently pending approval."""
        orders = (
            db.query(Order)
            .filter(
                Order.user_id == user_id,
                Order.status == OrderStatus.PENDING_APPROVAL.value,
            )
            .order_by(Order.created_at.desc())
            .all()
        )
        return [
            {
                "order_id": o.id,
                "symbol": o.symbol,
                "side": o.side,
                "quantity": float(o.quantity or 0),
                "order_type": o.order_type,
                "estimated_value": _estimated_order_value_usd(o),
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "minutes_pending": (
                    (
                        datetime.now(timezone.utc)
                        - (
                            o.updated_at.replace(tzinfo=timezone.utc)
                            if o.updated_at.tzinfo is None
                            else o.updated_at.astimezone(timezone.utc)
                        )
                    ).total_seconds()
                    / 60
                    if o.updated_at
                    else None
                ),
                "timeout_minutes": APPROVAL_TIMEOUT_MINUTES,
            }
            for o in orders
        ]


approval_service = ApprovalService()
