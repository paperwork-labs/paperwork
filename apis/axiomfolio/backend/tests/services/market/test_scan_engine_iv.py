"""Tests for the ``iv_rank_252`` scan-engine filter (G5).

The null-rank exclusion is the critical behaviour -- a ramping symbol
(no rank yet) must NOT pass through a ``iv_rank_252 < 20`` filter, which
would silently look like "cheap options" and hand off garbage candidates
to a premium-selling strategy.
"""

from __future__ import annotations

import pytest

from backend.services.market.scan_engine import (
    IV_RANK_OPS,
    ScanInput,
    apply_iv_rank_filter,
)

pytestmark = pytest.mark.no_db


def _row(symbol: str, iv_rank: float | None) -> ScanInput:
    return ScanInput(
        symbol=symbol,
        stage_label="Stage 2",
        rs_mansfield=None,
        ema10_dist_n=None,
        atre_150_pctile=None,
        range_pos_52w=None,
        ext_pct=None,
        atrp_14=None,
        iv_rank_252=iv_rank,
    )


def test_iv_rank_lt_20_excludes_null_rank() -> None:
    rows = [
        _row("LOW", 10.0),     # passes
        _row("MID", 50.0),     # filtered out
        _row("RAMP", None),    # EXCLUDED (ramping/no data)
        _row("HIGH", 95.0),    # filtered out
        _row("ZERO", 0.0),     # passes
    ]
    out = apply_iv_rank_filter(rows, op="lt", value=20.0)
    symbols = [r.symbol for r in out]
    # Neither the ramping row nor the rows >= 20 should make it through.
    assert symbols == ["LOW", "ZERO"]
    assert "RAMP" not in symbols


def test_iv_rank_operators_behave_as_expected() -> None:
    rows = [_row("A", 10.0), _row("B", 20.0), _row("C", 50.0), _row("D", 80.0)]
    assert [r.symbol for r in apply_iv_rank_filter(rows, "lte", 20)] == ["A", "B"]
    assert [r.symbol for r in apply_iv_rank_filter(rows, "gt", 20)] == ["C", "D"]
    assert [r.symbol for r in apply_iv_rank_filter(rows, "gte", 50)] == ["C", "D"]

    between = apply_iv_rank_filter(rows, "between", 20, value2=70)
    assert [r.symbol for r in between] == ["B", "C"]


def test_between_requires_value2() -> None:
    with pytest.raises(ValueError, match="value2"):
        apply_iv_rank_filter([_row("X", 30.0)], "between", 20)


def test_unknown_op_raises() -> None:
    with pytest.raises(ValueError, match="unknown iv_rank operator"):
        apply_iv_rank_filter([_row("X", 30.0)], "eq", 20)


def test_all_null_rank_universe_returns_empty() -> None:
    """When every symbol is in the warm-up window, ``iv_rank < X``
    matches nothing -- silent-zero would have matched everything, which
    is the failure mode this test pins."""
    rows = [_row("A", None), _row("B", None)]
    assert apply_iv_rank_filter(rows, "lt", 20) == []
    assert apply_iv_rank_filter(rows, "gt", 20) == []


def test_supported_ops_constant_stable() -> None:
    # Downstream UIs switch on this constant; pin to avoid silent drift.
    assert set(IV_RANK_OPS) == {"lt", "lte", "gt", "gte", "between"}
