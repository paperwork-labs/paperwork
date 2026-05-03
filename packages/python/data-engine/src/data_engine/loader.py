"""File-discovery + caching loader for canonical packages/data JSON.

Mirrors packages/data/src/engine/loader.ts — same directory layout
(`tax/{year}/{STATE}.json`, `formation/{STATE}.json`, `portals/{state}.json`),
plus the new `federal/{year}.json` introduced by Wave K3.

Resolution order for the data root:
  1. PAPERWORK_DATA_DIR env var (must point at `packages/data/src`)
  2. Walk up from this file's location until a directory containing
     `packages/data/src/` is found (works in dev, tests, editable installs)

Caches are per-process and cleared via clear_*_cache() helpers (test only).
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from data_engine.schemas.common import StateCode
from data_engine.schemas.federal import FederalTaxRules
from data_engine.schemas.formation import FormationRules
from data_engine.schemas.tax import StateTaxRules

DATA_DIR_ENV_VAR = "PAPERWORK_DATA_DIR"


class DataDirNotFoundError(RuntimeError):
    """Raised when the canonical packages/data/src directory cannot be located."""


def _resolve_data_dir() -> Path:
    env = os.environ.get(DATA_DIR_ENV_VAR)
    if env:
        env_path = Path(env).resolve()
        if not env_path.is_dir():
            raise DataDirNotFoundError(
                f"{DATA_DIR_ENV_VAR}={env!r} but that directory does not exist"
            )
        return env_path

    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        candidate = parent / "packages" / "data" / "src"
        if candidate.is_dir():
            return candidate

    raise DataDirNotFoundError(
        "Could not locate packages/data/src by walking up from "
        f"{here}. Set {DATA_DIR_ENV_VAR} to override."
    )


@lru_cache(maxsize=1)
def get_data_dir() -> Path:
    """Cached canonical packages/data/src path."""
    return _resolve_data_dir()


_state_tax_rules_adapter = TypeAdapter(StateTaxRules)
_formation_rules_adapter = TypeAdapter(FormationRules)
_federal_tax_rules_adapter = TypeAdapter(FederalTaxRules)


_tax_year_cache: dict[int, dict[StateCode, StateTaxRules]] = {}
_formation_cache: dict[StateCode, FormationRules] = {}
_portal_cache: dict[StateCode, dict[str, Any]] = {}
_federal_cache: dict[int, FederalTaxRules] = {}


def load_tax_year(year: int) -> dict[StateCode, StateTaxRules]:
    """Load + validate every state file under tax/{year}/. Cached per year."""
    if year in _tax_year_cache:
        return _tax_year_cache[year]

    year_dir = get_data_dir() / "tax" / str(year)
    if not year_dir.is_dir():
        raise FileNotFoundError(f"Tax year directory not found: {year_dir}")

    out: dict[StateCode, StateTaxRules] = {}
    for path in sorted(year_dir.iterdir()):
        if path.suffix != ".json" or path.name.startswith("_"):
            continue
        expected_state = path.stem
        with path.open(encoding="utf-8") as fh:
            raw = json.load(fh)
        rules = _state_tax_rules_adapter.validate_python(raw)
        if rules.state.value != expected_state:
            raise ValueError(
                f"State mismatch in {path}: filename={expected_state}, data={rules.state.value}"
            )
        if rules.tax_year != year:
            raise ValueError(
                f"tax_year mismatch in {path}: dir={year}, data={rules.tax_year}"
            )
        out[rules.state] = rules

    _tax_year_cache[year] = out
    return out


def load_state_tax(state: StateCode, year: int) -> StateTaxRules:
    """Load a single state for a given year. Loads the whole year + caches."""
    rules = load_tax_year(year).get(state)
    if rules is None:
        raise FileNotFoundError(
            f"No tax data for state={state.value} year={year} "
            f"(checked {get_data_dir() / 'tax' / str(year) / f'{state.value}.json'})"
        )
    return rules


def load_state_formation(state: StateCode) -> FormationRules:
    """Load + cache a single formation file."""
    if state in _formation_cache:
        return _formation_cache[state]

    path = get_data_dir() / "formation" / f"{state.value}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Formation data not found: {path}")
    with path.open(encoding="utf-8") as fh:
        raw = json.load(fh)
    rules = _formation_rules_adapter.validate_python(raw)
    if rules.state != state:
        raise ValueError(
            f"State mismatch in {path}: filename={state.value}, data={rules.state.value}"
        )

    _formation_cache[state] = rules
    return rules


def load_state_portal(state: StateCode) -> dict[str, Any]:
    """Load a portal config (loose schema for now — Pydantic mirror is TODO)."""
    if state in _portal_cache:
        return _portal_cache[state]

    path = get_data_dir() / "portals" / f"{state.value.lower()}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Portal data not found: {path}")
    with path.open(encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)

    _portal_cache[state] = data
    return data


def load_federal(year: int) -> FederalTaxRules:
    """Load + validate the federal bracket file. Cached per year."""
    if year in _federal_cache:
        return _federal_cache[year]

    path = get_data_dir() / "federal" / f"{year}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Federal data not found: {path}")
    with path.open(encoding="utf-8") as fh:
        raw = json.load(fh)
    rules = _federal_tax_rules_adapter.validate_python(raw)
    if rules.tax_year != year:
        raise ValueError(
            f"tax_year mismatch in {path}: filename={year}, data={rules.tax_year}"
        )

    _federal_cache[year] = rules
    return rules


def load_all_tax_states(year: int) -> list[StateCode]:
    return sorted(load_tax_year(year).keys())


def get_available_tax_years() -> list[int]:
    """Discover tax/{NNNN}/ year directories on disk. Not cached (cheap)."""
    tax_root = get_data_dir() / "tax"
    if not tax_root.is_dir():
        return []
    years: list[int] = []
    for entry in tax_root.iterdir():
        if entry.is_dir() and entry.name.isdigit() and len(entry.name) == 4:
            years.append(int(entry.name))
    return sorted(years)


def get_available_federal_years() -> list[int]:
    federal_root = get_data_dir() / "federal"
    if not federal_root.is_dir():
        return []
    years: list[int] = []
    for entry in federal_root.iterdir():
        if entry.suffix != ".json":
            continue
        stem = entry.stem
        if stem.isdigit() and len(stem) == 4:
            years.append(int(stem))
    return sorted(years)


def clear_all_caches() -> None:
    """Test/dev helper. Do not call in prod hot paths."""
    _tax_year_cache.clear()
    _formation_cache.clear()
    _portal_cache.clear()
    _federal_cache.clear()
    get_data_dir.cache_clear()
