"""Unit tests for ``PickQualityScorer``."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.models.market_data import MarketRegime, MarketSnapshot
from app.services.gold.pick_quality_scorer import (
    PickQualityScorer,
    pick_quality_to_payload,
)


def _regime(db_session, *, code: str) -> MarketRegime:
    now = datetime.now(UTC).replace(tzinfo=None)
    row = MarketRegime(
        as_of_date=now,
        regime_state=code,
        composite_score=2.0,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _snapshot(
    db_session,
    *,
    symbol: str = "TEST",
    stage_label: str = "2A",
    rs: float | None = 85.0,
    regime_hint: str | None = None,
    next_earnings: datetime | None = None,
    td_buy: int | None = 8,
    td_sell: int | None = 0,
) -> MarketSnapshot:
    now = datetime.now(UTC)
    price = 125.50
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
        current_price=price,
        high_52w=130.0,
        atr_14=2.5,
        volume_avg_20d=500_000.0,
        td_buy_setup=td_buy,
        td_sell_setup=td_sell,
        next_earnings=next_earnings,
        regime_state=regime_hint,
    )
    db_session.add(row)
    db_session.flush()
    return row


def test_high_stage2a_strong_rs_r1_is_high_score(db_session):
    r = _regime(db_session, code="R1")
    _snapshot(db_session, stage_label="2A", rs=88.0)
    scorer = PickQualityScorer()
    out = scorer.score(db_session, "TEST", 101, regime_row=r)
    assert out.total_score > Decimal("55")
    assert out.regime_multiplier == Decimal("1.0")
    assert "stage" in out.components


def test_stage4_distribution_low_rs_is_low_score(db_session):
    r = _regime(db_session, code="R1")
    _snapshot(db_session, stage_label="4A", rs=15.0)
    scorer = PickQualityScorer()
    high = scorer.score(db_session, "TEST", 101, regime_row=r)
    _snapshot(db_session, symbol="GOOD", stage_label="2A", rs=88.0)
    good = scorer.score(db_session, "GOOD", 101, regime_row=r)
    assert high.total_score < good.total_score


def test_missing_rs_surfaces_reason_and_zero_weighted_rs(db_session):
    r = _regime(db_session, code="R1")
    _snapshot(db_session, symbol="WITHRS", rs=88.0)
    _snapshot(db_session, symbol="NORS", rs=None)
    scorer = PickQualityScorer()
    with_rs = scorer.score(db_session, "WITHRS", 101, regime_row=r)
    no_rs = scorer.score(db_session, "NORS", 102, regime_row=r)
    assert no_rs.components["rs"].reason == "RS data not available"
    assert no_rs.components["rs"].raw_score == Decimal("0")
    assert with_rs.total_score > no_rs.total_score


def test_regime_r5_forces_total_zero(db_session):
    r = _regime(db_session, code="R5")
    _snapshot(db_session, stage_label="2A", rs=95.0)
    scorer = PickQualityScorer()
    out = scorer.score(db_session, "TEST", 101, regime_row=r)
    assert out.regime_multiplier == Decimal("0")
    assert out.total_score == Decimal("0")


def test_earnings_in_three_days_penalizes_component(db_session):
    r = _regime(db_session, code="R1")
    ref = datetime.now(UTC)
    ne = ref + timedelta(days=3)
    _snapshot(db_session, next_earnings=ne)
    scorer = PickQualityScorer()
    out = scorer.score(db_session, "TEST", 101, regime_row=r)
    earn = out.components["earnings"]
    assert earn.raw_score < Decimal("40")


def test_cross_tenant_same_snapshot_same_score(db_session):
    r = _regime(db_session, code="R2")
    _snapshot(db_session)
    scorer = PickQualityScorer()
    a = scorer.score(db_session, "TEST", 5001, regime_row=r)
    b = scorer.score(db_session, "TEST", 5002, regime_row=r)
    assert a.total_score == b.total_score


def test_scoring_exception_returns_sanitized_reason(db_session):
    r = _regime(db_session, code="R1")
    snap = _snapshot(db_session)
    scorer = PickQualityScorer()

    def _boom(*args: object, **kwargs: object) -> object:
        raise ValueError("SECRET_INTERNAL_BOILERPLATE")

    scorer._score_stage = _boom  # type: ignore[method-assign]

    pq, outcome = scorer.score_with_counts(
        db_session,
        "TEST",
        101,
        regime_row=r,
        snapshot_row=snap,
        fetch_snapshot=False,
    )
    assert outcome == "errored"
    secret = "SECRET_INTERNAL_BOILERPLATE"
    for comp in pq.components.values():
        assert comp.reason == "scoring_error"
        assert secret not in comp.reason
    dumped = str(pick_quality_to_payload(pq))
    assert secret not in dumped
