"""Unit tests for :class:`TradeCardComposer`.

The composer turns a scored candidate plus the latest snapshot/regime into an
executable trade card. These tests cover:

* a clean Stage 2A setup in a long-biased regime — expect a card with
  computed sizing and a full alert set;
* a regime R3 constraint where stage cap is still positive but smaller;
* an edge case where no candidate input is provided (the route-level empty
  path) — exercised via the public API route to prove the ``empty`` state
  is distinct from the ``data`` state.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.dependencies import get_current_user
from backend.database import get_db
from backend.models.broker_account import (
    AccountStatus,
    AccountType,
    BrokerAccount,
    BrokerType,
)
from backend.models.market_data import MarketRegime, MarketSnapshot
from backend.models.picks import Candidate, CandidateQueueState, PickAction
from backend.models.user import User, UserRole
from backend.services.gold.trade_card_composer import (
    ContractRecommendation,
    ContractStatus,
    ContractType,
    SizingStatus,
    TradeCardComposer,
    UnderlyingView,
    _resolve_contract_status_for_earnings,
    trade_card_to_payload,
)


# ---------------------------------------------------------------------------
# Fixtures (inline helpers; keep tests hermetic)
# ---------------------------------------------------------------------------


def _user(db_session, *, email: str = "trader@example.com") -> User:
    u = User(
        email=email,
        username=email.split("@")[0],
        password_hash="x",
        role=UserRole.ANALYST,
        is_active=True,
        is_verified=True,
        is_approved=True,
    )
    db_session.add(u)
    db_session.flush()
    return u


def _broker_account(
    db_session,
    *,
    user_id: int,
    total_value: Decimal,
    account_number: str = "U00000001",
) -> BrokerAccount:
    acct = BrokerAccount(
        user_id=user_id,
        broker=BrokerType.IBKR,
        account_number=account_number,
        account_type=AccountType.TAXABLE,
        status=AccountStatus.ACTIVE,
        total_value=total_value,
        cash_balance=total_value,
        buying_power=total_value,
    )
    db_session.add(acct)
    db_session.flush()
    return acct


def _regime(db_session, *, code: str) -> MarketRegime:
    row = MarketRegime(
        as_of_date=datetime.now(timezone.utc).replace(tzinfo=None),
        regime_state=code,
        composite_score=2.0,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _snapshot(
    db_session,
    *,
    symbol: str = "ACME",
    stage_label: str = "2A",
    rs: float | None = 88.0,
    current_price: float = 100.0,
    atrp_14: float = 2.5,
    sma_21: float = 97.0,
    atr_14: float = 2.5,
    next_earnings: datetime | None = None,
    td_buy: int | None = 8,
    td_sell: int | None = 0,
) -> MarketSnapshot:
    now = datetime.now(timezone.utc)
    row = MarketSnapshot(
        symbol=symbol,
        analysis_type="technical_snapshot",
        analysis_timestamp=now,
        as_of_timestamp=now,
        expiry_timestamp=now + timedelta(hours=24),
        is_valid=True,
        stage_label=stage_label,
        rs_mansfield_pct=rs,
        ext_pct=2.0,
        current_price=current_price,
        high_52w=current_price * 1.1,
        atr_14=atr_14,
        atrp_14=atrp_14,
        sma_21=sma_21,
        volume_avg_20d=500_000.0,
        td_buy_setup=td_buy,
        td_sell_setup=td_sell,
        next_earnings=next_earnings,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _candidate(
    db_session,
    *,
    symbol: str = "ACME",
    pick_quality_score: float | None = 72.5,
) -> Candidate:
    row = Candidate(
        symbol=symbol,
        generator_name="test-generator",
        generator_version="v1",
        score=85.0,
        pick_quality_score=pick_quality_score,
        action_suggestion=PickAction.BUY,
        status=CandidateQueueState.DRAFT,
        generated_at=datetime.now(timezone.utc),
    )
    db_session.add(row)
    db_session.flush()
    return row


class _FakeChain:
    """In-memory :class:`OptionsChainSurface` that returns a preset contract."""

    def __init__(self, rec: ContractRecommendation | None) -> None:
        self.rec = rec
        self.calls: list[dict] = []

    def recommend_contract(self, db, *, symbol, current_price, earnings_date, bias):
        self.calls.append(
            {
                "symbol": symbol,
                "current_price": current_price,
                "earnings_date": earnings_date,
                "bias": bias,
            }
        )
        return self.rec


def _contract_rec(
    *,
    expiry_days: int = 30,
    expiry: date | None = None,
    mid: Decimal = Decimal("3.50"),
    strike: Decimal = Decimal("100"),
) -> ContractRecommendation:
    if expiry is None:
        expiry = (datetime.now(timezone.utc) + timedelta(days=expiry_days)).date()
    bid = (mid - Decimal("0.05")).quantize(Decimal("0.01"))
    ask = (mid + Decimal("0.05")).quantize(Decimal("0.01"))
    return ContractRecommendation(
        contract_type=ContractType.CALL_DEBIT,
        occ_symbol="ACME240101C00100000",
        expiry=expiry,
        strike=strike,
        bid=bid,
        mid=mid,
        ask=ask,
        spread_pct=((ask - bid) / mid * Decimal("100")).quantize(Decimal("0.01")),
        delta=Decimal("0.55"),
        open_interest=1200,
        volume=300,
    )


def _underlying_with_earnings_on(earn_d: date) -> UnderlyingView:
    return UnderlyingView(
        symbol="ACME",
        name=None,
        sector=None,
        stage_label=None,
        current_price=None,
        rs_mansfield_pct=None,
        perf_5d=None,
        td_buy_setup=None,
        td_sell_setup=None,
        next_earnings=datetime(earn_d.year, earn_d.month, earn_d.day, tzinfo=timezone.utc),
        days_to_earnings=None,
        atr_14=None,
        atrp_14=None,
        sma_21=None,
        volume_avg_20d=None,
    )


# ---------------------------------------------------------------------------
# Composer unit tests
# ---------------------------------------------------------------------------


def test_stage_2a_green_regime_produces_computed_sizing_and_contract(db_session):
    user = _user(db_session)
    _broker_account(db_session, user_id=user.id, total_value=Decimal("100000"))
    regime = _regime(db_session, code="R1")
    _snapshot(db_session, symbol="ACME", stage_label="2A")
    cand = _candidate(db_session, symbol="ACME")

    chain = _FakeChain(_contract_rec())
    composer = TradeCardComposer(options_surface=chain)

    card = composer.compose(db_session, candidate=cand, user=user, rank=1, regime=regime)

    assert card.contract_status is ContractStatus.READY
    assert card.contract is not None
    assert card.sizing_status is SizingStatus.COMPUTED
    assert card.sizing is not None
    assert card.sizing.contracts >= 1
    assert card.sizing.premium_dollars > Decimal("0")
    assert card.stops.underlying_stop is not None
    assert card.stops.premium_stop is not None
    assert len(card.limit_tiers) == 3
    passive, mid, aggressive = card.limit_tiers
    # Tiers must be monotonically increasing price-wise for a call debit.
    assert passive.price < mid.price < aggressive.price
    # Every tier must carry a non-empty reason.
    assert all(t.logic for t in card.limit_tiers)
    # No silent zeroes: risk budget = 1% of 100k.
    assert card.sizing.risk_budget == Decimal("1000.00")
    # Options surface was actually consulted.
    assert len(chain.calls) == 1

    # Serialization round-trip — API must not lose Decimals to float.
    payload = trade_card_to_payload(card)
    assert payload["sizing"]["contracts"] == card.sizing.contracts
    assert payload["contract"]["occ_symbol"] == "ACME240101C00100000"


def test_regime_r3_still_sizes_but_applies_smaller_stage_cap(db_session):
    """R3 keeps a 2A cap at 0.50. Sizing should be computed and smaller than R1's."""
    user = _user(db_session, email="r3trader@example.com")
    _broker_account(db_session, user_id=user.id, total_value=Decimal("100000"))
    regime_r1 = _regime(db_session, code="R1")
    regime_r3 = _regime(db_session, code="R3")
    _snapshot(db_session, symbol="ACME", stage_label="2A")
    cand = _candidate(db_session, symbol="ACME")

    chain = _FakeChain(_contract_rec())
    composer = TradeCardComposer(options_surface=chain)

    card_r1 = composer.compose(
        db_session, candidate=cand, user=user, rank=1, regime=regime_r1
    )
    card_r3 = composer.compose(
        db_session, candidate=cand, user=user, rank=1, regime=regime_r3
    )

    assert card_r1.sizing_status is SizingStatus.COMPUTED
    assert card_r3.sizing_status is SizingStatus.COMPUTED
    assert card_r3.sizing is not None and card_r1.sizing is not None
    # 2A cap is 0.75 in R1 vs 0.50 in R3 → capped_position_dollars shrinks.
    assert card_r3.sizing.capped_position_dollars < card_r1.sizing.capped_position_dollars
    # The R3 info alert fires when regime is R3.
    assert any(a.alert_type == "regime_shift" for a in card_r3.alerts)


def test_account_without_broker_surfaces_account_unknown_state(db_session):
    """Zero-connected-accounts case must not silently size to zero."""
    user = _user(db_session, email="noacct@example.com")
    regime = _regime(db_session, code="R1")
    _snapshot(db_session, symbol="ACME", stage_label="2A")
    cand = _candidate(db_session, symbol="ACME")

    composer = TradeCardComposer(options_surface=_FakeChain(_contract_rec()))
    card = composer.compose(db_session, candidate=cand, user=user, rank=1, regime=regime)

    assert card.sizing_status is SizingStatus.ACCOUNT_UNKNOWN
    assert card.sizing is None
    # The card still carries a contract so the user can plan manually.
    assert card.contract_status is ContractStatus.READY
    # An alert tells the user to connect a brokerage.
    assert any(a.alert_type == "account" for a in card.alerts)
    # Limit tiers are still populated so price anchors are visible.
    assert len(card.limit_tiers) == 3


def test_stage_4a_in_r4_yields_regime_blocked_sizing(db_session):
    """Distribution stage in a poor regime has a zero cap — the card is informational."""
    user = _user(db_session, email="blocked@example.com")
    _broker_account(db_session, user_id=user.id, total_value=Decimal("50000"))
    regime = _regime(db_session, code="R4")
    _snapshot(db_session, symbol="BAD", stage_label="4A", rs=12.0)
    cand = _candidate(db_session, symbol="BAD", pick_quality_score=8.0)

    composer = TradeCardComposer(options_surface=None)
    card = composer.compose(db_session, candidate=cand, user=user, rank=1, regime=regime)

    assert card.sizing_status is SizingStatus.REGIME_BLOCKED
    assert card.sizing is not None
    assert card.sizing.capped_position_dollars == Decimal("0.00")
    assert any(a.alert_type == "regime_blocked" and a.level.value == "critical" for a in card.alerts)
    # No options surface is wired — composer should surface the stock-only
    # status rather than pretending a chain was consulted.
    assert card.contract_status is ContractStatus.STOCK_ONLY


def test_earnings_window_skips_chain_one_day_before_expiry():
    """Earnings 1d before expiry lies in [expiry-2, expiry] — suppress chain."""
    exp = date(2026, 6, 10)
    c = _contract_rec(expiry=exp)
    u = _underlying_with_earnings_on(date(2026, 6, 9))
    assert _resolve_contract_status_for_earnings(u, c) == ContractStatus.SKIPPED_EARNINGS


def test_earnings_window_skips_chain_two_days_before_expiry():
    """Earnings on expiry-2 is inclusive — suppress chain."""
    exp = date(2026, 6, 10)
    c = _contract_rec(expiry=exp)
    u = _underlying_with_earnings_on(date(2026, 6, 8))
    assert _resolve_contract_status_for_earnings(u, c) == ContractStatus.SKIPPED_EARNINGS


def test_earnings_window_allows_chain_three_days_before_expiry():
    """Earnings before the 2-day pre-expiry window does not suppress chain."""
    exp = date(2026, 6, 10)
    c = _contract_rec(expiry=exp)
    u = _underlying_with_earnings_on(date(2026, 6, 7))
    assert _resolve_contract_status_for_earnings(u, c) is None


# ---------------------------------------------------------------------------
# Route tests (empty state must be distinct)
# ---------------------------------------------------------------------------


def _override_deps(db_session, user: User):
    def _get_db():
        try:
            yield db_session
        finally:
            pass

    def _get_user():
        return user

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_user


def test_trade_cards_today_empty_returns_zero_items(db_session):
    user = _user(db_session, email="empty@example.com")
    _override_deps(db_session, user)
    try:
        with TestClient(app) as client:
            resp = client.get("/api/v1/trade-cards/today")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["errors"] == []
        assert body["total"] == 0
        assert body["user_id"] == user.id
    finally:
        app.dependency_overrides.clear()


def test_trade_cards_today_returns_ranked_cards(db_session):
    user = _user(db_session, email="ranked@example.com")
    _broker_account(db_session, user_id=user.id, total_value=Decimal("100000"))
    _regime(db_session, code="R1")

    _snapshot(db_session, symbol="HIGH", stage_label="2A", current_price=100.0)
    _snapshot(db_session, symbol="LOW", stage_label="2B", current_price=80.0)
    _candidate(db_session, symbol="HIGH", pick_quality_score=82.0)
    _candidate(db_session, symbol="LOW", pick_quality_score=51.5)

    _override_deps(db_session, user)
    try:
        with TestClient(app) as client:
            resp = client.get("/api/v1/trade-cards/today")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert [c["underlying"]["symbol"] for c in body["items"]] == ["HIGH", "LOW"]
        assert [c["rank"] for c in body["items"]] == [1, 2]
        assert body["items"][0]["sizing_status"] == "computed"
    finally:
        app.dependency_overrides.clear()
