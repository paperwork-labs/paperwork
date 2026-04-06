"""Position reconciliation service.

Compares internal position records against broker-reported positions
and generates discrepancy alerts.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy.orm import Session

from backend.models import AccountStatus, BrokerAccount, BrokerType
from backend.models.position import Position

logger = logging.getLogger(__name__)


class DiscrepancyType(Enum):
    """Types of position discrepancies."""

    QUANTITY_MISMATCH = "quantity_mismatch"
    COST_BASIS_MISMATCH = "cost_basis_mismatch"
    MISSING_IN_BROKER = "missing_in_broker"
    MISSING_IN_INTERNAL = "missing_in_internal"
    SYMBOL_MISMATCH = "symbol_mismatch"


@dataclass
class PositionDiscrepancy:
    """Represents a single position discrepancy."""

    symbol: str
    discrepancy_type: DiscrepancyType
    internal_value: Optional[str]
    broker_value: Optional[str]
    account_id: int
    detected_at: datetime
    severity: str  # "low", "medium", "high"

    def __str__(self) -> str:
        return (
            f"{self.discrepancy_type.value}: {self.symbol} - "
            f"internal={self.internal_value}, broker={self.broker_value}"
        )


class ReconciliationService:
    """Service for reconciling positions between internal records and brokers."""

    QUANTITY_TOLERANCE = Decimal("0.001")  # Allow tiny float rounding differences
    COST_BASIS_TOLERANCE = Decimal("0.01")  # $0.01 tolerance for cost basis

    def __init__(self, db: Session):
        self.db = db

    def reconcile_account(self, account_id: int) -> list[PositionDiscrepancy]:
        """Reconcile all positions for a single account.

        Returns list of discrepancies found.
        """
        account = self.db.query(BrokerAccount).filter(BrokerAccount.id == account_id).first()
        if not account:
            logger.warning("Account %d not found for reconciliation", account_id)
            return []

        internal_positions = self._get_internal_positions(account_id)
        broker_positions = self._fetch_broker_positions(account)
        if broker_positions is None:
            logger.info(
                "Skipping reconciliation for account %d: broker position fetch unavailable",
                account_id,
            )
            return []

        discrepancies = []
        now = datetime.now(timezone.utc)

        # Check internal positions against broker
        for symbol, internal_pos in internal_positions.items():
            broker_pos = broker_positions.get(symbol)

            if broker_pos is None:
                discrepancies.append(
                    PositionDiscrepancy(
                        symbol=symbol,
                        discrepancy_type=DiscrepancyType.MISSING_IN_BROKER,
                        internal_value=str(internal_pos["quantity"]),
                        broker_value=None,
                        account_id=account_id,
                        detected_at=now,
                        severity="high",
                    )
                )
                continue

            # Check quantity
            qty_diff = abs(
                Decimal(str(internal_pos["quantity"])) - Decimal(str(broker_pos["quantity"]))
            )
            if qty_diff > self.QUANTITY_TOLERANCE:
                discrepancies.append(
                    PositionDiscrepancy(
                        symbol=symbol,
                        discrepancy_type=DiscrepancyType.QUANTITY_MISMATCH,
                        internal_value=str(internal_pos["quantity"]),
                        broker_value=str(broker_pos["quantity"]),
                        account_id=account_id,
                        detected_at=now,
                        severity="high" if qty_diff > 1 else "medium",
                    )
                )

            # Check cost basis
            if internal_pos.get("cost_basis") and broker_pos.get("cost_basis"):
                cost_diff = abs(
                    Decimal(str(internal_pos["cost_basis"]))
                    - Decimal(str(broker_pos["cost_basis"]))
                )
                if cost_diff > self.COST_BASIS_TOLERANCE:
                    discrepancies.append(
                        PositionDiscrepancy(
                            symbol=symbol,
                            discrepancy_type=DiscrepancyType.COST_BASIS_MISMATCH,
                            internal_value=str(internal_pos["cost_basis"]),
                            broker_value=str(broker_pos["cost_basis"]),
                            account_id=account_id,
                            detected_at=now,
                            severity="low",
                        )
                    )

        # Check for positions in broker not in internal
        for symbol, broker_pos in broker_positions.items():
            if symbol not in internal_positions:
                discrepancies.append(
                    PositionDiscrepancy(
                        symbol=symbol,
                        discrepancy_type=DiscrepancyType.MISSING_IN_INTERNAL,
                        internal_value=None,
                        broker_value=str(broker_pos["quantity"]),
                        account_id=account_id,
                        detected_at=now,
                        severity="high",
                    )
                )

        if discrepancies:
            logger.warning(
                "Found %d discrepancies for account %d",
                len(discrepancies),
                account_id,
            )
        else:
            logger.info("Account %d reconciled successfully", account_id)

        return discrepancies

    def _get_internal_positions(self, account_id: int) -> dict[str, dict]:
        """Get internal positions as dict keyed by symbol."""
        positions = (
            self.db.query(Position)
            .filter(Position.account_id == account_id, Position.quantity != 0)
            .all()
        )
        return {
            p.symbol: {
                "quantity": p.quantity,
                "cost_basis": p.total_cost_basis,
            }
            for p in positions
        }

    def _fetch_broker_positions(self, account: BrokerAccount) -> Optional[dict[str, dict]]:
        """Fetch positions from broker API.

        Returns None when the broker adapter is not implemented yet (skip reconcile).
        Override in subclasses for different brokers.
        """
        if account.broker == BrokerType.IBKR:
            return self._fetch_ibkr_positions(account)
        # Add other brokers as needed
        logger.warning("Broker %s not supported for reconciliation", account.broker)
        return {}

    def _fetch_ibkr_positions(self, account: BrokerAccount) -> Optional[dict[str, dict]]:
        """Fetch positions from IBKR."""
        # This would integrate with the IBKR client
        # Return None until implemented — empty dict would mark all internal rows MISSING_IN_BROKER
        logger.info("IBKR position fetch for reconciliation not yet implemented")
        return None


def reconcile_all_accounts(db: Session) -> dict[int, list[PositionDiscrepancy]]:
    """Reconcile all active accounts.

    Returns dict of account_id -> list of discrepancies.
    """
    service = ReconciliationService(db)
    accounts = (
        db.query(BrokerAccount)
        .filter(
            BrokerAccount.status == AccountStatus.ACTIVE,
            BrokerAccount.is_enabled.is_(True),
        )
        .all()
    )

    results = {}
    for account in accounts:
        discrepancies = service.reconcile_account(account.id)
        if discrepancies:
            results[account.id] = discrepancies

    return results


# NOTE: Instantiate ``ReconciliationService(db)`` with a caller-owned session in tasks
# and routes; there is no module-level singleton.
