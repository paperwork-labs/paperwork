"""Tests for the Quad Engine — Hedgeye GIP Quad Model classification."""

import pytest

from app.services.silver.regime.quad_engine import (
    QuadConcentrationLimits,
    QuadState,
    classify_quad,
    compute_depth,
    compute_quad_state,
    get_concentration_limits,
    get_sector_action,
    get_scan_sectors,
    check_t10_trigger,
    compute_binding_ceiling,
    DEFENSIVE_SECTORS,
)


# ── classify_quad ──


class TestClassifyQuad:
    def test_q1_goldilocks(self):
        assert classify_quad(gdp_first_diff=0.5, cpi_first_diff=-0.3) == "Q1"

    def test_q2_reflation(self):
        assert classify_quad(gdp_first_diff=0.5, cpi_first_diff=0.3) == "Q2"

    def test_q3_stagflation(self):
        assert classify_quad(gdp_first_diff=-0.5, cpi_first_diff=0.3) == "Q3"

    def test_q4_deflation(self):
        assert classify_quad(gdp_first_diff=-0.5, cpi_first_diff=-0.3) == "Q4"

    def test_zero_gdp_is_not_growth_up(self):
        assert classify_quad(gdp_first_diff=0.0, cpi_first_diff=-0.1) == "Q4"

    def test_zero_cpi_is_not_inflation_up(self):
        assert classify_quad(gdp_first_diff=0.1, cpi_first_diff=0.0) == "Q1"

    def test_both_zero(self):
        assert classify_quad(gdp_first_diff=0.0, cpi_first_diff=0.0) == "Q4"


# ── compute_depth ──


class TestComputeDepth:
    def test_deep_gdp(self):
        assert compute_depth(gdp_first_diff=0.5, cpi_first_diff=0.1) == "Deep"

    def test_deep_cpi(self):
        assert compute_depth(gdp_first_diff=0.1, cpi_first_diff=-0.5) == "Deep"

    def test_shallow(self):
        assert compute_depth(gdp_first_diff=0.2, cpi_first_diff=0.1) == "Shallow"

    def test_boundary_exactly_30bps(self):
        assert compute_depth(gdp_first_diff=0.30, cpi_first_diff=0.0) == "Shallow"

    def test_boundary_just_above(self):
        assert compute_depth(gdp_first_diff=0.31, cpi_first_diff=0.0) == "Deep"


# ── compute_quad_state ──


class TestComputeQuadState:
    def test_no_divergence(self):
        state = compute_quad_state(
            gdp_first_diff_quarterly=0.5, cpi_first_diff_quarterly=-0.3,
            gdp_first_diff_monthly=0.4, cpi_first_diff_monthly=-0.2,
        )
        assert state.quarterly_quad == "Q1"
        assert state.monthly_quad == "Q1"
        assert state.operative_quad == "Q1"
        assert state.divergence_flag is False
        assert state.divergence_months == 0

    def test_divergence_first_month(self):
        state = compute_quad_state(
            gdp_first_diff_quarterly=0.5, cpi_first_diff_quarterly=-0.3,
            gdp_first_diff_monthly=-0.2, cpi_first_diff_monthly=0.3,
            prior_divergence_months=0,
        )
        assert state.quarterly_quad == "Q1"
        assert state.monthly_quad == "Q3"
        assert state.divergence_flag is True
        assert state.divergence_months == 1
        assert state.operative_quad == "Q1"

    def test_divergence_two_months_monthly_becomes_operative(self):
        state = compute_quad_state(
            gdp_first_diff_quarterly=0.5, cpi_first_diff_quarterly=-0.3,
            gdp_first_diff_monthly=-0.2, cpi_first_diff_monthly=0.3,
            prior_divergence_months=1,
        )
        assert state.divergence_months == 2
        assert state.operative_quad == "Q3"

    def test_divergence_resets_on_convergence(self):
        state = compute_quad_state(
            gdp_first_diff_quarterly=0.5, cpi_first_diff_quarterly=-0.3,
            gdp_first_diff_monthly=0.3, cpi_first_diff_monthly=-0.1,
            prior_divergence_months=3,
        )
        assert state.divergence_flag is False
        assert state.divergence_months == 0
        assert state.operative_quad == "Q1"

    def test_depth_computation(self):
        state = compute_quad_state(
            gdp_first_diff_quarterly=0.5, cpi_first_diff_quarterly=-0.1,
            gdp_first_diff_monthly=0.1, cpi_first_diff_monthly=-0.05,
        )
        assert state.quarterly_depth == "Deep"
        assert state.monthly_depth == "Shallow"


# ── get_concentration_limits ──


class TestConcentrationLimits:
    def test_q1_deep(self):
        lim = get_concentration_limits("Q1", "Deep")
        assert lim.max_equity_pct == 100
        assert lim.min_cash_floor_pct == 0
        assert lim.max_single_position_pct == 8

    def test_q3_deep(self):
        lim = get_concentration_limits("Q3", "Deep")
        assert lim.max_equity_pct == 40
        assert lim.min_cash_floor_pct == 50

    def test_q4_deep(self):
        lim = get_concentration_limits("Q4", "Deep")
        assert lim.max_equity_pct == 20
        assert lim.min_cash_floor_pct == 80

    def test_shallow_reduces_equity_by_25(self):
        lim = get_concentration_limits("Q1", "Shallow")
        assert lim.max_equity_pct == 75.0

    def test_shallow_does_not_change_other_limits(self):
        lim = get_concentration_limits("Q2", "Shallow")
        assert lim.max_single_sector_pct == 25
        assert lim.max_single_position_pct == 6

    def test_unknown_quad_defaults_to_q4(self):
        lim = get_concentration_limits("QX", "Deep")
        assert lim.max_equity_pct == 20


# ── get_sector_action ──


class TestSectorAction:
    def test_tech_q1_r1(self):
        assert get_sector_action("Technology", "Q1", "R1") == "SCAN"

    def test_tech_q3_r1(self):
        assert get_sector_action("Technology", "Q3", "R1") == "WATCH"

    def test_tech_q4_r1(self):
        assert get_sector_action("Technology", "Q4", "R1") == "AVOID"

    def test_r3_filters_to_scan_or_watch_only(self):
        assert get_sector_action("Technology", "Q3", "R3") == "WATCH"
        assert get_sector_action("Consumer Disc.", "Q3", "R3") == "AVOID"
        assert get_sector_action("Energy", "Q3", "R3") == "SCAN"

    def test_r4_only_defensive(self):
        assert get_sector_action("Health Care", "Q1", "R4") == "WATCH"
        assert get_sector_action("Technology", "Q1", "R4") == "AVOID"
        assert get_sector_action("Utilities", "Q3", "R4") == "WATCH"

    def test_r5_only_defensive(self):
        assert get_sector_action("Gold", "Q4", "R5") == "WATCH"
        assert get_sector_action("Industrials", "Q1", "R5") == "AVOID"

    def test_unknown_sector(self):
        assert get_sector_action("Crypto", "Q1", "R1") == "AVOID"

    def test_defense_always_scan_in_r1(self):
        assert get_sector_action("Defense/Aero", "Q1", "R1") == "SCAN"
        assert get_sector_action("Defense/Aero", "Q4", "R1") == "SCAN"


# ── get_scan_sectors ──


class TestScanSectors:
    def test_q1_r1_has_many_scan_sectors(self):
        sectors = get_scan_sectors("Q1", "R1")
        assert "Technology" in sectors
        assert "Industrials" in sectors
        assert "Health Care" not in sectors

    def test_q3_r3_restricted(self):
        sectors = get_scan_sectors("Q3", "R3")
        assert "Energy" in sectors
        assert "Technology" not in sectors


# ── check_t10_trigger ──


class TestT10Trigger:
    def test_no_change(self):
        assert check_t10_trigger("Q1", "Q1") is False

    def test_q1_to_q3_triggers(self):
        assert check_t10_trigger("Q1", "Q3") is True

    def test_q2_to_q4_triggers(self):
        assert check_t10_trigger("Q2", "Q4") is True

    def test_q3_to_q1_does_not_trigger(self):
        assert check_t10_trigger("Q3", "Q1") is False

    def test_q1_to_q2_does_not_trigger(self):
        assert check_t10_trigger("Q1", "Q2") is False


# ── compute_binding_ceiling ──


class TestBindingCeiling:
    def test_regime_is_tighter(self):
        assert compute_binding_ceiling(30, 40) == 30

    def test_quad_is_tighter(self):
        assert compute_binding_ceiling(90, 40) == 40

    def test_equal(self):
        assert compute_binding_ceiling(50, 50) == 50
