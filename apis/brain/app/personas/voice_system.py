"""Persona voice configuration — anchors, cross-genre rules, synthesis routing (stub).

medallion: ops
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Final, Literal

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

COMPLIANCE_LEVEL_RANK: Final[dict[str, int]] = {
    "regulated_promotional": 0,
    "creative_free": 1,
    "standard": 2,
    "regulated_safe": 3,
}

ComplianceLevel = Literal[
    "regulated_promotional",
    "creative_free",
    "standard",
    "regulated_safe",
]

VOICE_SPECS_DIR = Path(__file__).resolve().parent / "voice_specs"


class VoiceAnchor(BaseModel):
    author: str
    source: str
    sample_count: int = 0


class CrossGenreRule(BaseModel):
    sources: list[str] = Field(default_factory=list)
    min_compliance_level: ComplianceLevel = "regulated_safe"


class VoiceConfig(BaseModel):
    mode: Literal["shadow", "active", "archived"] = "shadow"
    anchors: list[VoiceAnchor] = Field(default_factory=list)
    corpus_dir: str = ""
    cross_genre_pull_allowed: CrossGenreRule = Field(default_factory=CrossGenreRule)
    forbidden_phrases: list[str] = Field(default_factory=list)
    signature_moves: list[str] = Field(default_factory=list)
    platform_targets: list[str] = Field(default_factory=list)


class VoicePersona(BaseModel):
    slug: str
    voice: VoiceConfig


def _compliance_rank(level: str) -> int:
    return COMPLIANCE_LEVEL_RANK.get(level, -1)


def can_pull_pattern(
    source_persona: str,
    target: VoicePersona,
    pattern_compliance_level: str,
) -> tuple[bool, str]:
    """Check if a pattern from source can be used by target persona."""
    rule = target.voice.cross_genre_pull_allowed
    if rule.sources and source_persona not in rule.sources:
        return False, "source persona not in cross_genre_pull_allowed.sources"

    required = rule.min_compliance_level
    req_rank = _compliance_rank(required)
    if req_rank < 0:
        return False, f"unknown min_compliance_level: {required!r}"

    pat_rank = _compliance_rank(pattern_compliance_level)
    if pat_rank < 0:
        return False, f"unknown pattern_compliance_level: {pattern_compliance_level!r}"

    if pat_rank < req_rank:
        return (
            False,
            f"pattern compliance {pattern_compliance_level!r} below required {required!r}",
        )
    return True, "ok"


def synthesize_post_stub(persona: VoicePersona, brief: dict[str, object]) -> dict[str, Any]:
    """Stub for post synthesis — draft structure without LLM; mode-aware routing."""
    mode = persona.voice.mode
    if mode == "shadow":
        route = "conversation"
    elif mode == "active":
        route = "queue"
    else:
        route = "archived"

    return {
        "persona": persona.slug,
        "voice_mode": mode,
        "route": route,
        "brief_echo": brief,
        "draft": {
            "body": "",
            "hooks": [],
            "status": "stub",
        },
    }


def _safe_slug(raw: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_\-]", "", raw.lower())
    return cleaned or ""


@lru_cache(maxsize=64)
def get_voice_persona(slug: str) -> VoicePersona | None:
    """Load one voice persona from ``voice_specs/<slug>.yaml``."""
    safe = _safe_slug(slug)
    if not safe:
        return None
    path = VOICE_SPECS_DIR / f"{safe}.yaml"
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError:
        logger.exception("Invalid YAML in voice spec %s", path)
        return None
    try:
        return VoicePersona.model_validate(data)
    except (TypeError, ValueError) as exc:
        logger.warning("VoicePersona validation failed for %s: %s", path, exc)
        return None


def list_voice_personas() -> list[VoicePersona]:
    """All voice specs on disk."""
    out: list[VoicePersona] = []
    if not VOICE_SPECS_DIR.is_dir():
        return out
    for path in sorted(VOICE_SPECS_DIR.glob("*.yaml")):
        persona = get_voice_persona(path.stem)
        if persona is not None:
            out.append(persona)
    return out


__all__ = [
    "COMPLIANCE_LEVEL_RANK",
    "ComplianceLevel",
    "CrossGenreRule",
    "VoiceAnchor",
    "VoiceConfig",
    "VoicePersona",
    "can_pull_pattern",
    "get_voice_persona",
    "list_voice_personas",
    "synthesize_post_stub",
]
