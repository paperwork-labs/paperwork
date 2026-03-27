"""
Tax Loss Harvester Service.

Identifies tax loss harvesting opportunities while enforcing
wash sale compliance (61-day window: 30 days before + 30 days after sale).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Set

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from backend.models.position import Position
from backend.models.tax_lot import TaxLot
from backend.models.order import Order, OrderStatus
from backend.models.market_data import MarketSnapshot

logger = logging.getLogger(__name__)


@dataclass
class HarvestOpportunity:
    """A potential tax loss harvesting opportunity."""

    symbol: str
    position_id: int
    current_price: float
    cost_basis: float
    unrealized_loss: float
    loss_pct: float
    quantity: float
    tax_lots_count: int
    oldest_lot_date: datetime
    is_long_term: bool  # Held > 1 year
    wash_sale_blocked: bool
    wash_sale_reason: Optional[str]
    suggested_action: str  # "harvest", "wait", "blocked"
    estimated_tax_savings: float  # At estimated tax rate

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "position_id": self.position_id,
            "current_price": self.current_price,
            "cost_basis": self.cost_basis,
            "unrealized_loss": self.unrealized_loss,
            "loss_pct": round(self.loss_pct, 2),
            "quantity": self.quantity,
            "tax_lots_count": self.tax_lots_count,
            "oldest_lot_date": self.oldest_lot_date.isoformat() if self.oldest_lot_date else None,
            "is_long_term": self.is_long_term,
            "wash_sale_blocked": self.wash_sale_blocked,
            "wash_sale_reason": self.wash_sale_reason,
            "suggested_action": self.suggested_action,
            "estimated_tax_savings": round(self.estimated_tax_savings, 2),
        }


@dataclass
class WashSaleWindow:
    """Tracks a wash sale exclusion window."""

    symbol: str
    sale_date: datetime
    window_start: datetime  # sale_date - 30 days
    window_end: datetime  # sale_date + 30 days
    shares_sold: float
    triggered_by_order_id: Optional[int]

    def is_active(self, check_date: Optional[datetime] = None) -> bool:
        check = check_date or datetime.now(timezone.utc)
        return self.window_start <= check <= self.window_end


class TaxLossHarvester:
    """
    Identifies tax loss harvesting opportunities.

    Key features:
    - Scans positions for unrealized losses
    - Enforces 61-day wash sale window
    - Tracks substantially identical securities
    - Suggests optimal harvest timing
    """

    WASH_SALE_DAYS_BEFORE = 30
    WASH_SALE_DAYS_AFTER = 30
    MIN_LOSS_THRESHOLD = 100.0  # Minimum $ loss to consider
    MIN_LOSS_PCT = 5.0  # Minimum % loss to consider
    SHORT_TERM_TAX_RATE = 0.37  # Estimated marginal rate
    LONG_TERM_TAX_RATE = 0.20

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self._wash_windows: Dict[str, List[WashSaleWindow]] = {}
        self._substantially_identical: Dict[str, Set[str]] = self._build_identical_map()

    def find_opportunities(
        self,
        min_loss: Optional[float] = None,
        min_loss_pct: Optional[float] = None,
    ) -> List[HarvestOpportunity]:
        """
        Find all tax loss harvesting opportunities for the user.

        Returns sorted by estimated tax savings (highest first).
        """
        min_loss = min_loss or self.MIN_LOSS_THRESHOLD
        min_loss_pct = min_loss_pct or self.MIN_LOSS_PCT

        # Load wash sale windows
        self._load_wash_windows()

        # Get all positions with losses
        positions = (
            self.db.query(Position)
            .filter(
                Position.user_id == self.user_id,
                Position.quantity > 0,
            )
            .all()
        )

        opportunities = []

        for pos in positions:
            opp = self._evaluate_position(pos, min_loss, min_loss_pct)
            if opp:
                opportunities.append(opp)

        # Sort by estimated tax savings
        opportunities.sort(key=lambda x: x.estimated_tax_savings, reverse=True)

        return opportunities

    def check_wash_sale_risk(
        self,
        symbol: str,
        action: str,  # "buy" or "sell"
        trade_date: Optional[datetime] = None,
    ) -> Dict:
        """
        Check if a trade would trigger or be affected by wash sale rules.

        Returns:
            {
                "allowed": bool,
                "risk_level": "none" | "warning" | "blocked",
                "reason": str,
                "affected_symbols": [...],
                "window_end": datetime | None
            }
        """
        trade_date = trade_date or datetime.now(timezone.utc)
        self._load_wash_windows()

        result = {
            "allowed": True,
            "risk_level": "none",
            "reason": None,
            "affected_symbols": [],
            "window_end": None,
        }

        # Check if symbol is in an active wash sale window
        if symbol in self._wash_windows:
            for window in self._wash_windows[symbol]:
                if window.is_active(trade_date):
                    result["allowed"] = False if action == "buy" else True
                    result["risk_level"] = "blocked" if action == "buy" else "warning"
                    result["reason"] = (
                        f"Active wash sale window until {window.window_end.date()}"
                    )
                    result["window_end"] = window.window_end
                    return result

        # Check substantially identical securities
        identical = self._substantially_identical.get(symbol, set())
        for ident_symbol in identical:
            if ident_symbol in self._wash_windows:
                for window in self._wash_windows[ident_symbol]:
                    if window.is_active(trade_date):
                        result["allowed"] = action != "buy"
                        result["risk_level"] = "warning"
                        result["reason"] = (
                            f"Substantially identical to {ident_symbol} "
                            f"with active wash sale window"
                        )
                        result["affected_symbols"].append(ident_symbol)
                        if not result["window_end"] or window.window_end > result["window_end"]:
                            result["window_end"] = window.window_end

        return result

    def record_sale(
        self,
        symbol: str,
        quantity: float,
        sale_date: datetime,
        order_id: Optional[int] = None,
        was_loss: bool = True,
    ) -> Optional[WashSaleWindow]:
        """
        Record a sale and create wash sale window if it was at a loss.
        """
        if not was_loss:
            return None

        window = WashSaleWindow(
            symbol=symbol,
            sale_date=sale_date,
            window_start=sale_date - timedelta(days=self.WASH_SALE_DAYS_BEFORE),
            window_end=sale_date + timedelta(days=self.WASH_SALE_DAYS_AFTER),
            shares_sold=quantity,
            triggered_by_order_id=order_id,
        )

        if symbol not in self._wash_windows:
            self._wash_windows[symbol] = []
        self._wash_windows[symbol].append(window)

        logger.info(
            "Created wash sale window for %s: %s to %s",
            symbol,
            window.window_start.date(),
            window.window_end.date(),
        )

        return window

    def get_portfolio_summary(self) -> Dict:
        """
        Get summary of tax loss harvesting state for the portfolio.
        """
        opportunities = self.find_opportunities()

        total_harvestable = sum(
            o.unrealized_loss for o in opportunities if not o.wash_sale_blocked
        )
        total_blocked = sum(
            o.unrealized_loss for o in opportunities if o.wash_sale_blocked
        )
        total_tax_savings = sum(
            o.estimated_tax_savings for o in opportunities if not o.wash_sale_blocked
        )

        return {
            "total_opportunities": len(opportunities),
            "harvestable_count": sum(1 for o in opportunities if not o.wash_sale_blocked),
            "blocked_count": sum(1 for o in opportunities if o.wash_sale_blocked),
            "total_harvestable_loss": round(total_harvestable, 2),
            "total_blocked_loss": round(total_blocked, 2),
            "estimated_tax_savings": round(total_tax_savings, 2),
            "opportunities": [o.to_dict() for o in opportunities[:10]],  # Top 10
        }

    def _evaluate_position(
        self,
        position: Position,
        min_loss: float,
        min_loss_pct: float,
    ) -> Optional[HarvestOpportunity]:
        """Evaluate a single position for harvesting opportunity."""
        # Get current price
        price = self._get_price(position.symbol)
        if not price:
            return None

        # Get cost basis from tax lots
        tax_lots = (
            self.db.query(TaxLot)
            .filter(
                TaxLot.user_id == self.user_id,
                TaxLot.symbol == position.symbol,
                TaxLot.remaining_quantity > 0,
            )
            .order_by(TaxLot.acquisition_date)
            .all()
        )

        if not tax_lots:
            # Use position cost basis if no lots
            total_quantity = float(position.quantity or 0)
            cost_basis = float(position.cost_basis or 0)
            oldest_date = position.created_at
        else:
            total_quantity = sum(float(lot.remaining_quantity or 0) for lot in tax_lots)
            cost_basis = sum(
                float(lot.cost_per_share or 0) * float(lot.remaining_quantity or 0)
                for lot in tax_lots
            )
            oldest_date = tax_lots[0].acquisition_date

        if total_quantity <= 0:
            return None

        current_value = price * total_quantity
        unrealized_pnl = current_value - cost_basis
        loss_pct = (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0

        # Only consider losses
        if unrealized_pnl >= 0:
            return None

        unrealized_loss = abs(unrealized_pnl)

        # Check thresholds
        if unrealized_loss < min_loss or abs(loss_pct) < min_loss_pct:
            return None

        # Check holding period
        is_long_term = False
        if oldest_date:
            days_held = (datetime.now(timezone.utc) - oldest_date).days
            is_long_term = days_held > 365

        # Check wash sale window
        wash_blocked = False
        wash_reason = None
        check = self.check_wash_sale_risk(position.symbol, "sell")
        if check["risk_level"] == "blocked":
            wash_blocked = True
            wash_reason = check["reason"]

        # Calculate estimated tax savings
        tax_rate = self.LONG_TERM_TAX_RATE if is_long_term else self.SHORT_TERM_TAX_RATE
        estimated_savings = unrealized_loss * tax_rate

        # Determine suggested action
        if wash_blocked:
            suggested = "blocked"
        elif unrealized_loss >= min_loss * 3:  # High value opportunity
            suggested = "harvest"
        else:
            suggested = "wait"

        return HarvestOpportunity(
            symbol=position.symbol,
            position_id=position.id,
            current_price=price,
            cost_basis=cost_basis,
            unrealized_loss=unrealized_loss,
            loss_pct=loss_pct,
            quantity=total_quantity,
            tax_lots_count=len(tax_lots),
            oldest_lot_date=oldest_date,
            is_long_term=is_long_term,
            wash_sale_blocked=wash_blocked,
            wash_sale_reason=wash_reason,
            suggested_action=suggested,
            estimated_tax_savings=estimated_savings,
        )

    def _load_wash_windows(self) -> None:
        """Load active wash sale windows from recent loss sales."""
        if self._wash_windows:
            return  # Already loaded

        # Look at orders from last 61 days that resulted in losses
        cutoff = datetime.now(timezone.utc) - timedelta(days=61)

        loss_orders = (
            self.db.query(Order)
            .filter(
                Order.user_id == self.user_id,
                Order.side.ilike("sell"),
                Order.status == OrderStatus.FILLED.value,
                Order.filled_at >= cutoff,
            )
            .all()
        )

        for order in loss_orders:
            # Check if this was a loss sale (simplified - would check vs cost basis)
            filled_price = float(order.filled_avg_price or order.limit_price or 0)
            # For now, assume we track this properly elsewhere
            # In production, compare to cost basis

            self.record_sale(
                symbol=order.symbol,
                quantity=float(order.quantity),
                sale_date=order.filled_at,
                order_id=order.id,
                was_loss=True,  # Simplified
            )

    def _get_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol."""
        snapshot = (
            self.db.query(MarketSnapshot)
            .filter(
                MarketSnapshot.symbol == symbol,
                MarketSnapshot.analysis_type == "technical_snapshot",
            )
            .order_by(MarketSnapshot.analysis_timestamp.desc())
            .first()
        )

        if snapshot and snapshot.current_price:
            return float(snapshot.current_price)
        return None

    def _build_identical_map(self) -> Dict[str, Set[str]]:
        """
        Build map of substantially identical securities.

        These include:
        - ETFs tracking the same index (SPY/IVV/VOO)
        - Different share classes (BRK.A/BRK.B)
        - Options on the same underlying
        """
        identical = {
            # S&P 500 trackers
            "SPY": {"IVV", "VOO", "SPLG"},
            "IVV": {"SPY", "VOO", "SPLG"},
            "VOO": {"SPY", "IVV", "SPLG"},
            "SPLG": {"SPY", "IVV", "VOO"},
            # Nasdaq trackers
            "QQQ": {"QQQM"},
            "QQQM": {"QQQ"},
            # Total market
            "VTI": {"ITOT", "SPTM"},
            "ITOT": {"VTI", "SPTM"},
            # Bond funds
            "BND": {"AGG"},
            "AGG": {"BND"},
        }
        return identical
