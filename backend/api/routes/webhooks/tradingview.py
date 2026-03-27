"""
TradingView webhook endpoint for alert-triggered order execution.

Receives alerts from TradingView and routes through RiskGate to execution.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user
from backend.database import get_db
from backend.models.user import User
from backend.models.order import Order, OrderStatus
from backend.services.execution.broker_base import OrderRequest
from backend.services.execution.risk_gate import RiskGate, RiskViolation
from backend.services.risk.circuit_breaker import circuit_breaker

logger = logging.getLogger(__name__)
router = APIRouter()


def hash_secret(secret: str) -> str:
    """Return SHA-256 hex digest for storage (never store plaintext webhook secrets)."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def verify_secret(provided: str, stored_hash: str) -> bool:
    """Constant-time compare of digest(provided) to stored hash."""
    return secrets.compare_digest(hash_secret(provided), stored_hash)


def _stored_value_is_sha256_hex(value: str) -> bool:
    """True if DB value looks like our stored webhook secret hash (not legacy plaintext)."""
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


class TradingViewAlert(BaseModel):
    """TradingView webhook payload."""

    secret: str = Field(..., description="User's TV webhook secret")
    symbol: str = Field(..., description="Ticker symbol (e.g., AAPL)")
    action: str = Field(..., description="buy, sell, or close")
    quantity: Optional[int] = Field(None, description="Share quantity")
    price: Optional[float] = Field(None, description="Current price")
    order_type: str = Field("market", description="market or limit")
    limit_price: Optional[float] = Field(None, description="Limit price if order_type=limit")
    strategy_name: Optional[str] = Field(None, description="Strategy that triggered alert")
    message: Optional[str] = Field(None, description="Alert message")


class WebhookResponse(BaseModel):
    """Response from webhook processing."""

    success: bool
    order_id: Optional[int] = None
    status: Optional[str] = None
    message: Optional[str] = None
    rejection_reason: Optional[str] = None


@router.post("", response_model=WebhookResponse)
async def receive_tradingview_alert(
    alert: TradingViewAlert,
    request: Request,
    db: Session = Depends(get_db),
) -> WebhookResponse:
    """
    Receive and process TradingView webhook alert.

    Flow:
    1. Validate secret against user's stored tv_webhook_secret (SHA-256 hash)
    2. Check circuit breaker
    3. Run through RiskGate
    4. Create and execute order

    Expected TradingView alert message format (JSON):
    {
        "secret": "your_webhook_secret",
        "symbol": "{{ticker}}",
        "action": "buy",
        "quantity": 100,
        "price": {{close}},
        "strategy_name": "Stage 2 Entry"
    }
    """
    # Log incoming request (without secret)
    logger.info(
        "TradingView alert received: %s %s from %s",
        alert.action,
        alert.symbol,
        request.client.host if request.client else "unknown",
    )

    # Validate secret and get user
    user = _validate_secret(db, alert.secret)
    if not user:
        logger.warning(
            "Invalid webhook secret from %s",
            request.client.host if request.client else "unknown",
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook secret",
        )

    # Check circuit breaker
    is_exit = alert.action.lower() in ("sell", "close")
    allowed, reason, tier = circuit_breaker.can_trade(is_exit=is_exit)

    if not allowed:
        logger.warning(
            "Circuit breaker blocked TV alert for %s: %s",
            user.email,
            reason,
        )
        return WebhookResponse(
            success=False,
            message="Circuit breaker active",
            rejection_reason=reason,
        )

    # Normalize action to side
    action = alert.action.lower()
    if action in ("buy", "long"):
        side = "BUY"
    elif action in ("sell", "short", "close"):
        side = "SELL"
    else:
        return WebhookResponse(
            success=False,
            message=f"Invalid action: {alert.action}",
        )

    # Determine quantity
    quantity = alert.quantity
    if not quantity or quantity <= 0:
        # Auto-size based on risk budget (simplified)
        quantity = _calculate_position_size(
            db, user.id, alert.symbol, alert.price or 0
        )

    if quantity <= 0:
        return WebhookResponse(
            success=False,
            message="Could not determine position size",
        )

    # Create order request using from_user_input for proper enum conversion
    req = OrderRequest.from_user_input(
        symbol=alert.symbol,
        side=side,
        order_type=alert.order_type,
        quantity=quantity,
        limit_price=alert.limit_price,
    )

    # Run through RiskGate
    risk_gate = RiskGate()
    price_estimate = alert.price or risk_gate.estimate_price(db, alert.symbol)
    portfolio_equity = _get_portfolio_equity(db, user.id)

    try:
        warnings = risk_gate.check(
            req=req,
            price_estimate=price_estimate,
            db=db,
            portfolio_equity=portfolio_equity,
            risk_budget=portfolio_equity * 0.02 if portfolio_equity else 2000,
        )
        if warnings:
            logger.info("RiskGate warnings for TV alert: %s", warnings)
    except RiskViolation as e:
        logger.warning(
            "RiskGate rejected TV alert for %s: %s",
            user.email,
            str(e),
        )
        return WebhookResponse(
            success=False,
            message="Order rejected by risk check",
            rejection_reason=str(e),
        )

    # Apply circuit breaker size multiplier
    size_mult = circuit_breaker.get_size_multiplier()
    adjusted_quantity = int(quantity * size_mult)

    if adjusted_quantity <= 0:
        return WebhookResponse(
            success=False,
            message="Position size reduced to zero by circuit breaker",
        )

    # Create order (PREVIEW required — OrderManager.submit / execute_order_task only accept PREVIEW)
    order = Order(
        symbol=alert.symbol.upper(),
        side=side.lower(),
        order_type=alert.order_type.lower(),
        status=OrderStatus.PREVIEW.value,
        quantity=adjusted_quantity,
        limit_price=alert.limit_price,
        source="tradingview",
        broker_type="alpaca",  # Default to Alpaca for TV alerts
        user_id=user.id,
        created_by=f"tradingview:{alert.strategy_name or 'alert'}",
        decision_price=alert.price,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    logger.info(
        "Created order %s from TradingView alert: %s %s %d shares",
        order.id,
        side,
        alert.symbol,
        adjusted_quantity,
    )

    # Queue for async execution; SUBMITTED is set by OrderManager after broker accepts
    try:
        from backend.tasks.portfolio.orders import execute_order_task

        execute_order_task.delay(order.id)
    except Exception as e:
        logger.error("Failed to queue order execution: %s", e)
        order.status = OrderStatus.ERROR.value
        order.error_message = f"Failed to queue: {str(e)}"
        db.commit()

    return WebhookResponse(
        success=True,
        order_id=order.id,
        status=order.status,
        message=f"Order created: {side} {adjusted_quantity} {alert.symbol}",
    )


@router.post("/generate-secret")
async def generate_webhook_secret(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Generate a new webhook secret for the current user."""
    new_secret = secrets.token_urlsafe(32)

    current_user.tv_webhook_secret = hash_secret(new_secret)
    db.commit()

    return {
        "secret": new_secret,
        "message": "Save this secret - it won't be shown again",
    }


def _validate_secret(db: Session, secret: str) -> Optional[User]:
    """Validate webhook secret and return associated user (hash or legacy plaintext row)."""
    if not secret:
        return None

    digest = hash_secret(secret)
    user = (
        db.query(User)
        .filter(User.tv_webhook_secret == digest)
        .first()
    )
    if user is not None and verify_secret(secret, user.tv_webhook_secret):
        return user

    # Legacy: plaintext stored before hashing migration; constant-time per candidate.
    for candidate in db.query(User).filter(User.tv_webhook_secret.isnot(None)):
        stored = candidate.tv_webhook_secret
        if not stored or _stored_value_is_sha256_hex(stored):
            continue
        if secrets.compare_digest(secret, stored):
            return candidate

    return None


def _calculate_position_size(
    db: Session,
    user_id: int,
    symbol: str,
    price: float,
) -> int:
    """Calculate position size based on risk parameters."""
    if price <= 0:
        return 0

    portfolio_equity = _get_portfolio_equity(db, user_id)
    if not portfolio_equity or portfolio_equity <= 0:
        return 0

    # 2% risk per position
    risk_amount = portfolio_equity * 0.02
    quantity = int(risk_amount / price)

    return max(1, quantity)


def _get_portfolio_equity(db: Session, user_id: int) -> Optional[float]:
    """Get portfolio equity for a user."""
    try:
        from backend.models.account_balance import AccountBalance

        balance = (
            db.query(AccountBalance)
            .filter(AccountBalance.user_id == user_id)
            .order_by(AccountBalance.as_of_date.desc())
            .first()
        )
        if balance and balance.total_value:
            return float(balance.total_value)
    except Exception as e:
        logger.warning("Failed to get portfolio equity: %s", e)
    return None
