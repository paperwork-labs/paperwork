"""Persona voice configuration, cross-genre pull policy, and synthesis stub.

Medallion layer: operational policy + routing scaffolding (no external LLM).

medallion: ops
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from app.personas.pattern_classifier import pattern_contains_regulated_content

logger = logging.getLogger(__name__)

VOICE_SPECS_DIR = Path(__file__).resolve().parent / "voice_specs"

# Higher rank = stricter / more compliance-heavy pattern tier.
_COMPLIANCE_RANK: dict[str, int] = {
    "creative_open": 0,
    "regulated_safe": 1,
    "restricted_financial": 2,
}

# Explicitly blocklisted compliance labels (e.g. output of a future classifier).
_NONCOMPLIANT_LEVELS = frozenset({"regulated_claim", "noncompliant", "forbidden"})


class VoiceAnchor(BaseModel):
    author: str
    source: str
    sample_count: int = 0


class CrossGenreRule(BaseModel):
    sources: list[str] = Field(default_factory=list)
    min_compliance_level: str = "regulated_safe"


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


def _compliance_rank(level: str) -> int | None:
    return _COMPLIANCE_RANK.get(level.strip().lower())


def can_pull_pattern(
    source_persona: str,
    target: VoicePersona,
    pattern_compliance_level: str,
    *,
    pattern_text: str | None = None,
) -> tuple[bool, str]:
    """Check if a pattern from *source_persona* may be reused by *target*."""
    if pattern_text:
        blocked, reason = pattern_contains_regulated_content(pattern_text)
        if blocked:
            return False, f"regulated_content:{reason}"

    pcl = pattern_compliance_level.strip().lower()
    if pcl in _NONCOMPLIANT_LEVELS:
        return False, "pattern_marked_noncompliant"

    required = target.voice.cross_genre_pull_allowed.min_compliance_level.strip().lower()
    req_rank = _compliance_rank(required)
    pat_rank = _compliance_rank(pcl)
    if req_rank is None:
        return False, "unknown_target_min_compliance_level"
    if pat_rank is None:
        return False, "unknown_pattern_compliance_level"
    if pat_rank < req_rank:
        return False, "pattern_below_min_compliance"

    src = source_persona.strip().lower()
    tgt = target.slug.strip().lower()
    if src != tgt:
        allowed = [s.strip().lower() for s in target.voice.cross_genre_pull_allowed.sources]
        if not allowed:
            return False, "cross_genre_pull_disabled"
        if src not in allowed:
            return False, "source_not_in_cross_genre_allowlist"

    return True, "ok"


def synthesize_post_stub(persona: VoicePersona, brief: dict[str, Any]) -> dict[str, Any]:
    """Stub post synthesis — draft envelope only (no LLM).

    Routing:
      shadow → conversation review path
      active → publishing queue path
      archived → archived (no active pipeline)
    """
    mode = persona.voice.mode
    if mode == "shadow":
        destination = "conversation"
    elif mode == "active":
        destination = "queue"
    else:
        destination = "archived"

    return {
        "persona_slug": persona.slug,
        "voice_mode": mode,
        "destination": destination,
        "brief": dict(brief),
        "draft_lines": [],
        "stub": True,
    }


def _safe_slug(persona: str) -> str:
    return re.sub(r"[^a-z0-9_\-]", "", persona.lower())


@lru_cache(maxsize=64)
def _load_voice_persona_cached(slug_key: str) -> VoicePersona | None:
    path = VOICE_SPECS_DIR / f"{slug_key}.yaml"
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
        logger.warning("VoicePersona validation failed for %s: %s", slug_key, exc)
        return None


def get_voice_persona(slug: str) -> VoicePersona | None:
    """Load a voice persona from ``voice_specs/<slug>.yaml``."""
    safe = _safe_slug(slug)
    if not safe:
        return None
    return _load_voice_persona_cached(safe)


def list_voice_personas(*, reload: bool = False) -> list[VoicePersona]:
    """All voice personas with YAML specs on disk."""
    if reload:
        _load_voice_persona_cached.cache_clear()
    out: list[VoicePersona] = []
    if not VOICE_SPECS_DIR.is_dir():
        return out
    for path in sorted(VOICE_SPECS_DIR.glob("*.yaml")):
        vp = get_voice_persona(path.stem)
        if vp is not None:
            out.append(vp)
    return out
