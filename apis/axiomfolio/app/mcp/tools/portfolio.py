"""Read-only portfolio tools exposed to MCP clients.

All tools accept ``(db, user_id, **kwargs)`` and filter every query on
``user_id`` (or via ``BrokerAccount.user_id`` for tables that don't
have it directly). The transport layer in :mod:`backend.mcp.server`
guarantees that ``user_id`` comes from the authenticated bearer token
and not from caller-supplied arguments.

Numeric values are rendered as decimal strings (never floats) to
preserve precision across the JSON wire and to satisfy the project's
"never float for money" iron law.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models import (
    AutoOpsExplanation,
    BrokerAccount,
    Position,
    PositionType,
    Trade,
)
from app.models.market_data import MarketSnapshot
from app.models.picks import PickEngagement, ValidatedPick
from app.models.transaction import Dividend

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _money(value: Any | None) -> str | None:
    """Render a Decimal/Float as a lossless decimal string, or None."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return format(value, "f")
    return format(Decimal(str(value)), "f")


def _iso(ts: datetime | None) -> str | None:
    """ISO-8601 UTC string for a datetime (None-safe)."""
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts.isoformat()


def _user_account_ids(db: Session, user_id: int) -> list[int]:
    """All broker_account ids belonging to ``user_id`` (enabled or not)."""
    rows = db.query(BrokerAccount.id).filter(BrokerAccount.user_id == user_id).all()
    return [r[0] for r in rows]


# ----------------------------------------------------------------------
# Tool: get_holdings
# ----------------------------------------------------------------------


def get_holdings(db: Session, user_id: int) -> dict[str, Any]:
    """Return open long equity positions (quantity > 0, equity instrument) for the authenticated user.

    Excludes closed rows (quantity zero), shorts/options/futures via
    ``instrument_type`` and ``position_type``, and any non-long posture.
    """
    equity_instrument = func.coalesce(Position.instrument_type, "STOCK") == "STOCK"
    long_only = or_(
        Position.position_type.is_(None),
        Position.position_type == PositionType.LONG,
    )
    rows = (
        db.query(Position)
        .filter(Position.user_id == user_id)
        .filter(Position.quantity > 0)
        .filter(equity_instrument)
        .filter(long_only)
        .order_by(Position.symbol.asc())
        .all()
    )
    holdings: list[dict[str, Any]] = []
    total_market_value = Decimal("0")
    for p in rows:
        mv = p.market_value or Decimal("0")
        if isinstance(mv, (int, float)):
            mv = Decimal(str(mv))
        total_market_value += mv
        holdings.append(
            {
                "symbol": p.symbol,
                "quantity": _money(p.quantity),
                "average_cost": _money(p.average_cost),
                "current_price": _money(p.current_price),
                "market_value": _money(p.market_value),
                "unrealized_pnl": _money(p.unrealized_pnl),
                "unrealized_pnl_pct": _money(p.unrealized_pnl_pct),
                "position_size_pct": _money(p.position_size_pct),
                "currency": p.currency or "USD",
                "sector": p.sector,
                "account_id": p.account_id,
                "status": p.status.value if p.status is not None else None,
            }
        )
    return {
        "as_of": _iso(datetime.now(UTC)),
        "holdings_count": len(holdings),
        "total_market_value": _money(total_market_value),
        "holdings": holdings,
    }


# ----------------------------------------------------------------------
# Tool: get_recent_trades
# ----------------------------------------------------------------------


def get_recent_trades(db: Session, user_id: int, days: int = 30) -> dict[str, Any]:
    """Trades executed in the last ``days`` for the user's accounts."""
    if not isinstance(days, int) or days <= 0:
        raise ValueError("days must be a positive integer")
    if days > 3650:
        raise ValueError("days must be <= 3650")

    account_ids = _user_account_ids(db, user_id)
    if not account_ids:
        return {
            "window_days": days,
            "trades_count": 0,
            "trades": [],
        }

    since = datetime.now(UTC) - timedelta(days=days)
    rows = (
        db.query(Trade)
        .filter(Trade.account_id.in_(account_ids))
        .filter(Trade.execution_time >= since)
        .order_by(Trade.execution_time.desc())
        .limit(500)
        .all()
    )
    trades: list[dict[str, Any]] = []
    for t in rows:
        trades.append(
            {
                "id": t.id,
                "symbol": t.symbol,
                "side": t.side,
                "quantity": _money(t.quantity),
                "price": _money(t.price),
                "total_value": _money(t.total_value),
                "commission": _money(t.commission),
                "fees": _money(t.fees),
                "realized_pnl": _money(t.realized_pnl),
                "execution_time": _iso(t.execution_time),
                "order_type": t.order_type,
                "status": t.status,
                "is_opening": bool(t.is_opening) if t.is_opening is not None else None,
                "account_id": t.account_id,
            }
        )
    return {
        "window_days": days,
        "since": _iso(since),
        "trades_count": len(trades),
        "trades": trades,
    }


# ----------------------------------------------------------------------
# Tool: get_dividend_summary
# ----------------------------------------------------------------------


def get_dividend_summary(db: Session, user_id: int, days: int = 365) -> dict[str, Any]:
    """Per-symbol dividend aggregation over the last ``days``."""
    if not isinstance(days, int) or days <= 0:
        raise ValueError("days must be a positive integer")
    if days > 3650:
        raise ValueError("days must be <= 3650")

    account_ids = _user_account_ids(db, user_id)
    if not account_ids:
        return {
            "window_days": days,
            "symbols_count": 0,
            "total_net_dividend": "0",
            "by_symbol": [],
        }

    since = datetime.now(UTC) - timedelta(days=days)
    rows = (
        db.query(Dividend)
        .filter(Dividend.account_id.in_(account_ids))
        .filter(Dividend.ex_date >= since)
        .order_by(Dividend.ex_date.desc())
        .all()
    )

    per_symbol: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "gross": Decimal("0"),
            "tax": Decimal("0"),
            "net": Decimal("0"),
            "payments": 0,
            "currency": "USD",
            "last_pay_date": None,
        }
    )
    total_net = Decimal("0")
    for d in rows:
        agg = per_symbol[d.symbol]
        gross = Decimal(str(d.total_dividend or 0))
        tax = Decimal(str(d.tax_withheld or 0))
        net = Decimal(str(d.net_dividend or 0))
        agg["gross"] += gross
        agg["tax"] += tax
        agg["net"] += net
        agg["payments"] += 1
        agg["currency"] = d.currency or agg["currency"]
        if d.pay_date is not None:
            iso_pay = _iso(d.pay_date)
            if agg["last_pay_date"] is None or iso_pay > agg["last_pay_date"]:
                agg["last_pay_date"] = iso_pay
        total_net += net

    by_symbol = [
        {
            "symbol": sym,
            "gross_dividend": _money(agg["gross"]),
            "tax_withheld": _money(agg["tax"]),
            "net_dividend": _money(agg["net"]),
            "payments": agg["payments"],
            "currency": agg["currency"],
            "last_pay_date": agg["last_pay_date"],
        }
        for sym, agg in sorted(per_symbol.items(), key=lambda kv: kv[1]["net"], reverse=True)
    ]

    return {
        "window_days": days,
        "since": _iso(since),
        "symbols_count": len(by_symbol),
        "total_net_dividend": _money(total_net),
        "by_symbol": by_symbol,
    }


# ----------------------------------------------------------------------
# Tool: get_stage_summary
# ----------------------------------------------------------------------


def get_stage_summary(db: Session, user_id: int) -> dict[str, Any]:
    """Distribution of Weinstein stage labels across the user's holdings."""
    rows = (
        db.query(Position.symbol, Position.market_value, MarketSnapshot.stage_label)
        .outerjoin(MarketSnapshot, MarketSnapshot.symbol == Position.symbol)
        .filter(Position.user_id == user_id)
        .all()
    )
    by_stage: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"symbols": [], "market_value": Decimal("0")}
    )
    total_value = Decimal("0")
    for symbol, market_value, stage_label in rows:
        label = stage_label or "UNKNOWN"
        bucket = by_stage[label]
        if symbol not in bucket["symbols"]:
            bucket["symbols"].append(symbol)
        if market_value is not None:
            mv = market_value if isinstance(market_value, Decimal) else Decimal(str(market_value))
            bucket["market_value"] += mv
            total_value += mv

    summary = sorted(
        (
            {
                "stage": stage,
                "symbol_count": len(b["symbols"]),
                "symbols": b["symbols"],
                "market_value": _money(b["market_value"]),
            }
            for stage, b in by_stage.items()
        ),
        key=lambda r: r["stage"],
    )
    return {
        "as_of": _iso(datetime.now(UTC)),
        "total_market_value": _money(total_value),
        "stages": summary,
    }


# ----------------------------------------------------------------------
# Tool: get_recent_explanations
# ----------------------------------------------------------------------


def get_recent_explanations(db: Session, user_id: int, limit: int = 10) -> dict[str, Any]:
    """Recent AutoOps anomaly summaries persisted for the authenticated user.

    Returns a tenant-safe subset (title, summary, category, severity,
    generated_at) and omits ``payload_json`` so third-party MCP clients
    cannot pull operational internals. Rows with NULL ``user_id`` are
    system-scoped and are not returned here (use admin HTTP routes for
    platform-wide audit history).
    """
    if not isinstance(limit, int) or limit <= 0:
        raise ValueError("limit must be a positive integer")
    if limit > 100:
        raise ValueError("limit must be <= 100")

    rows = (
        db.query(AutoOpsExplanation)
        .filter(AutoOpsExplanation.user_id == user_id)
        .order_by(AutoOpsExplanation.generated_at.desc())
        .limit(limit)
        .all()
    )
    explanations = [
        {
            "anomaly_id": r.anomaly_id,
            "title": r.title,
            "summary": r.summary,
            "category": r.category,
            "severity": r.severity,
            "confidence": _money(r.confidence),
            "is_fallback": bool(r.is_fallback),
            "generated_at": _iso(r.generated_at),
        }
        for r in rows
    ]
    return {
        "scope": "user",
        "explanations_count": len(explanations),
        "explanations": explanations,
    }


# ----------------------------------------------------------------------
# Tool: get_pick_history
# ----------------------------------------------------------------------


def get_pick_history(db: Session, user_id: int, limit: int = 50) -> dict[str, Any]:
    """Validated picks the user has engaged with (viewed / executed)."""
    if not isinstance(limit, int) or limit <= 0:
        raise ValueError("limit must be a positive integer")
    if limit > 500:
        raise ValueError("limit must be <= 500")

    rows = (
        db.query(PickEngagement, ValidatedPick)
        .join(ValidatedPick, PickEngagement.pick_id == ValidatedPick.id)
        .filter(PickEngagement.user_id == user_id)
        .order_by(PickEngagement.occurred_at.desc())
        .limit(limit)
        .all()
    )

    items: list[dict[str, Any]] = []
    for engagement, pick in rows:
        action = pick.action.value if pick.action is not None else None
        status = pick.status.value if pick.status is not None else None
        eng_type = (
            engagement.engagement_type.value if engagement.engagement_type is not None else None
        )
        items.append(
            {
                "engagement_id": engagement.id,
                "engagement_type": eng_type,
                "occurred_at": _iso(engagement.occurred_at),
                "pick_id": pick.id,
                "symbol": pick.symbol,
                "action": action,
                "conviction": pick.conviction,
                "reason_summary": pick.reason_summary,
                "suggested_entry": _money(pick.suggested_entry),
                "suggested_stop": _money(pick.suggested_stop),
                "suggested_target": _money(pick.suggested_target),
                "suggested_size_pct": _money(pick.suggested_size_pct),
                "validator_pseudonym": pick.validator_pseudonym,
                "pick_status": status,
                "published_at": _iso(pick.published_at),
                "expires_at": _iso(pick.expires_at),
            }
        )
    return {"items_count": len(items), "items": items}


# ----------------------------------------------------------------------
# Tool catalog (advertised via tools/list)
# ----------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "get_holdings",
        "description": (
            "List all open equity positions for the authenticated user. "
            "Each holding includes symbol, quantity, average cost, "
            "current price, market value, unrealized P&L, position size "
            "(percent of portfolio), and sector."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "get_recent_trades",
        "description": (
            "Trades executed within the last N days across all of the "
            "user's broker accounts. Returns up to 500 most-recent rows."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 3650,
                    "default": 30,
                    "description": "Lookback window in days (default 30).",
                }
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "get_dividend_summary",
        "description": (
            "Per-symbol dividend aggregation over the last N days: "
            "gross, tax withheld, net, payment count, and last pay date."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 3650,
                    "default": 365,
                    "description": "Lookback window in days (default 365).",
                }
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "get_stage_summary",
        "description": (
            "Distribution of Weinstein stage labels (1A..4C) across the "
            "user's holdings, with symbol counts and aggregate market "
            "value per stage."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "get_recent_explanations",
        "description": (
            "Recent AutoOps anomaly summaries for the authenticated user "
            "(title, category, severity, narrative). System-wide rows are "
            "excluded; use admin routes for platform audit history."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 10,
                    "description": "Max rows to return (default 10).",
                }
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "get_pick_history",
        "description": (
            "Validated picks the authenticated user has engaged with "
            "(viewed, executed, etc.), newest first."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 500,
                    "default": 50,
                    "description": "Max rows to return (default 50).",
                }
            },
            "additionalProperties": False,
        },
    },
]


TOOL_HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "get_holdings": get_holdings,
    "get_recent_trades": get_recent_trades,
    "get_dividend_summary": get_dividend_summary,
    "get_stage_summary": get_stage_summary,
    "get_recent_explanations": get_recent_explanations,
    "get_pick_history": get_pick_history,
}
