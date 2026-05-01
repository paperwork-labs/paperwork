"""Tests for the PersonaSpec registry (Phase D1)."""

from __future__ import annotations

import pytest
import yaml
from pydantic import ValidationError

from app.personas import PersonaSpec, get_spec, list_specs, resolve_model
from app.personas.registry import SPECS_DIR


def test_specs_directory_exists():
    assert SPECS_DIR.is_dir(), f"missing specs dir: {SPECS_DIR}"


def test_every_yaml_is_valid_persona_spec():
    """No spec should be silently dropped by the registry."""
    yaml_files = list(SPECS_DIR.glob("*.yaml"))
    assert yaml_files, "expected at least one persona spec"
    loaded = {spec.name for spec in list_specs()}
    disk = {path.stem for path in yaml_files}
    assert disk == loaded, f"specs failed to load: {disk - loaded}"


def test_spec_slugs_match_filenames():
    for path in SPECS_DIR.glob("*.yaml"):
        data = yaml.safe_load(path.read_text())
        assert data["name"] == path.stem, (
            f"spec name {data['name']!r} does not match filename {path.stem!r}"
        )


def test_compliance_flagged_personas_have_confidence_floor():
    for spec in list_specs():
        if spec.compliance_flagged:
            assert spec.confidence_floor is not None, (
                f"{spec.name} is compliance_flagged but has no confidence_floor"
            )
            assert spec.confidence_floor >= 0.75


def test_get_spec_missing_returns_none():
    assert get_spec("this-persona-does-not-exist") is None


def test_get_spec_handles_bad_input():
    with pytest.raises(ValueError, match="invalid persona slug"):
        get_spec("")
    with pytest.raises(ValueError, match="invalid persona slug"):
        get_spec("../../etc/passwd")


def test_escalate_if_rejects_unknown_tags():
    with pytest.raises(ValueError):
        PersonaSpec(
            name="x",
            description="y",
            default_model="gpt-4o-mini",
            escalate_if=["random-unknown"],
        )


def test_resolve_model_no_escalation_stays_on_default():
    spec = PersonaSpec(
        name="x",
        description="y",
        default_model="gpt-4o-mini",
    )
    model, escalated = resolve_model(spec)
    assert model == "gpt-4o-mini"
    assert escalated is False


def test_resolve_model_rejects_deprecated_tools_required_tag():
    """tools_required was removed; requires_tools is now a first-class field."""
    with pytest.raises(ValidationError):
        PersonaSpec(
            name="x",
            description="y",
            default_model="gpt-4o-mini",
            escalation_model="claude-sonnet-4-20250514",
            escalate_if=["tools_required"],
        )


def test_requires_tools_field_defaults_false():
    spec = PersonaSpec(
        name="x",
        description="y",
        default_model="gpt-4o-mini",
    )
    assert spec.requires_tools is False


def test_requires_tools_field_is_honored():
    spec = PersonaSpec(
        name="x",
        description="y",
        default_model="gpt-4o-mini",
        requires_tools=True,
    )
    assert spec.requires_tools is True


def test_resolve_model_escalates_on_token_threshold():
    spec = PersonaSpec(
        name="x",
        description="y",
        default_model="gpt-4o-mini",
        escalation_model="claude-sonnet-4-20250514",
        escalate_if=["tokens>4000"],
    )
    model, _ = resolve_model(spec, input_tokens=100)
    assert model == "gpt-4o-mini"
    model, _ = resolve_model(spec, input_tokens=10000)
    assert model == "claude-sonnet-4-20250514"


def test_resolve_model_escalates_on_mention():
    spec = PersonaSpec(
        name="x",
        description="y",
        default_model="gpt-4o-mini",
        escalation_model="claude-sonnet-4-20250514",
        escalate_if=["mention:quarterly"],
    )
    model, _ = resolve_model(spec, message="tell me about Quarterly planning")
    assert model == "claude-sonnet-4-20250514"
    model, _ = resolve_model(spec, message="what's for lunch")
    assert model == "gpt-4o-mini"


def test_compliance_personas_escalate_when_flagged():
    """Compliance-flagged personas should escalate when escalate_if includes
    'compliance'."""
    spec = PersonaSpec(
        name="x",
        description="y",
        default_model="gpt-4o-mini",
        escalation_model="claude-sonnet-4-20250514",
        escalate_if=["compliance"],
        compliance_flagged=True,
    )
    model, escalated = resolve_model(spec)
    assert model == "claude-sonnet-4-20250514"
    assert escalated is True


def test_known_personas_loaded():
    """Sanity check: the personas we rely on at runtime all have specs."""
    names = {spec.name for spec in list_specs()}
    for required in {"ea", "engineering", "cpa", "tax-domain", "legal", "qa", "brand", "infra-ops"}:
        assert required in names, f"missing persona spec for {required}"


def test_every_persona_spec_has_tone_prefix():
    """Track C: every employee has a distinct voice."""
    for spec in list_specs():
        assert spec.tone_prefix, f"{spec.name} is missing tone_prefix"
        assert len(spec.tone_prefix) > 20, f"{spec.name} tone_prefix is too short"


def test_proactive_cadence_valid_values():
    for spec in list_specs():
        assert spec.proactive_cadence in {"never", "daily", "weekly", "monthly"}


def test_at_least_one_daily_cadence():
    """Sanity check so we don't accidentally ship all 'never'."""
    cadences = {spec.proactive_cadence for spec in list_specs()}
    assert "daily" in cadences
