"""Read-only helpers for Studio /admin/brain/personas tabs."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml

from app.personas import list_specs as list_persona_specs
from app.personas.routing import CHANNEL_PERSONA_MAP, PHRASE_KEYWORDS, SINGLE_WORD_KEYWORDS

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_COST_FILE = _DATA_DIR / "persona_cost.json"
_ROUTING_FILE = _DATA_DIR / "persona_routing.json"
_ACTIVITY_FILE = _DATA_DIR / "persona_activity.json"


def _monorepo_root() -> Path:
    env = __import__("os").environ.get("REPO_ROOT", "").strip()
    if env:
        return Path(env).resolve()
    current = Path(__file__).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".cursor" / "rules").is_dir() and (candidate / "apis" / "brain").is_dir():
            return candidate
    raise RuntimeError("Paperwork monorepo root not found; set REPO_ROOT")


def _parse_mdc_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    try:
        fm = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}, parts[2].lstrip("\n")
    if not isinstance(fm, dict):
        return {}, parts[2].lstrip("\n")
    return fm, parts[2].lstrip("\n")


def list_cursor_rule_personas() -> list[dict[str, Any]]:
    """Scan ``.cursor/rules/*.mdc`` into structured rows for Studio."""
    root = _monorepo_root()
    rules_dir = root / ".cursor" / "rules"
    if not rules_dir.is_dir():
        return []

    spec_by_name = {s.name: s for s in list_persona_specs()}

    rows: list[dict[str, Any]] = []
    for path in sorted(rules_dir.glob("*.mdc")):
        stem = path.stem
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            logger.warning("Could not read persona rule file %s", path)
            continue
        fm, _body = _parse_mdc_frontmatter(text)
        desc = fm.get("description")
        description = desc.strip() if isinstance(desc, str) else ""
        spec = spec_by_name.get(stem)
        model = spec.default_model if spec else None
        status = "active" if spec else "draft"
        rel = str(path.relative_to(root)).replace("\\", "/")
        rows.append(
            {
                "id": stem,
                "name": stem,
                "description": description,
                "model": model,
                "status": status,
                "relative_path": rel,
                "markdown_body": _body.strip(),
            }
        )
    return rows


def load_persona_cost_payload() -> dict[str, Any] | None:
    if not _COST_FILE.is_file():
        return None
    try:
        return json.loads(_COST_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Invalid or unreadable %s", _COST_FILE)
        return None


def aggregate_persona_cost(*, window: str) -> dict[str, Any]:
    """Sum cost rows for ``7d`` or ``30d`` from ``persona_cost.json`` if present."""
    if window not in ("7d", "30d"):
        window = "7d"
    raw = load_persona_cost_payload()
    if raw is None:
        return {"window": window, "personas": [], "has_file": False}

    # Supported shapes:
    # A) { "windows": { "7d": [ { "persona", "tokens_in", "tokens_out", "usd" } ] } }
    # B) [ { "persona", "window": "7d", "tokens_in", ... } ]
    rows: list[dict[str, Any]] = []
    windows = raw.get("windows")
    if isinstance(windows, dict):
        bucket = windows.get(window)
        if isinstance(bucket, list):
            rows = [r for r in bucket if isinstance(r, dict)]
    elif isinstance(raw, list):
        rows = [r for r in raw if isinstance(r, dict) and r.get("window") == window]

    by_persona: dict[str, dict[str, float]] = {}
    for r in rows:
        p = str(r.get("persona") or r.get("id") or "").strip()
        if not p:
            continue
        acc = by_persona.setdefault(
            p,
            {"tokens_in": 0.0, "tokens_out": 0.0, "usd": 0.0},
        )
        for k in ("tokens_in", "tokens_out"):
            v = r.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                acc[k] += float(v)
        u = r.get("usd")
        if isinstance(u, (int, float)) and not isinstance(u, bool):
            acc["usd"] += float(u)
        uc = r.get("usd_cents")
        if isinstance(uc, (int, float)) and not isinstance(uc, bool):
            acc["usd"] += float(uc) / 100.0

    personas = [
        {
            "persona": name,
            "tokens_in": int(vals["tokens_in"]),
            "tokens_out": int(vals["tokens_out"]),
            "usd": round(vals["usd"], 4),
        }
        for name, vals in sorted(by_persona.items(), key=lambda x: x[0].lower())
    ]
    return {"window": window, "personas": personas, "has_file": True}


def load_routing_rules() -> dict[str, Any]:
    """Prefer ``persona_routing.json``; otherwise derive from in-code router tables."""
    if _ROUTING_FILE.is_file():
        try:
            data = json.loads(_ROUTING_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = None
        if isinstance(data, dict):
            data.setdefault("derived_from_code", False)
            data.setdefault(
                "edit_path",
                "apis/brain/data/persona_routing.json",
            )
            return data

    tag_map = {k: v for k, v in CHANNEL_PERSONA_MAP.items()}
    keywords: dict[str, list[str]] = {}
    for persona, kws in SINGLE_WORD_KEYWORDS.items():
        keywords.setdefault(persona, []).extend(kws)
    for persona, kws in PHRASE_KEYWORDS.items():
        keywords.setdefault(persona, []).extend(kws)
    return {
        "derived_from_code": True,
        "edit_path": "apis/brain/app/personas/routing.py",
        "tag_to_persona": tag_map,
        "content_keyword_to_persona": keywords,
        "default_persona": "ea",
        "note": (
            "Legacy Slack channel IDs appear under tag_to_persona until "
            "persona_routing.json is introduced for tag-native routing."
        ),
    }


def load_persona_activity(*, limit: int) -> dict[str, Any]:
    lim = max(1, min(limit, 200))
    if not _ACTIVITY_FILE.is_file():
        return {"events": [], "has_file": False}
    try:
        raw = json.loads(_ACTIVITY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"events": [], "has_file": True, "parse_error": True}
    events = raw.get("events") if isinstance(raw, dict) else None
    if not isinstance(events, list):
        return {"events": [], "has_file": True, "parse_error": True}
    out: list[dict[str, Any]] = []
    for e in events[:lim]:
        if isinstance(e, dict):
            out.append(e)
    return {"events": out, "has_file": True}
