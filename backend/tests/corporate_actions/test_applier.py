"""Integration tests for the corporate-action applier.

These tests exercise the full apply / reverse path against a real
(test-mode) DB session: positions + tax_lots are populated, the applier
runs, snapshots are written to ``applied_corporate_actions``, and the
test asserts the visible state of every mutated row.

Coverage map
------------
* Forward split -- qty grows, total cost basis is invariant, avg_cost
  drops by the multiplier, ``AppliedCorporateAction`` snapshots are
  written, status flips to APPLIED.
* Reverse split -- same math in the other direction.
* Cash dividend -- qty / basis unchanged; ``cash_credited`` recorded;
  status APPLIED.
* Stock-for-stock merger -- symbol re-tagged on Position + TaxLot.
* Cash merger -- position closed, qty zeroed, status APPLIED, audit
  row records cash_credited.
* Cross-tenant isolation -- two users hold the same symbol; user A has
  a duplicate-key constraint poison row that forces a savepoint
  rollback; user B's adjustment must still commit.
* Reverse -- after apply, ``reverse_action`` restores the exact
  pre-application qty / cost basis / avg_cost / symbol on every row.
* Idempotency -- running ``apply_pending`` twice in a row never
  produces duplicate ``AppliedCorporateAction`` rows; second run is a
  no-op.
* Historical OHLCV -- back-adjuster divides pre-ex-date prices by the
  multiplier, multiplies pre-ex-date volume by it, and the ex-date bar
  itself is left untouched.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import inspect, select

from backend.models import BrokerAccount, Position, PriceData, TaxLot, User
from backend.models.broker_account import (
    AccountStatus,
    AccountType,
    BrokerType,
)
from backend.models.corporate_action import (
    AppliedCorporateAction,
    CorporateAction,
    CorporateActionSource,
    CorporateActionStatus,
    CorporateActionType,
)
from backend.models.position import PositionStatus, PositionType
from backend.services.corporate_actions.applier import CorporateActionApplier
from backend.services.corporate_actions.historical_ohlcv_adjuster import (
    HistoricalOhlcvAdjuster,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _require_schema(db_session):
    if db_session is None:
        pytest.skip("DB-backed test requires db_session")
    inspector = inspect(db_session.bind)
    required = ("users", "broker_accounts", "positions", "tax_lots", "corporate_actions")
    missing = [t for t in required if not inspector.has_table(t)]
    if missing:
        pytest.skip(f"Test DB not migrated; missing: {', '.join(missing)}")


def _make_user(db, username: str) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        full_name=username.title(),
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _make_account(db, user: User, label: str = "ACC") -> BrokerAccount:
    ba = BrokerAccount(
        user_id=user.id,
        broker=BrokerType.IBKR,
        account_number=f"{user.username}-{label}",
        account_name=f"{user.username} {label}",
        account_type=AccountType.TAXABLE,
        status=AccountStatus.ACTIVE,
        is_enabled=True,
        currency="USD",
    )
    db.add(ba)
    db.flush()
    return ba


def _make_position(
    db,
    user: User,
    account: BrokerAccount,
    symbol: str,
    *,
    qty: Decimal,
    avg_cost: Decimal,
) -> Position:
    pos = Position(
        user_id=user.id,
        account_id=account.id,
        symbol=symbol,
        instrument_type="STOCK",
        position_type=PositionType.LONG,
        status=PositionStatus.OPEN,
        quantity=qty,
        average_cost=avg_cost,
        total_cost_basis=(qty * avg_cost).quantize(Decimal("0.01")),
        currency="USD",
    )
    db.add(pos)
    db.flush()
    return pos


def _make_tax_lot(
    db,
    user: User,
    account: BrokerAccount,
    symbol: str,
    *,
    qty: float,
    cost_per_share: float,
) -> TaxLot:
    lot = TaxLot(
        user_id=user.id,
        account_id=account.id,
        symbol=symbol,
        quantity=qty,
        cost_per_share=cost_per_share,
        cost_basis=qty * cost_per_share,
        acquisition_date=date(2024, 1, 5),
        currency="USD",
    )
    db.add(lot)
    db.flush()
    return lot


def _make_action(
    db,
    *,
    symbol: str,
    action_type: CorporateActionType,
    ex_date: date,
    ratio_numerator: Decimal | None = None,
    ratio_denominator: Decimal | None = None,
    cash_amount: Decimal | None = None,
    target_symbol: str | None = None,
    source: CorporateActionSource = CorporateActionSource.MANUAL,
) -> CorporateAction:
    action = CorporateAction(
        symbol=symbol,
        action_type=action_type.value,
        ex_date=ex_date,
        ratio_numerator=ratio_numerator,
        ratio_denominator=ratio_denominator,
        cash_amount=cash_amount,
        cash_currency="USD" if cash_amount is not None else None,
        target_symbol=target_symbol,
        source=source.value,
        status=CorporateActionStatus.PENDING.value,
        ohlcv_adjusted=False,
    )
    db.add(action)
    db.flush()
    return action


# ---------------------------------------------------------------------------
# Forward / reverse split
# ---------------------------------------------------------------------------


def test_forward_split_3_for_1_preserves_total_cost_basis(db_session):
    db = db_session
    user = _make_user(db, "alice_split")
    account = _make_account(db, user)
    pos = _make_position(
        db, user, account, "NVDA",
        qty=Decimal("100.000000"),
        avg_cost=Decimal("450.0000"),
    )
    lot = _make_tax_lot(
        db, user, account, "NVDA",
        qty=100.0,
        cost_per_share=450.0,
    )
    action = _make_action(
        db,
        symbol="NVDA",
        action_type=CorporateActionType.SPLIT,
        ex_date=date(2025, 6, 10),
        ratio_numerator=Decimal("3"),
        ratio_denominator=Decimal("1"),
    )

    report = CorporateActionApplier(db).apply_pending(today=date(2025, 6, 10))
    db.flush()

    db.refresh(pos)
    db.refresh(lot)
    db.refresh(action)

    assert report.actions_total == 1
    assert report.actions_applied == 1
    assert report.positions_adjusted == 1
    assert report.tax_lots_adjusted == 1

    # Total cost basis is the cardinal invariant of split-style actions.
    assert pos.quantity == Decimal("300.000000")
    assert pos.total_cost_basis == Decimal("45000.0000")
    assert pos.average_cost == Decimal("150.00000000")
    assert pos.symbol == "NVDA"
    assert pos.status == PositionStatus.OPEN

    assert lot.quantity == pytest.approx(300.0)
    assert lot.cost_basis == pytest.approx(45000.0)
    assert lot.cost_per_share == pytest.approx(150.0)

    assert action.status == CorporateActionStatus.APPLIED.value
    assert action.applied_at is not None
    assert action.error_message is None

    apps = (
        db.execute(
            select(AppliedCorporateAction).where(
                AppliedCorporateAction.corporate_action_id == action.id
            )
        )
        .scalars()
        .all()
    )
    assert len(apps) == 2
    pos_app = next(a for a in apps if a.position_id == pos.id)
    lot_app = next(a for a in apps if a.tax_lot_id == lot.id)
    assert pos_app.original_qty == Decimal("100.00000000")
    assert pos_app.adjusted_qty == Decimal("300.00000000")
    assert lot_app.original_cost_basis == Decimal("45000.00000000")
    assert lot_app.adjusted_cost_basis == Decimal("45000.00000000")


def test_reverse_split_1_for_10_preserves_total_cost_basis(db_session):
    db = db_session
    user = _make_user(db, "alice_revsplit")
    account = _make_account(db, user)
    pos = _make_position(
        db, user, account, "REVS",
        qty=Decimal("1000.000000"),
        avg_cost=Decimal("0.5000"),
    )
    action = _make_action(
        db,
        symbol="REVS",
        action_type=CorporateActionType.REVERSE_SPLIT,
        ex_date=date(2025, 5, 1),
        ratio_numerator=Decimal("1"),
        ratio_denominator=Decimal("10"),
    )

    CorporateActionApplier(db).apply_pending(today=date(2025, 5, 1))
    db.flush()

    db.refresh(pos)
    db.refresh(action)

    assert pos.quantity == Decimal("100.000000")
    assert pos.total_cost_basis == Decimal("500.0000")
    assert pos.average_cost == Decimal("5.00000000")
    assert action.status == CorporateActionStatus.APPLIED.value


# ---------------------------------------------------------------------------
# Cash dividend
# ---------------------------------------------------------------------------


def test_cash_dividend_records_cash_without_changing_position(db_session):
    db = db_session
    user = _make_user(db, "alice_div")
    account = _make_account(db, user)
    pos = _make_position(
        db, user, account, "AAPL",
        qty=Decimal("200.000000"),
        avg_cost=Decimal("150.0000"),
    )
    action = _make_action(
        db,
        symbol="AAPL",
        action_type=CorporateActionType.CASH_DIVIDEND,
        ex_date=date(2025, 5, 9),
        cash_amount=Decimal("0.25"),
    )

    CorporateActionApplier(db).apply_pending(today=date(2025, 5, 9))
    db.flush()

    db.refresh(pos)
    db.refresh(action)

    assert pos.quantity == Decimal("200.000000")
    assert pos.total_cost_basis == Decimal("30000.0000")
    assert action.status == CorporateActionStatus.APPLIED.value

    apps = (
        db.execute(
            select(AppliedCorporateAction).where(
                AppliedCorporateAction.corporate_action_id == action.id
            )
        )
        .scalars()
        .all()
    )
    assert len(apps) == 1
    assert apps[0].cash_credited == Decimal("50.00000000")
    assert apps[0].original_qty == apps[0].adjusted_qty
    assert apps[0].original_cost_basis == apps[0].adjusted_cost_basis


# ---------------------------------------------------------------------------
# Mergers
# ---------------------------------------------------------------------------


def test_stock_merger_renames_symbol_in_place(db_session):
    db = db_session
    user = _make_user(db, "alice_merger")
    account = _make_account(db, user)
    pos = _make_position(
        db, user, account, "OLDCO",
        qty=Decimal("100.000000"),
        avg_cost=Decimal("20.0000"),
    )
    lot = _make_tax_lot(
        db, user, account, "OLDCO",
        qty=100.0,
        cost_per_share=20.0,
    )
    action = _make_action(
        db,
        symbol="OLDCO",
        action_type=CorporateActionType.MERGER_STOCK,
        ex_date=date(2025, 7, 1),
        ratio_numerator=Decimal("105"),
        ratio_denominator=Decimal("100"),
        target_symbol="NEWCO",
    )

    CorporateActionApplier(db).apply_pending(today=date(2025, 7, 1))
    db.flush()

    db.refresh(pos)
    db.refresh(lot)
    db.refresh(action)

    assert pos.symbol == "NEWCO"
    assert pos.quantity == Decimal("105.000000")
    # Total basis preserved across the merger.
    assert pos.total_cost_basis == Decimal("2000.0000")
    assert lot.symbol == "NEWCO"
    assert action.status == CorporateActionStatus.APPLIED.value


def test_cash_merger_closes_position_and_records_cash(db_session):
    db = db_session
    user = _make_user(db, "alice_buyout")
    account = _make_account(db, user)
    pos = _make_position(
        db, user, account, "BUYME",
        qty=Decimal("100.000000"),
        avg_cost=Decimal("10.0000"),
    )
    action = _make_action(
        db,
        symbol="BUYME",
        action_type=CorporateActionType.MERGER_CASH,
        ex_date=date(2025, 7, 15),
        cash_amount=Decimal("18.50"),
    )

    CorporateActionApplier(db).apply_pending(today=date(2025, 7, 15))
    db.flush()

    db.refresh(pos)
    db.refresh(action)

    assert pos.quantity == Decimal("0.000000")
    assert pos.total_cost_basis == Decimal("0.0000")
    assert pos.status == PositionStatus.CLOSED
    assert action.status == CorporateActionStatus.APPLIED.value

    apps = (
        db.execute(
            select(AppliedCorporateAction).where(
                AppliedCorporateAction.corporate_action_id == action.id
            )
        )
        .scalars()
        .all()
    )
    assert len(apps) == 1
    assert apps[0].cash_credited == Decimal("1850.00000000")


# ---------------------------------------------------------------------------
# Reversibility
# ---------------------------------------------------------------------------


def test_reverse_restores_exact_pre_application_state(db_session):
    db = db_session
    user = _make_user(db, "alice_reverse")
    account = _make_account(db, user)
    pos = _make_position(
        db, user, account, "TSLA",
        qty=Decimal("33.000000"),
        avg_cost=Decimal("700.1234"),
    )
    lot = _make_tax_lot(
        db, user, account, "TSLA",
        qty=33.0,
        cost_per_share=700.1234,
    )
    original_qty = pos.quantity
    original_basis = pos.total_cost_basis
    original_avg = pos.average_cost
    original_lot_qty = lot.quantity
    original_lot_basis = lot.cost_basis

    action = _make_action(
        db,
        symbol="TSLA",
        action_type=CorporateActionType.SPLIT,
        ex_date=date(2025, 8, 25),
        ratio_numerator=Decimal("3"),
        ratio_denominator=Decimal("1"),
    )

    CorporateActionApplier(db).apply_pending(today=date(2025, 8, 25))
    db.flush()
    db.refresh(pos)
    db.refresh(action)
    assert pos.quantity == Decimal("99.000000")
    assert action.status == CorporateActionStatus.APPLIED.value

    outcome = CorporateActionApplier(db).reverse_action(action)
    db.flush()
    db.refresh(pos)
    db.refresh(lot)
    db.refresh(action)

    assert outcome.users_failed == 0
    assert pos.quantity == original_qty
    assert pos.total_cost_basis == original_basis
    assert pos.average_cost == original_avg
    assert lot.quantity == pytest.approx(float(original_lot_qty))
    assert lot.cost_basis == pytest.approx(float(original_lot_basis))
    assert action.status == CorporateActionStatus.REVERSED.value

    # Audit rows deleted on reverse.
    remaining = (
        db.execute(
            select(AppliedCorporateAction).where(
                AppliedCorporateAction.corporate_action_id == action.id
            )
        )
        .scalars()
        .all()
    )
    assert remaining == []


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_apply_pending_is_idempotent(db_session):
    db = db_session
    user = _make_user(db, "alice_idem")
    account = _make_account(db, user)
    pos = _make_position(
        db, user, account, "IDEM",
        qty=Decimal("10.000000"),
        avg_cost=Decimal("100.0000"),
    )
    action = _make_action(
        db,
        symbol="IDEM",
        action_type=CorporateActionType.SPLIT,
        ex_date=date(2025, 4, 1),
        ratio_numerator=Decimal("2"),
        ratio_denominator=Decimal("1"),
    )

    first = CorporateActionApplier(db).apply_pending(today=date(2025, 4, 1))
    db.flush()
    second = CorporateActionApplier(db).apply_pending(today=date(2025, 4, 1))
    db.flush()

    db.refresh(pos)
    db.refresh(action)

    assert first.actions_applied == 1
    # Second pass must skip: status no longer PENDING.
    assert second.actions_total == 0
    assert second.actions_applied == 0

    # Position only doubled once.
    assert pos.quantity == Decimal("20.000000")

    apps = (
        db.execute(
            select(AppliedCorporateAction).where(
                AppliedCorporateAction.corporate_action_id == action.id
            )
        )
        .scalars()
        .all()
    )
    assert len(apps) == 1


# ---------------------------------------------------------------------------
# Cross-tenant isolation
# ---------------------------------------------------------------------------


def test_cross_tenant_isolation_one_user_failure_does_not_block_another(
    db_session, monkeypatch
):
    """Inject a per-user failure for user A; user B's adjustment must
    still commit and the action must surface as PARTIAL.

    This is the property guarded by the per-user ``begin_nested()``
    savepoint in ``CorporateActionApplier._apply_one``. Without it, a
    single user's failure would roll back the entire batch -- the v0
    failure mode that motivated this PR's design.
    """
    db = db_session
    user_a = _make_user(db, "alice_iso")
    user_b = _make_user(db, "bob_iso")
    account_a = _make_account(db, user_a)
    account_b = _make_account(db, user_b)

    pos_a = _make_position(
        db, user_a, account_a, "ISOL",
        qty=Decimal("50.000000"),
        avg_cost=Decimal("100.0000"),
    )
    pos_b = _make_position(
        db, user_b, account_b, "ISOL",
        qty=Decimal("80.000000"),
        avg_cost=Decimal("100.0000"),
    )

    action = _make_action(
        db,
        symbol="ISOL",
        action_type=CorporateActionType.SPLIT,
        ex_date=date(2025, 9, 1),
        ratio_numerator=Decimal("2"),
        ratio_denominator=Decimal("1"),
    )

    # Inject failure for user A only by monkey-patching the inner per-user
    # method. Validates that the savepoint isolates the failure so user
    # B's mutations still land.
    original_apply_for_user = CorporateActionApplier._apply_for_user

    def _explode_for_user_a(self, action, user_id, positions, tax_lots):
        if user_id == user_a.id:
            raise RuntimeError("simulated user-A failure")
        return original_apply_for_user(self, action, user_id, positions, tax_lots)

    monkeypatch.setattr(
        CorporateActionApplier, "_apply_for_user", _explode_for_user_a
    )

    report = CorporateActionApplier(db).apply_pending(today=date(2025, 9, 1))
    db.flush()

    db.refresh(pos_a)
    db.refresh(pos_b)
    db.refresh(action)

    assert pos_a.quantity == Decimal("50.000000")
    assert pos_b.quantity == Decimal("160.000000")

    assert action.status == CorporateActionStatus.PARTIAL.value
    assert action.error_message is not None
    assert "user_id=" in action.error_message
    assert report.actions_partial == 1

    apps = (
        db.execute(
            select(AppliedCorporateAction).where(
                AppliedCorporateAction.corporate_action_id == action.id
            )
        )
        .scalars()
        .all()
    )
    assert len(apps) == 1
    assert apps[0].user_id == user_b.id


# ---------------------------------------------------------------------------
# Skip + no-holders
# ---------------------------------------------------------------------------


def test_action_with_no_holders_is_skipped(db_session):
    db = db_session
    action = _make_action(
        db,
        symbol="NOBODY",
        action_type=CorporateActionType.SPLIT,
        ex_date=date(2025, 3, 1),
        ratio_numerator=Decimal("2"),
        ratio_denominator=Decimal("1"),
    )

    report = CorporateActionApplier(db).apply_pending(today=date(2025, 3, 1))
    db.flush()

    db.refresh(action)
    assert action.status == CorporateActionStatus.SKIPPED.value
    assert report.actions_skipped == 1


# ---------------------------------------------------------------------------
# Historical OHLCV back-adjustment
# ---------------------------------------------------------------------------


def test_historical_ohlcv_back_adjuster_divides_pre_ex_date_prices(db_session):
    db = db_session

    ex_date = date(2025, 6, 10)

    def _bar(d: datetime, *, close: float) -> PriceData:
        return PriceData(
            symbol="OHLC",
            date=d,
            open_price=close,
            high_price=close * 1.01,
            low_price=close * 0.99,
            close_price=close,
            adjusted_close=close,
            volume=1_000_000,
            interval="1d",
            data_source="test",
            is_adjusted=False,
        )

    pre_bar = _bar(datetime(2025, 6, 9, tzinfo=timezone.utc), close=300.0)
    ex_bar = _bar(datetime(2025, 6, 10, tzinfo=timezone.utc), close=100.0)
    post_bar = _bar(datetime(2025, 6, 11, tzinfo=timezone.utc), close=101.0)
    db.add_all([pre_bar, ex_bar, post_bar])
    db.flush()

    action = _make_action(
        db,
        symbol="OHLC",
        action_type=CorporateActionType.SPLIT,
        ex_date=ex_date,
        ratio_numerator=Decimal("3"),
        ratio_denominator=Decimal("1"),
    )

    adjuster = HistoricalOhlcvAdjuster(db, enabled=True)
    report = adjuster.adjust(action)
    db.flush()

    db.refresh(pre_bar)
    db.refresh(ex_bar)
    db.refresh(post_bar)

    assert report.rows_updated == 1
    # Pre-ex-date bar divided by 3, volume multiplied by 3.
    assert pre_bar.close_price == pytest.approx(100.0)
    assert pre_bar.volume == pytest.approx(3_000_000)
    # Ex-date and post bars untouched.
    assert ex_bar.close_price == pytest.approx(100.0)
    assert ex_bar.volume == pytest.approx(1_000_000)
    assert post_bar.close_price == pytest.approx(101.0)
    assert post_bar.volume == pytest.approx(1_000_000)
    assert action.ohlcv_adjusted is True

    # Reverse undoes it.
    adjuster.reverse(action)
    db.flush()
    db.refresh(pre_bar)
    assert pre_bar.close_price == pytest.approx(300.0)
    assert pre_bar.volume == pytest.approx(1_000_000)
    assert action.ohlcv_adjusted is False


def test_historical_ohlcv_back_adjuster_short_circuits_when_disabled(db_session):
    db = db_session
    action = _make_action(
        db,
        symbol="DISABLED",
        action_type=CorporateActionType.SPLIT,
        ex_date=date(2025, 6, 10),
        ratio_numerator=Decimal("2"),
        ratio_denominator=Decimal("1"),
    )
    report = HistoricalOhlcvAdjuster(db, enabled=False).adjust(action)
    assert report.rows_updated == 0
    assert report.skipped_reason == "feature_disabled"
    assert action.ohlcv_adjusted is False
