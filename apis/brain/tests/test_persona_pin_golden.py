"""Track G — structural regression on the 16-persona golden fixture.

We don't try to assert anything about generated text here. Instead we
check that every persona we route through n8n (via ``persona_pin``) is:

1. Registered in the PersonaSpec registry.
2. Stable across its declared contract (model, compliance flag, tools,
   cadence) so a spec change shows up as a failing test rather than a
   silent prod regression.
3. Covered end-to-end — adding a new persona without adding a scenario
   fails the coverage test, so docs-vs-code drift can't hide in Track G.

The regression layer is cheap to run nightly (see
``.github/workflows/brain-golden-suite.yaml``) and gets us a daily
"yes, our 16 employees still match their contracts" signal instead of
debugging in prod.

medallion: ops
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from app.personas import get_spec, list_specs


FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "persona_pin_scenarios.yaml"
)


def _load_scenarios() -> list[dict[str, Any]]:
    data = yaml.safe_load(FIXTURE_PATH.read_text())
    return data.get("scenarios", [])


SCENARIOS = _load_scenarios()


def _scenario_ids() -> list[str]:
    return [s["id"] for s in SCENARIOS]


def test_fixture_file_exists_and_parses():
    assert FIXTURE_PATH.exists(), f"missing fixture: {FIXTURE_PATH}"
    assert SCENARIOS, "persona_pin_scenarios.yaml has zero scenarios"


def test_every_registered_persona_has_a_scenario():
    """Coverage gate. Adding a persona without a fixture fails here."""
    registered = {spec.name for spec in list_specs()}
    covered = {s["persona"] for s in SCENARIOS}
    missing = registered - covered
    assert not missing, (
        f"Registered personas missing from golden fixture: {sorted(missing)}. "
        "Add a scenario in tests/fixtures/persona_pin_scenarios.yaml."
    )


def test_every_scenario_targets_a_real_persona():
    """Orphan gate. Fixtures must reference a registered PersonaSpec."""
    registered = {spec.name for spec in list_specs()}
    orphans = [s["persona"] for s in SCENARIOS if s["persona"] not in registered]
    assert not orphans, (
        f"Scenarios reference unknown personas: {orphans}. "
        "Either add the spec or remove the scenario."
    )


@pytest.mark.parametrize("scenario", SCENARIOS, ids=_scenario_ids())
def test_scenario_contract_matches_persona_spec(scenario: dict[str, Any]):
    """Golden assertion: fixture expectations must agree with the spec."""
    spec = get_spec(scenario["persona"])
    assert spec is not None, f"no spec for {scenario['persona']}"
    exp = scenario["expected"]

    if "default_model" in exp:
        assert spec.default_model == exp["default_model"], (
            f"{scenario['id']}: default_model drift — spec says "
            f"{spec.default_model!r}, fixture says {exp['default_model']!r}"
        )
    if "escalation_model" in exp:
        assert spec.escalation_model == exp["escalation_model"], (
            f"{scenario['id']}: escalation_model drift"
        )
    if "compliance_flagged" in exp:
        assert spec.compliance_flagged == exp["compliance_flagged"]
    if "requires_tools" in exp:
        assert spec.requires_tools == exp["requires_tools"]
    if "proactive_cadence" in exp:
        assert spec.proactive_cadence == exp["proactive_cadence"]
    if exp.get("has_ceiling"):
        assert spec.daily_cost_ceiling_usd is not None, (
            f"{scenario['id']}: expected a ceiling, spec has none"
        )
    if exp.get("has_rate_limit"):
        assert spec.requests_per_minute is not None, (
            f"{scenario['id']}: expected a rate limit, spec has none"
        )


@pytest.mark.parametrize("scenario", SCENARIOS, ids=_scenario_ids())
def test_scenario_message_is_non_empty(scenario: dict[str, Any]):
    """Defensive check — a scenario with no prompt is a silent no-op."""
    assert scenario.get("message", "").strip(), (
        f"{scenario['id']}: scenario message is empty"
    )


def test_all_personas_have_output_caps():
    """Track I: every persona in the registry must declare a max_output_tokens
    and requests_per_minute so the guardrails actually bite. This is a
    companion to the fixture scenarios above and catches drift if
    someone adds a new persona but forgets the caps.
    """
    missing: list[str] = []
    for spec in list_specs():
        if spec.max_output_tokens is None or spec.requests_per_minute is None:
            missing.append(spec.name)
    assert not missing, (
        f"Personas missing Track I caps (max_output_tokens or "
        f"requests_per_minute): {missing}"
    )
