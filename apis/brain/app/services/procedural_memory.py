"""Procedural memory service -- reads and writes apis/brain/data/procedural_memory.yaml.

Procedural rules encode "when X, do Y" knowledge distilled from incidents,
PR retros, and dispatch outcomes.  The WS-64 self-improvement loop consumes
these rules to bias agent dispatch and workstream decomposition.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.schemas.procedural_memory import (
    ProceduralMemoryFile,
    ProceduralRule,
    ProceduralRuleInput,
)

logger = logging.getLogger(__name__)

_CONFIDENCE_ORDER: dict[str, int] = {"high": 0, "medium": 1, "low": 2}


def _data_dir() -> Path:
    repo_root = os.environ.get("REPO_ROOT")
    if repo_root:
        return Path(repo_root) / "apis" / "brain" / "data"
    return Path(__file__).parent.parent.parent.parent / "data"


def _memory_path() -> Path:
    return _data_dir() / "procedural_memory.yaml"


def _incidents_path() -> Path:
    return _data_dir() / "incidents.json"


def load_rules() -> list[ProceduralRule]:
    """Read procedural_memory.yaml, validate schema, and return all rules.

    Raises FileNotFoundError if the YAML file is missing.
    Raises pydantic.ValidationError if the content fails schema validation.
    """
    path = _memory_path()
    raw = path.read_text(encoding="utf-8")
    data: dict[str, Any] = yaml.safe_load(raw)
    file = ProceduralMemoryFile.model_validate(data)
    return file.rules


def find_rules_for_context(context_keywords: list[str]) -> list[ProceduralRule]:
    """Return rules whose ``when`` field contains any of *context_keywords*.

    Match is case-insensitive substring.  Results are sorted by confidence
    (high -> medium -> low).
    """
    if not context_keywords:
        return []

    rules = load_rules()
    patterns = [kw.lower() for kw in context_keywords]

    matched = [r for r in rules if any(p in r.when.lower() for p in patterns)]
    return sorted(matched, key=lambda r: _CONFIDENCE_ORDER[r.confidence])


def add_rule(rule: ProceduralRuleInput) -> None:
    """Append *rule* to procedural_memory.yaml.

    - If a rule with the same ``id`` already exists, logs a warning and no-ops.
    - Write is atomic: write to a temp file in the same directory, then
      ``os.replace`` to avoid partial writes.
    - ``learned_at`` is set to UTC now if the caller left it as None.
    """
    path = _memory_path()
    raw = path.read_text(encoding="utf-8")
    data: dict[str, Any] = yaml.safe_load(raw)
    file = ProceduralMemoryFile.model_validate(data)

    existing_ids = {r.id for r in file.rules}
    if rule.id in existing_ids:
        logger.warning("procedural_memory: rule %r already exists -- skipping add", rule.id)
        return

    learned_at = rule.learned_at or datetime.now(UTC)

    new_rule = ProceduralRule(
        id=rule.id,
        when=rule.when,
        do=rule.do,
        source=rule.source,
        learned_at=learned_at,
        confidence=rule.confidence,
        applies_to=rule.applies_to,
    )
    file.rules.append(new_rule)

    _atomic_write(path, file)


def consolidate_from_incidents(
    incidents_path: Path | None = None,
) -> list[ProceduralRule]:
    """Distil candidate procedural rules from incidents.json.

    Returns an empty list if the incidents file is missing or empty.
    Each incident with a ``title`` and ``resolution`` (or ``summary``) field
    is converted to a low-confidence candidate rule.  These candidates are
    NOT written to the YAML automatically -- callers decide whether to persist
    them via ``add_rule()``.
    """
    target = incidents_path or _incidents_path()
    if not target.exists():
        logger.info("procedural_memory: incidents file not found at %s -- returning []", target)
        return []

    try:
        raw = target.read_text(encoding="utf-8")
        incidents: list[dict[str, Any]] = json.loads(raw)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("procedural_memory: could not read incidents file: %s", exc)
        return []

    if not incidents:
        return []

    candidates: list[ProceduralRule] = []
    now = datetime.now(UTC)

    for incident in incidents:
        title: str = incident.get("title", "").strip()
        resolution: str = (incident.get("resolution") or incident.get("summary") or "").strip()

        if not title or not resolution:
            continue

        rule_id = _slugify(title)
        try:
            rule = ProceduralRule(
                id=rule_id,
                when=title,
                do=resolution,
                source="incident:" + incident.get("id", rule_id),
                learned_at=incident.get("occurred_at")
                or incident.get("created_at")
                or now.isoformat(),
                confidence="low",
                applies_to=["orchestrator", "cheap-agents"],
            )
            candidates.append(rule)
        except ValidationError as exc:
            logger.warning(
                "procedural_memory: skipping incident %r -- validation error: %s",
                title,
                exc,
            )

    return candidates


def _slugify(text: str) -> str:
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    return slug[:80] or "incident"


def _atomic_write(path: Path, file: ProceduralMemoryFile) -> None:
    rules_data: list[dict[str, Any]] = []
    for rule in file.rules:
        entry: dict[str, Any] = {
            "id": rule.id,
            "when": rule.when,
            "do": rule.do,
            "source": rule.source,
            "learned_at": rule.learned_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "confidence": rule.confidence,
            "applies_to": list(rule.applies_to),
        }
        rules_data.append(entry)

    payload: dict[str, Any] = {
        "version": file.version,
        "rules": rules_data,
    }

    dir_ = path.parent
    fd, tmp_path = tempfile.mkstemp(dir=dir_, suffix=".yaml.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            yaml.dump(
                payload,
                fh,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
        os.replace(tmp_path, path)
    except Exception:
        import contextlib

        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise
