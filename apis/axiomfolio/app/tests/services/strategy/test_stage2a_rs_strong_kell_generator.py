"""Tests for `Stage2ARsStrongKellGenerator` (quintile universe rank + SMA150 + volume + 52w)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.config import settings
from app.models.market_data import MarketSnapshot
from app.services.picks.generators.stage2a_rs_strong_kell import (
    Stage2ARsStrongKellGenerator,
)


def _snap(
    *,
    symbol: str,
    stage_label: str,
    rs: float,
    price: float = 100.0,
    sma150: float = 95.0,
    slope: float = 1.0,
    vol_ratio: float = 1.5,
    high_52w: float = 115.0,
) -> MarketSnapshot:
    now = datetime.now(timezone.utc)
    return MarketSnapshot(
        symbol=symbol,
        analysis_type="technical_snapshot",
        analysis_timestamp=now,
        as_of_timestamp=now,
        expiry_timestamp=now + timedelta(hours=24),
        is_valid=True,
        stage_label=stage_label,
        rs_mansfield_pct=rs,
        current_price=price,
        sma_150=sma150,
        sma150_slope=slope,
        vol_ratio=vol_ratio,
        high_52w=high_52w,
    )


def test_stage2a_kell_returns_only_matching_symbol(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ENABLE_STAGE2A_GENERATOR", True)

    # Universe RS order: -1, 12, 50, 100 → only 100 is top quintile (>= 80th pct).
    db_session.add(_snap(symbol="BAD_RS", stage_label="2A", rs=-1.0))
    db_session.add(_snap(symbol="BAD_RANK", stage_label="2A", rs=12.0))
    db_session.add(_snap(symbol="BAD_STAGE", stage_label="3A", rs=50.0))
    db_session.add(_snap(symbol="MATCH", stage_label="2A", rs=100.0))
    db_session.flush()

    gen = Stage2ARsStrongKellGenerator()
    out = list(gen.generate(db_session))

    assert [c.symbol for c in out] == ["MATCH"]


def test_stage2a_kell_score_breakdown_five_dimensions(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ENABLE_STAGE2A_GENERATOR", True)

    db_session.add(_snap(symbol="BAD_RS", stage_label="2A", rs=-1.0))
    db_session.add(_snap(symbol="BAD_RANK", stage_label="2A", rs=12.0))
    db_session.add(_snap(symbol="BAD_STAGE", stage_label="3A", rs=50.0))
    db_session.add(_snap(symbol="MATCH", stage_label="2A", rs=100.0))
    db_session.flush()

    gen = Stage2ARsStrongKellGenerator()
    out = list(gen.generate(db_session))
    assert len(out) == 1
    c = out[0]
    assert c.score == Decimal("100.0000")
    bd = c.signals.get("score_breakdown") or {}
    expected_keys = {
        "stage_substage",
        "rs_mansfield_and_rank",
        "sma150_anchor",
        "volume_ratio_20d",
        "distance_from_52w_high_pct",
    }
    assert set(bd.keys()) == expected_keys
    for k in expected_keys:
        assert Decimal(bd[k]) == Decimal("20")


def test_stage2a_kell_disabled_returns_empty(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ENABLE_STAGE2A_GENERATOR", False)

    db_session.add(_snap(symbol="MATCH", stage_label="2A", rs=100.0))
    db_session.flush()

    gen = Stage2ARsStrongKellGenerator()
    assert list(gen.generate(db_session)) == []
