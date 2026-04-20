"""Unit tests for MCP portfolio tool query scoping."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from backend.mcp.tools.portfolio import get_holdings, get_recent_explanations
from backend.models.auto_ops_explanation import AutoOpsExplanation
from backend.models.broker_account import (
    AccountStatus,
    AccountType,
    BrokerAccount,
    BrokerType,
)
from backend.models.position import Position, PositionStatus, PositionType
from backend.models.user import User, UserRole


def _user(db, *, suffix: str) -> User:
    u = User(
        username=f"mcp_pt_{suffix}",
        email=f"mcp_pt_{suffix}@example.com",
        full_name=f"MCP PT {suffix}",
        role=UserRole.OWNER,
        is_active=True,
        is_approved=True,
        is_verified=True,
        password_hash="x",
    )
    db.add(u)
    db.flush()
    return u


def _broker_account(db, user: User) -> BrokerAccount:
    a = BrokerAccount(
        user_id=user.id,
        broker=BrokerType.IBKR,
        account_number=f"DU_PT_{user.id}",
        account_type=AccountType.TAXABLE,
        status=AccountStatus.ACTIVE,
    )
    db.add(a)
    db.flush()
    return a


def test_get_holdings_open_equity_only(db_session):
    """Only quantity > 0, equity instrument, long posture positions are returned."""
    user = _user(db_session, suffix="hold")
    acct = _broker_account(db_session, user)

    db_session.add_all(
        [
            Position(
                user_id=user.id,
                account_id=acct.id,
                symbol="OPENEQ",
                instrument_type="STOCK",
                position_type=PositionType.LONG,
                status=PositionStatus.OPEN,
                quantity=Decimal("10"),
                average_cost=Decimal("100"),
                current_price=Decimal("100"),
                market_value=Decimal("1000"),
                currency="USD",
            ),
            Position(
                user_id=user.id,
                account_id=acct.id,
                symbol="CLOSED",
                instrument_type="STOCK",
                position_type=PositionType.LONG,
                status=PositionStatus.CLOSED,
                quantity=Decimal("0"),
                average_cost=Decimal("50"),
                current_price=Decimal("50"),
                market_value=Decimal("0"),
                currency="USD",
            ),
            Position(
                user_id=user.id,
                account_id=acct.id,
                symbol="OPT",
                instrument_type="OPTION",
                position_type=PositionType.OPTION_LONG,
                status=PositionStatus.OPEN,
                quantity=Decimal("1"),
                average_cost=Decimal("2"),
                current_price=Decimal("2"),
                market_value=Decimal("2"),
                currency="USD",
            ),
        ]
    )
    db_session.flush()

    out = get_holdings(db_session, user.id)
    syms = [h["symbol"] for h in out["holdings"]]
    assert syms == ["OPENEQ"]


def test_get_recent_explanations_filters_by_user_id(db_session):
    """Rows for another user must never appear in the MCP tool result."""
    user_a = _user(db_session, suffix="ex_a")
    user_b = _user(db_session, suffix="ex_b")
    now = datetime.now(timezone.utc)

    def _row(uid: int, aid: str, title: str) -> AutoOpsExplanation:
        return AutoOpsExplanation(
            user_id=uid,
            schema_version="1.0.0",
            anomaly_id=aid,
            category="other",
            severity="info",
            title=title,
            summary="summary",
            confidence=Decimal("0.500"),
            is_fallback=False,
            model="test-model",
            payload_json={"ok": True},
            generated_at=now,
        )

    db_session.add_all(
        [
            _row(user_a.id, "anom-a-1", "for A"),
            _row(user_b.id, "anom-b-1", "for B"),
        ]
    )
    db_session.flush()

    out_a = get_recent_explanations(db_session, user_a.id, limit=10)
    titles_a = {e["title"] for e in out_a["explanations"]}
    assert titles_a == {"for A"}

    out_b = get_recent_explanations(db_session, user_b.id, limit=10)
    titles_b = {e["title"] for e in out_b["explanations"]}
    assert titles_b == {"for B"}
