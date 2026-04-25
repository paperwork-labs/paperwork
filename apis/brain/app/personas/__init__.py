"""Brain persona platform — typed contracts + registry + routing.

See docs/BRAIN_PERSONAS.md for design rationale and how to add a spec.

Public API:
    PersonaSpec          - Pydantic model for a single persona's contract.
    get_spec(persona)    - Load and cache a spec from specs/<persona>.yaml.
    list_specs()         - All specs known to the registry.
    resolve_model(...)   - Choose default vs escalation model per spec.
    route_persona(...)   - Heuristic keyword + channel + pin router.
"""
from app.personas.spec import PersonaSpec
from app.personas.registry import (
    get_spec,
    list_specs,
    resolve_model,
)
from app.personas.routing import (
    CHANNEL_BOOST,
    CHANNEL_PERSONA_MAP,
    PHRASE_KEYWORDS,
    SINGLE_WORD_KEYWORDS,
    route_persona,
)

__all__ = [
    "PersonaSpec",
    "get_spec",
    "list_specs",
    "resolve_model",
    "route_persona",
    "CHANNEL_BOOST",
    "CHANNEL_PERSONA_MAP",
    "PHRASE_KEYWORDS",
    "SINGLE_WORD_KEYWORDS",
]
