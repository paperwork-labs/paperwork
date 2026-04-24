"""Tests for scan tier classification (long/short) and regime gates."""

from __future__ import annotations

import pytest

from backend.services.market.regime_engine import REGIME_R1, REGIME_R3, REGIME_R4, REGIME_R5
from backend.services.market.scan_engine import (
    TIER_BREAKDOWN_ELITE,
    TIER_BREAKOUT_ELITE,
    TIER_BREAKOUT_STANDARD,
    TIER_EARLY_BASE,
    ScanInput,
    classify_long_tier,
    classify_short_tier,
    classify_scan_tier,
    compute_forward_rr,
    check_correlation_constraint,
    compute_sector_confirmation,
    compute_sector_divergence_pct,
)

pytestmark = pytest.mark.no_db


def test_breakout_elite():
    inp = ScanInput(
        symbol="TEST",
        stage_label="2A",
        rs_mansfield=5.0,
        ema10_dist_n=1.5,
        atre_150_pctile=75.0,
        range_pos_52w=65.0,
        ext_pct=None,
        atrp_14=None,
    )
    assert classify_long_tier(inp, REGIME_R1) == TIER_BREAKOUT_ELITE


def test_breakout_standard():
    inp = ScanInput(
        symbol="TEST",
        stage_label="2B",
        rs_mansfield=-3.0,
        ema10_dist_n=2.5,
        atre_150_pctile=None,
        range_pos_52w=45.0,
        ext_pct=None,
        atrp_14=None,
    )
    assert classify_long_tier(inp, REGIME_R1) == TIER_BREAKOUT_STANDARD


def test_none_rs_skips_elite():
    inp = ScanInput(
        symbol="TEST",
        stage_label="2A",
        rs_mansfield=None,
        ema10_dist_n=1.5,
        atre_150_pctile=75.0,
        range_pos_52w=65.0,
        ext_pct=None,
        atrp_14=None,
    )
    assert classify_long_tier(inp, REGIME_R1) != TIER_BREAKOUT_ELITE


def test_none_rs_allows_early_base():
    inp = ScanInput(
        symbol="TEST",
        stage_label="2A",
        rs_mansfield=None,
        ema10_dist_n=1.5,
        atre_150_pctile=75.0,
        range_pos_52w=65.0,
        ext_pct=None,
        atrp_14=None,
    )
    assert classify_long_tier(inp, REGIME_R1) == TIER_EARLY_BASE


def test_breakdown_elite():
    inp = ScanInput(
        symbol="TEST",
        stage_label="4A",
        rs_mansfield=-5.0,
        ema10_dist_n=-1.5,
        atre_150_pctile=None,
        range_pos_52w=25.0,
        ext_pct=None,
        atrp_14=None,
    )
    assert classify_short_tier(inp, REGIME_R5) == TIER_BREAKDOWN_ELITE


def test_none_rs_skips_breakdown_elite():
    inp = ScanInput(
        symbol="TEST",
        stage_label="4A",
        rs_mansfield=None,
        ema10_dist_n=-1.5,
        atre_150_pctile=None,
        range_pos_52w=25.0,
        ext_pct=None,
        atrp_14=None,
    )
    assert classify_short_tier(inp, REGIME_R5) != TIER_BREAKDOWN_ELITE


def test_empty_universe_no_crash():
    for _inp in []:
        classify_long_tier(_inp, REGIME_R1)
    inp = ScanInput(
        symbol="",
        stage_label="UNKNOWN",
        rs_mansfield=None,
        ema10_dist_n=None,
        atre_150_pctile=None,
        range_pos_52w=None,
        ext_pct=None,
        atrp_14=None,
    )
    assert classify_long_tier(inp, REGIME_R1) is None
    assert classify_short_tier(inp, REGIME_R5) is None
    assert classify_scan_tier(inp, REGIME_R1) is None


def test_regime_gates_r5_blocks_longs():
    elite_inputs = ScanInput(
        symbol="TEST",
        stage_label="2A",
        rs_mansfield=5.0,
        ema10_dist_n=1.5,
        atre_150_pctile=75.0,
        range_pos_52w=65.0,
        ext_pct=None,
        atrp_14=None,
    )
    assert classify_long_tier(elite_inputs, REGIME_R5) is None


# ── Quad Sector Filter Tests ──


def test_avoid_sector_blocked_in_scan():
    inp = ScanInput(
        symbol="TEST",
        stage_label="2A",
        rs_mansfield=5.0,
        ema10_dist_n=1.5,
        atre_150_pctile=75.0,
        range_pos_52w=65.0,
        ext_pct=None,
        atrp_14=None,
        sector="Health Care",
    )
    assert classify_long_tier(inp, REGIME_R1, quad="Q1") is None


def test_scan_sector_allowed():
    inp = ScanInput(
        symbol="TEST",
        stage_label="2A",
        rs_mansfield=5.0,
        ema10_dist_n=1.5,
        atre_150_pctile=75.0,
        range_pos_52w=65.0,
        ext_pct=None,
        atrp_14=None,
        sector="Technology",
    )
    assert classify_long_tier(inp, REGIME_R1, quad="Q1") == TIER_BREAKOUT_ELITE


def test_unknown_sector_passes_through():
    inp = ScanInput(
        symbol="TEST",
        stage_label="2A",
        rs_mansfield=5.0,
        ema10_dist_n=1.5,
        atre_150_pctile=75.0,
        range_pos_52w=65.0,
        ext_pct=None,
        atrp_14=None,
        sector=None,
    )
    assert classify_long_tier(inp, REGIME_R1, quad="Q3") == TIER_BREAKOUT_ELITE


# ── Second-pass 2B prohibition ──


def test_second_pass_2b_blocked_in_r3():
    inp = ScanInput(
        symbol="TEST",
        stage_label="2B",
        rs_mansfield=5.0,
        ema10_dist_n=1.5,
        atre_150_pctile=75.0,
        range_pos_52w=65.0,
        ext_pct=None,
        atrp_14=None,
        pass_count=2,
    )
    assert classify_long_tier(inp, REGIME_R3) is None


def test_first_pass_2b_allowed_in_r3():
    inp = ScanInput(
        symbol="TEST",
        stage_label="2B",
        rs_mansfield=5.0,
        ema10_dist_n=1.5,
        atre_150_pctile=75.0,
        range_pos_52w=65.0,
        ext_pct=None,
        atrp_14=None,
        pass_count=1,
    )
    assert classify_long_tier(inp, REGIME_R3) == TIER_BREAKOUT_ELITE


def test_second_pass_2b_allowed_in_r1():
    inp = ScanInput(
        symbol="TEST",
        stage_label="2B",
        rs_mansfield=5.0,
        ema10_dist_n=1.5,
        atre_150_pctile=75.0,
        range_pos_52w=65.0,
        ext_pct=None,
        atrp_14=None,
        pass_count=2,
    )
    assert classify_long_tier(inp, REGIME_R1) == TIER_BREAKOUT_ELITE


# ── Forward R/R ──


def test_forward_rr_r1():
    rr = compute_forward_rr(close=100.0, atr_30=5.0, regime=REGIME_R1)
    assert rr is not None
    assert rr == pytest.approx(2.0)


def test_forward_rr_r3():
    rr = compute_forward_rr(close=100.0, atr_30=5.0, regime=REGIME_R3)
    assert rr is not None
    assert rr == pytest.approx(12.5 / 7.5, rel=0.01)


def test_forward_rr_with_explicit_stop():
    rr = compute_forward_rr(close=100.0, atr_30=5.0, stop=95.0, regime=REGIME_R1)
    assert rr is not None
    assert rr == pytest.approx(3.0)


def test_forward_rr_zero_risk():
    assert compute_forward_rr(close=100.0, atr_30=5.0, stop=100.0) is None


def test_forward_rr_invalid_inputs():
    assert compute_forward_rr(close=0, atr_30=5.0) is None
    assert compute_forward_rr(close=100, atr_30=0) is None


# ── Correlation Constraint ──


def test_correlation_under_limit():
    positions = [
        {"sub_industry": "Semiconductors"},
        {"sub_industry": "Semiconductors"},
        {"sub_industry": "Software"},
    ]
    assert check_correlation_constraint(positions, "Semiconductors") is True


def test_correlation_at_limit():
    positions = [
        {"sub_industry": "Semiconductors"},
        {"sub_industry": "Semiconductors"},
        {"sub_industry": "Semiconductors"},
    ]
    assert check_correlation_constraint(positions, "Semiconductors") is False


def test_correlation_none_sub_industry():
    positions = [{"sub_industry": "Semiconductors"}] * 5
    assert check_correlation_constraint(positions, None) is True


# ── Sector Confirmation ──


def test_sector_confirmation_stage_2():
    assert compute_sector_confirmation("2A") == "CONFIRMING"
    assert compute_sector_confirmation("2B") == "CONFIRMING"
    assert compute_sector_confirmation("2C") == "CONFIRMING"


def test_sector_confirmation_stage_1():
    assert compute_sector_confirmation("1A") == "NEUTRAL"
    assert compute_sector_confirmation("1B") == "NEUTRAL"


def test_sector_confirmation_stage_3_4():
    assert compute_sector_confirmation("3A") == "DENYING"
    assert compute_sector_confirmation("4B") == "DENYING"


def test_sector_divergence_pct():
    confirmations = {"XLK": "CONFIRMING", "XLE": "DENYING", "XLF": "DENYING"}
    pct = compute_sector_divergence_pct(confirmations)
    assert pct == pytest.approx(66.67, rel=0.01)


def test_sector_divergence_empty():
    assert compute_sector_divergence_pct({}) == 0.0
