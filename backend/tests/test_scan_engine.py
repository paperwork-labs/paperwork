"""Tests for scan tier classification (long/short) and regime gates."""

from __future__ import annotations

import pytest

from backend.services.market.regime_engine import REGIME_R1, REGIME_R5
from backend.services.market.scan_engine import (
    TIER_BREAKDOWN_ELITE,
    TIER_BREAKOUT_ELITE,
    TIER_BREAKOUT_STANDARD,
    TIER_EARLY_BASE,
    ScanInput,
    classify_long_tier,
    classify_short_tier,
    classify_scan_tier,
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
