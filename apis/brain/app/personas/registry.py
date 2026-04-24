"""Persona spec registry — loads YAML specs from app/personas/specs/ and
caches them in-process. Missing specs return None so callers can fall
back to legacy behavior without errors.

The registry is intentionally in-memory-only for now. The full design
(Phase D3 — governance table in Neon) will back this with a database
query that Studio can edit via /admin/agents. Until that ships, YAML-
on-disk is the source of truth.
"""
from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path

import yaml

from app.personas.spec import PersonaSpec

logger = logging.getLogger(__name__)

SPECS_DIR = Path(__file__).resolve().parent / "specs"


@lru_cache(maxsize=128)
def get_spec(persona: str) -> PersonaSpec | None:
    """Return the spec for a persona slug, or None if no spec exists."""
    safe = re.sub(r"[^a-z0-9_\-]", "", persona.lower())
    if not safe:
        return None
    path = SPECS_DIR / f"{safe}.yaml"
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError:
        logger.exception("Invalid YAML in persona spec %s", path)
        return None
    try:
        return PersonaSpec(**data)
    except (TypeError, ValueError) as exc:
        logger.warning("PersonaSpec for %s failed validation: %s", persona, exc)
        return None


def list_specs() -> list[PersonaSpec]:
    """All valid specs on disk. Used by Studio /admin/agents and smoke tests."""
    out: list[PersonaSpec] = []
    if not SPECS_DIR.is_dir():
        return out
    for path in sorted(SPECS_DIR.glob("*.yaml")):
        spec = get_spec(path.stem)
        if spec is not None:
            out.append(spec)
    return out


def resolve_model(
    spec: PersonaSpec,
    *,
    tools_required: bool = False,
    input_tokens: int = 0,
    message: str = "",
) -> tuple[str, bool]:
    """Pick (model, escalated) for a request.

    Evaluates spec.escalate_if in order. Returns early on first match.
    """
    if spec.escalation_model is None:
        return spec.default_model, False

    for tag in spec.escalate_if:
        if tag == "tools_required" and tools_required:
            return spec.escalation_model, True
        if tag == "compliance" and spec.compliance_flagged:
            return spec.escalation_model, True
        if tag.startswith("tokens>"):
            try:
                threshold = int(tag.split(">", 1)[1])
            except ValueError:
                continue
            if input_tokens > threshold:
                return spec.escalation_model, True
        if tag.startswith("mention:"):
            target = tag.split(":", 1)[1].lower()
            if target and target in message.lower():
                return spec.escalation_model, True

    return spec.default_model, False
