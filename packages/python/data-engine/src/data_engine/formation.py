"""Python port of packages/data/src/engine/formation.ts."""

from __future__ import annotations

from data_engine.loader import (
    clear_all_caches as _clear_all_caches,
)
from data_engine.loader import (
    get_data_dir,
    load_state_formation,
)
from data_engine.schemas.common import StateCode
from data_engine.schemas.formation import FormationRules


def get_state_formation_rules(state: StateCode) -> FormationRules | None:
    try:
        return load_state_formation(state)
    except FileNotFoundError:
        return None


def get_all_formation_states() -> list[StateCode]:
    """Every state with a formation/{STATE}.json file on disk."""
    formation_dir = get_data_dir() / "formation"
    if not formation_dir.is_dir():
        return []
    out: list[StateCode] = []
    for path in sorted(formation_dir.iterdir()):
        if path.suffix != ".json" or path.name.startswith("_"):
            continue
        try:
            out.append(StateCode(path.stem))
        except ValueError:
            continue
    return out


def get_formation_fee(state: StateCode, expedited: bool = False) -> int | None:
    """Return cheapest fee in cents (standard, or expedited if requested + available)."""
    rules = get_state_formation_rules(state)
    if rules is None:
        return None
    if expedited and rules.fees.expedited is not None:
        return rules.fees.expedited.amount_cents
    return rules.fees.standard.amount_cents


def clear_formation_cache() -> None:
    _clear_all_caches()
