"""Portfolio allocation aggregator.

Powers the `/portfolio/allocation` page (treemap + sunburst). Returns
positions aggregated by sector, asset class, or account, scoped to the
authenticated user.

Group keys are stable (lowercase slugs) so the frontend can reliably
deeplink to a specific group. Money values are computed in ``Decimal``
to avoid float drift on aggregation, then serialized as ``float`` once
at the response boundary -- the JSON contract is unchanged.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user
from backend.database import get_db
from backend.models.broker_account import BrokerAccount
from backend.models.position import Position, PositionStatus
from backend.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()

GroupBy = Literal["sector", "asset_class", "account"]


# Friendly labels for asset classes derived from `Position.instrument_type`.
# The Position table is "equity-only" today, but we still map other types so
# this surface keeps working when options or futures land in the same table
# without code changes here.
_ASSET_CLASS_LABELS: Dict[str, str] = {
    "STOCK": "Equity",
    "ETF": "Equity",
    "OPTION": "Option",
    "FUTURE": "Future",
    "CRYPTO": "Crypto",
    "BOND": "Bond",
    "CASH": "Cash",
}


def _asset_class_for(position: Position) -> str:
    """Map a position's instrument_type to a user-facing asset class label.

    Unknown / missing types fall through to ``"Other"`` -- importantly NOT
    silently dropped. Surfacing them as "Other" keeps the totals honest while
    flagging an unexpected category in the UI.
    """
    raw = (position.instrument_type or "").strip().upper()
    if not raw:
        return "Other"
    return _ASSET_CLASS_LABELS.get(raw, raw.title())


def _account_label(account: Optional[BrokerAccount]) -> Tuple[str, str]:
    """Return ``(group_key, group_label)`` for an account grouping.

    The key uses a stable, URL-safe identifier (the account id) so the UI
    can encode drill-down state in the URL without leaking account numbers.
    The label prefers the user-set ``account_name`` and falls back to the
    broker + last-four of the account number.
    """
    if account is None:
        return ("unknown", "Unknown account")
    key = f"acct-{account.id}"
    if account.account_name and account.account_name.strip():
        return (key, account.account_name.strip())
    broker = account.broker.value if account.broker else "broker"
    last4 = (account.account_number or "")[-4:] or "????"
    return (key, f"{broker.upper()} -{last4}")


def _group_key_label(position: Position, group_by: GroupBy) -> Tuple[str, str]:
    """Compute the ``(group_key, group_label)`` for a single position."""
    if group_by == "sector":
        sector = (position.sector or "").strip() or "Other"
        return (sector.lower().replace(" ", "-"), sector)
    if group_by == "asset_class":
        label = _asset_class_for(position)
        return (label.lower().replace(" ", "-"), label)
    if group_by == "account":
        return _account_label(position.account)
    raise ValueError(f"Unsupported group_by: {group_by}")


@router.get("/allocation", response_model=Dict[str, Any])
async def get_allocation(
    group_by: GroupBy = Query(
        "sector",
        description="How to bucket positions: sector | asset_class | account",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return the user's open positions aggregated by the requested grouping.

    Tenant scoping: every query joins through ``BrokerAccount`` and filters on
    ``BrokerAccount.user_id``. The ``Position.user_id`` column is also filtered
    as belt-and-suspenders so a stale cross-tenant ``Position`` row cannot
    leak.
    """
    positions: List[Position] = (
        db.query(Position)
        .join(BrokerAccount, Position.account_id == BrokerAccount.id)
        .filter(BrokerAccount.user_id == current_user.id)
        .filter(Position.user_id == current_user.id)
        .filter(Position.status == PositionStatus.OPEN)
        .all()
    )

    # Aggregate market value per group, and keep a per-group holdings list so
    # the frontend drill-down doesn't need a second roundtrip. Decimal is used
    # throughout to avoid the classic 0.1+0.2 drift on totals.
    group_totals: Dict[str, Decimal] = {}
    group_labels: Dict[str, str] = {}
    group_holdings: Dict[str, List[Tuple[str, Decimal]]] = {}
    grand_total = Decimal("0")

    for pos in positions:
        market_value = pos.market_value
        if market_value is None:
            # Don't silently zero out positions we have no price for; logging
            # surfaces missing pricing in ops dashboards instead of producing
            # a quietly-wrong pie (see no-silent-fallback.mdc).
            logger.debug(
                "allocation: skipping position id=%s symbol=%s with no market_value",
                pos.id,
                pos.symbol,
            )
            continue
        value = (
            market_value
            if isinstance(market_value, Decimal)
            else Decimal(str(market_value))
        )
        # Negatives (short positions) would distort percentages and treemap
        # rectangles. Use absolute exposure for sizing.
        value = abs(value)

        key, label = _group_key_label(pos, group_by)
        group_totals[key] = group_totals.get(key, Decimal("0")) + value
        group_labels.setdefault(key, label)
        group_holdings.setdefault(key, []).append((pos.symbol, value))
        grand_total += value

    # Sort groups by descending value so the treemap renders the heaviest
    # bucket top-left without any client-side sort. Holdings sort the same way
    # per group for the drill-down list.
    groups: List[Dict[str, Any]] = []
    sorted_keys = sorted(
        group_totals.keys(), key=lambda k: group_totals[k], reverse=True
    )
    for key in sorted_keys:
        total = group_totals[key]
        pct = (
            (total / grand_total * Decimal("100")) if grand_total > 0 else Decimal("0")
        )
        holdings_list = sorted(
            group_holdings[key], key=lambda h: h[1], reverse=True
        )
        holdings_payload: List[Dict[str, Any]] = []
        for symbol, value in holdings_list:
            holding_pct = (
                (value / grand_total * Decimal("100"))
                if grand_total > 0
                else Decimal("0")
            )
            holdings_payload.append(
                {
                    "symbol": symbol,
                    "value": float(value),
                    "percentage": float(holding_pct),
                }
            )
        groups.append(
            {
                "key": key,
                "label": group_labels[key],
                "total_value": float(total),
                "percentage": float(pct),
                "holdings": holdings_payload,
            }
        )

    return {
        "group_by": group_by,
        "total_value": float(grand_total),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "groups": groups,
    }
