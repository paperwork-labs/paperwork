"""Tests for :mod:`app.services.gold.signals.external_aggregator`."""

from __future__ import annotations

from datetime import UTC, date, timedelta
from decimal import Decimal

from app.models.external_signal import ExternalSignal
from app.services.gold.signals.external_aggregator import (
    external_context_bonus_points_map,
    fetch_finviz_signals,
    fetch_zacks_signals,
    persist_signals,
)


def test_fetch_stubs_return_empty() -> None:
    assert fetch_finviz_signals(["AAPL", "X"]) == []
    assert fetch_zacks_signals(["AAPL", "X"]) == []


def test_persist_empty_is_noop(db_session) -> None:
    n = persist_signals(db_session, [])
    assert n == 0
    db_session.commit()
    c = (
        db_session.query(ExternalSignal)
        .count()
    )
    assert c == 0


def test_persist_upsert_dedupes_unique_key(db_session) -> None:
    d = date(2025, 1, 2)
    row1 = {
        "symbol": "AAPL",
        "source": "finviz",
        "signal_date": d,
        "signal_type": "analyst_upgrade",
        "value": Decimal("1.0"),
        "raw_payload": {"x": 1},
    }
    n1 = persist_signals(db_session, [row1])
    assert n1 == 1
    db_session.commit()
    n2 = persist_signals(
        db_session,
        [
            {
                **row1,
                "value": Decimal("2.0"),
                "raw_payload": {"x": 2},
            }
        ],
    )
    assert n2 == 1
    db_session.commit()
    c = (
        db_session.query(ExternalSignal)
        .filter(ExternalSignal.symbol == "AAPL")
        .count()
    )
    assert c == 1
    r = (
        db_session.query(ExternalSignal)
        .filter(ExternalSignal.symbol == "AAPL")
        .one()
    )
    assert r.value == Decimal("2.0")
    assert r.raw_payload == {"x": 2}


def test_persist_normalizes_source_and_signal_type_casing(db_session) -> None:
    d = date(2025, 2, 1)
    n1 = persist_signals(
        db_session,
        [
            {
                "symbol": "AAPL",
                "source": "FinViz",
                "signal_date": d,
                "signal_type": "X_Y",
                "value": None,
                "raw_payload": {},
            }
        ],
    )
    assert n1 == 1
    db_session.commit()
    n2 = persist_signals(
        db_session,
        [
            {
                "symbol": "AAPL",
                "source": "finviz",
                "signal_date": d,
                "signal_type": "x_y",
                "value": Decimal("1"),
                "raw_payload": {"u": 1},
            }
        ],
    )
    assert n2 == 1
    c = (
        db_session.query(ExternalSignal)
        .filter(ExternalSignal.symbol == "AAPL")
        .count()
    )
    assert c == 1


def test_external_context_bonus_points_map_aggregates(monkeypatch, db_session) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "ENABLE_EXTERNAL_SIGNALS", True, raising=False)
    t0 = datetime.now(UTC).date()
    d = t0 - timedelta(days=1)
    db_session.add(
        ExternalSignal(
            symbol="AAPL",
            source="a",
            signal_date=d,
            signal_type="s",
            value=None,
            raw_payload={},
        )
    )
    db_session.add(
        ExternalSignal(
            symbol="AAPL",
            source="b",
            signal_date=d,
            signal_type="t",
            value=None,
            raw_payload={},
        )
    )
    db_session.add(
        ExternalSignal(
            symbol="X",
            source="a",
            signal_date=d,
            signal_type="s",
            value=None,
            raw_payload={},
        )
    )
    db_session.commit()
    m = external_context_bonus_points_map(db_session, ["AAPL", "X", "AAPL"])
    assert m["AAPL"] == min(Decimal("2"), Decimal("2") * Decimal("0.4"))
    assert m["X"] == min(Decimal("2"), Decimal("0.4"))
