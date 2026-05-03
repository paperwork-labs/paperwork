"""Loader / discovery tests — verify all canonical files load + validate.

Treats the canonical packages/data/src/* tree as a fixture: any state file
that fails Pydantic validation here would also fail Zod validation in the
TS engine (and vice versa, modulo the schema-drift CI guard).
"""

from __future__ import annotations

from data_engine import (
    StateCode,
    get_available_federal_years,
    get_available_tax_years,
    load_all_tax_states,
    load_federal,
    load_state_formation,
    load_state_tax,
    load_tax_year,
)
from data_engine.formation import get_all_formation_states
from data_engine.loader import get_data_dir


class TestTaxLoader:
    def test_data_dir_exists(self) -> None:
        path = get_data_dir()
        assert path.is_dir()
        assert (path / "tax").is_dir()
        assert (path / "formation").is_dir()
        assert (path / "federal").is_dir()

    def test_every_year_loads_completely(self) -> None:
        years = get_available_tax_years()
        assert len(years) > 0
        for year in years:
            states = load_tax_year(year)
            assert len(states) > 0, f"year {year} has no state files"
            for state, rules in states.items():
                assert rules.state == state
                assert rules.tax_year == year

    def test_load_state_tax_for_50_states(self) -> None:
        states = load_all_tax_states(2025)
        assert len(states) >= 50
        for state in states:
            rules = load_state_tax(state, 2025)
            assert rules.state == state


class TestFormationLoader:
    def test_every_formation_state_loads(self) -> None:
        states = get_all_formation_states()
        assert len(states) > 0
        for state in states:
            rules = load_state_formation(state)
            assert rules.state == state
            assert rules.entity_type == "LLC"
            assert rules.fees.standard.amount_cents >= 0


class TestFederalLoader:
    def test_2025_loads(self) -> None:
        rules = load_federal(2025)
        assert rules.tax_year == 2025
        assert len(rules.standard_deductions) >= 1
        assert len(rules.brackets) >= 1

    def test_year_discovery(self) -> None:
        years = get_available_federal_years()
        assert 2025 in years


class TestStateCodeCoverage:
    def test_state_codes_match_canonical_count(self) -> None:
        assert len(StateCode) == 51  # 50 + DC
