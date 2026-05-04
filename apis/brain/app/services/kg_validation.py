"""Knowledge-Graph self-validation service (WS-52).

Checks the integrity of Brain's data files and Pydantic schemas, then writes
a structured report to ``apis/brain/data/kg_validation.json``.

Six rule classes:
  1. schema_validation           — each data/*.json parses against its Pydantic schema
  2. workstream_id_references    — WS-XX references in data files resolve to real workstreams
  3. persona_owner_references    — workstream owners exist as known persona IDs or system actors
  4. procedural_memory_freshness — low-confidence rules older than 180 days are flagged stale
  5. dangling_dispatch_log       — agent_dispatch_log entries reference known workstream IDs
  6. operating_score_pillar_consistency — operating_score pillars match operating_score_spec.yaml

medallion: ops
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.schemas.kg_validation import (
    KGValidationFile,
    KGValidationRun,
    KGViolation,
    ViolationSeverity,
)

logger = logging.getLogger(__name__)

_ENV_KG_JSON = "BRAIN_KG_VALIDATION_JSON"

_MAX_HISTORY = 30
_STALE_DAYS = 180

# Known system actors that are always valid workstream owners.
_SYSTEM_ACTORS: frozenset[str] = frozenset({"brain", "opus", "founder", "community", "admin"})


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    from app.utils.paths import repo_root

    return repo_root()


def _brain_data_dir() -> Path:
    from app.utils.paths import brain_data_dir

    return brain_data_dir()


def kg_validation_file_path() -> Path:
    override = os.environ.get(_ENV_KG_JSON, "").strip()
    if override:
        return Path(override)
    return _brain_data_dir() / "kg_validation.json"


def _cursor_rules_dir() -> Path:
    return _repo_root() / ".cursor" / "rules"


def _workstreams_path() -> Path:
    override = os.environ.get("BRAIN_WORKSTREAMS_JSON", "").strip()
    if override:
        return Path(override)
    return _repo_root() / "apps" / "studio" / "src" / "data" / "workstreams.json"


def _operating_score_spec_path() -> Path:
    override = os.environ.get("BRAIN_OPERATING_SCORE_SPEC_YAML", "").strip()
    if override:
        return Path(override)
    return _brain_data_dir() / "operating_score_spec.yaml"


def _operating_score_json_path() -> Path:
    override = os.environ.get("BRAIN_OPERATING_SCORE_JSON", "").strip()
    if override:
        return Path(override)
    return _brain_data_dir() / "operating_score.json"


def _procedural_memory_path() -> Path:
    override = os.environ.get("BRAIN_PROCEDURAL_MEMORY_YAML", "").strip()
    if override:
        return Path(override)
    return _brain_data_dir() / "procedural_memory.yaml"


def _dispatch_log_path() -> Path:
    override = os.environ.get("BRAIN_AGENT_DISPATCH_LOG_JSON", "").strip()
    if override:
        return Path(override)
    return _brain_data_dir() / "agent_dispatch_log.json"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _safe_read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _safe_read_yaml(path: Path) -> Any | None:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError, UnicodeDecodeError):
        return None


def _workstream_ids(workstreams_path: Path) -> frozenset[str]:
    """Return all workstream IDs from workstreams.json."""
    data = _safe_read_json(workstreams_path)
    if not isinstance(data, dict):
        return frozenset()
    rows = data.get("workstreams")
    if not isinstance(rows, list):
        return frozenset()
    ids: set[str] = set()
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("id"), str):
            ids.add(row["id"])
    return frozenset(ids)


def _known_persona_ids() -> frozenset[str]:
    """Collect persona IDs from .cursor/rules/*.mdc stem names plus system actors."""
    ids: set[str] = set(_SYSTEM_ACTORS)
    rules_dir = _cursor_rules_dir()
    if rules_dir.is_dir():
        for mdc in rules_dir.glob("*.mdc"):
            stem = mdc.stem  # e.g. "cfo", "growth", "brain-skill-engineer"
            ids.add(stem)
            # Also try to read an `id:` field from YAML frontmatter if present
            try:
                text = mdc.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if text.startswith("---"):
                end = text.find("---", 3)
                if end != -1:
                    fm_text = text[3:end].strip()
                    try:
                        fm = yaml.safe_load(fm_text)
                    except yaml.YAMLError:
                        fm = None
                    if isinstance(fm, dict) and isinstance(fm.get("id"), str):
                        ids.add(fm["id"])
    return frozenset(ids)


_WS_ID_RE = re.compile(r"\bWS-\d+(?:-[a-z0-9]+)+\b", re.IGNORECASE)


def _extract_ws_refs(obj: Any) -> set[str]:
    """Recursively extract WS-XX-... style references from a JSON-decoded object."""
    found: set[str] = set()
    if isinstance(obj, str):
        found.update(m.upper() for m in _WS_ID_RE.findall(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            found.update(_extract_ws_refs(v))
    elif isinstance(obj, list):
        for item in obj:
            found.update(_extract_ws_refs(item))
    return found


# ---------------------------------------------------------------------------
# Schema map: data file stem → Pydantic model for validation
# ---------------------------------------------------------------------------


def _schema_map() -> dict[str, type[Any]]:
    """Return a mapping of data-file stem to its Pydantic model class."""
    from app.schemas.incidents import IncidentsFile
    from app.schemas.kg_validation import KGValidationFile
    from app.schemas.operating_score import OperatingScoreFile
    from app.schemas.pr_outcomes import PrOutcomesFile
    from app.schemas.self_merge import SelfMergePromotionsFile
    from app.schemas.weekly_retro import WeeklyRetrosFile
    from app.schemas.workstream_candidates import WorkstreamCandidatesFile

    return {
        "operating_score": OperatingScoreFile,
        "pr_outcomes": PrOutcomesFile,
        "incidents": IncidentsFile,
        "self_merge_promotions": SelfMergePromotionsFile,
        "weekly_retros": WeeklyRetrosFile,
        "workstream_candidates": WorkstreamCandidatesFile,
        "kg_validation": KGValidationFile,
    }


# ---------------------------------------------------------------------------
# Rule 1: schema_validation
# ---------------------------------------------------------------------------


def _rule_schema_validation(
    data_dir: Path,
    files_checked: list[str],
) -> list[KGViolation]:
    """Parse each data/*.json against its matching Pydantic schema."""
    violations: list[KGViolation] = []
    schema_map = _schema_map()

    for stem, model_cls in schema_map.items():
        json_path = data_dir / f"{stem}.json"
        if not json_path.is_file():
            continue
        files_checked.append(str(json_path))
        raw = _safe_read_json(json_path)
        if raw is None:
            violations.append(
                KGViolation(
                    rule="schema_validation",
                    severity=ViolationSeverity.high,
                    where=str(json_path.relative_to(data_dir.parent.parent.parent.parent)),
                    detail=f"{json_path.name} could not be decoded as JSON",
                )
            )
            continue
        try:
            if hasattr(model_cls, "model_validate"):
                model_cls.model_validate(raw)
            else:
                model_cls(**raw)
        except ValidationError as exc:
            violations.append(
                KGViolation(
                    rule="schema_validation",
                    severity=ViolationSeverity.high,
                    where=str(json_path.relative_to(data_dir.parent.parent.parent.parent)),
                    detail=f"Pydantic ValidationError: {exc.error_count()} error(s): "
                    + "; ".join(f"{e['loc']} {e['msg']}" for e in exc.errors()[:3]),
                )
            )
    return violations


# ---------------------------------------------------------------------------
# Rule 2: workstream_id_references
# ---------------------------------------------------------------------------


def _rule_workstream_id_references(
    data_dir: Path,
    ws_ids: frozenset[str],
    files_checked: list[str],
) -> list[KGViolation]:
    """Scan data JSON files for WS-XX references; flag any that are not in workstreams.json."""
    violations: list[KGViolation] = []
    # Normalise the workstream IDs for case-insensitive lookup
    ws_ids_upper = frozenset(w.upper() for w in ws_ids)

    for json_path in sorted(data_dir.glob("*.json")):
        if json_path.name == "kg_validation.json":
            continue  # skip self-referential file
        if str(json_path) not in files_checked:
            files_checked.append(str(json_path))
        raw = _safe_read_json(json_path)
        if raw is None:
            continue
        refs = _extract_ws_refs(raw)
        for ref in sorted(refs):
            # Only check IDs that look like full slugs (have a hyphen after the number)
            if ref.upper() not in ws_ids_upper:
                violations.append(
                    KGViolation(
                        rule="workstream_id_references",
                        severity=ViolationSeverity.medium,
                        where=str(json_path),
                        detail=(
                            f"References workstream '{ref}' which does not exist"
                            " in workstreams.json"
                        ),
                    )
                )
    return violations


# ---------------------------------------------------------------------------
# Rule 3: persona_owner_references
# ---------------------------------------------------------------------------


def _rule_persona_owner_references(
    workstreams_path: Path,
    known_personas: frozenset[str],
    files_checked: list[str],
) -> list[KGViolation]:
    """Each workstream owner must match a known persona or system actor."""
    violations: list[KGViolation] = []
    if str(workstreams_path) not in files_checked:
        files_checked.append(str(workstreams_path))
    data = _safe_read_json(workstreams_path)
    if not isinstance(data, dict):
        return violations
    rows = data.get("workstreams") or []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ws_id = row.get("id", "?")
        owner = row.get("owner")
        if owner is None:
            continue
        if owner not in known_personas:
            violations.append(
                KGViolation(
                    rule="persona_owner_references",
                    severity=ViolationSeverity.medium,
                    where=f"apps/studio/src/data/workstreams.json:{ws_id}",
                    detail=(
                        f"owner='{owner}' not found in .cursor/rules/*.mdc personas "
                        f"or known system actors {sorted(_SYSTEM_ACTORS)}"
                    ),
                )
            )
    return violations


# ---------------------------------------------------------------------------
# Rule 4: procedural_memory_freshness
# ---------------------------------------------------------------------------


def _rule_procedural_memory_freshness(
    memory_path: Path,
    files_checked: list[str],
) -> list[KGViolation]:
    """Low-confidence rules older than 180 days are flagged as stale."""
    violations: list[KGViolation] = []
    if str(memory_path) not in files_checked:
        files_checked.append(str(memory_path))
    raw = _safe_read_yaml(memory_path)
    if not isinstance(raw, dict):
        return violations
    rules = raw.get("rules") or []
    cutoff = datetime.now(UTC) - timedelta(days=_STALE_DAYS)
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rule_id = rule.get("id", "?")
        confidence = rule.get("confidence", "")
        learned_at_raw = rule.get("learned_at")
        if confidence != "low" or not isinstance(learned_at_raw, str):
            continue
        learned_str = learned_at_raw.strip()
        if learned_str.endswith("Z"):
            learned_str = learned_str[:-1] + "+00:00"
        try:
            learned_dt = datetime.fromisoformat(learned_str)
        except ValueError:
            continue
        if learned_dt.tzinfo is None:
            learned_dt = learned_dt.replace(tzinfo=UTC)
        if learned_dt < cutoff:
            age_days = (datetime.now(UTC) - learned_dt).days
            violations.append(
                KGViolation(
                    rule="procedural_memory_freshness",
                    severity=ViolationSeverity.low,
                    where=f"apis/brain/data/procedural_memory.yaml:{rule_id}",
                    detail=(
                        f"Rule '{rule_id}' has confidence=low and is {age_days} days old "
                        f"(>{_STALE_DAYS} days threshold) — consider reviewing or removing"
                    ),
                )
            )
    return violations


# ---------------------------------------------------------------------------
# Rule 5: dangling_dispatch_log
# ---------------------------------------------------------------------------


def _rule_dangling_dispatch_log(
    dispatch_log_path: Path,
    ws_ids: frozenset[str],
    files_checked: list[str],
) -> list[KGViolation]:
    """agent_dispatch_log entries must reference workstream IDs that exist."""
    violations: list[KGViolation] = []
    if str(dispatch_log_path) not in files_checked:
        files_checked.append(str(dispatch_log_path))
    data = _safe_read_json(dispatch_log_path)
    if not isinstance(data, dict):
        return violations
    dispatches = data.get("dispatches") or []
    ws_ids_upper = frozenset(w.upper() for w in ws_ids)
    for entry in dispatches:
        if not isinstance(entry, dict):
            continue
        ws_ref = entry.get("workstream_id")
        dispatch_id = entry.get("dispatch_id", "?")
        if not isinstance(ws_ref, str):
            continue
        if ws_ref.upper() not in ws_ids_upper:
            violations.append(
                KGViolation(
                    rule="dangling_dispatch_log",
                    severity=ViolationSeverity.medium,
                    where=f"apis/brain/data/agent_dispatch_log.json:{dispatch_id}",
                    detail=(
                        f"Dispatch entry references workstream_id='{ws_ref}' "
                        "which does not exist in workstreams.json"
                    ),
                )
            )
    return violations


# ---------------------------------------------------------------------------
# Rule 6: operating_score_pillar_consistency
# ---------------------------------------------------------------------------


def _rule_operating_score_pillar_consistency(
    spec_path: Path,
    score_json_path: Path,
    files_checked: list[str],
) -> list[KGViolation]:
    """Pillar keys in operating_score.json current entry must match spec pillar IDs."""
    violations: list[KGViolation] = []
    for p in (spec_path, score_json_path):
        if str(p) not in files_checked:
            files_checked.append(str(p))

    spec_raw = _safe_read_yaml(spec_path)
    if not isinstance(spec_raw, dict):
        return violations
    spec_pillars = spec_raw.get("pillars") or []
    spec_ids: set[str] = set()
    for p in spec_pillars:
        if isinstance(p, dict) and isinstance(p.get("id"), str):
            spec_ids.add(p["id"])

    if not spec_ids:
        return violations

    score_raw = _safe_read_json(score_json_path)
    if not isinstance(score_raw, dict):
        return violations
    current = score_raw.get("current")
    if not isinstance(current, dict):
        return violations
    actual_pillars = current.get("pillars")
    if not isinstance(actual_pillars, dict):
        return violations
    actual_ids = set(actual_pillars.keys())

    missing_in_score = spec_ids - actual_ids
    extra_in_score = actual_ids - spec_ids

    for pid in sorted(missing_in_score):
        violations.append(
            KGViolation(
                rule="operating_score_pillar_consistency",
                severity=ViolationSeverity.high,
                where="apis/brain/data/operating_score.json:current.pillars",
                detail=(
                    f"Pillar '{pid}' is defined in operating_score_spec.yaml "
                    "but missing from operating_score.json current snapshot"
                ),
            )
        )
    for pid in sorted(extra_in_score):
        violations.append(
            KGViolation(
                rule="operating_score_pillar_consistency",
                severity=ViolationSeverity.medium,
                where="apis/brain/data/operating_score.json:current.pillars",
                detail=(
                    f"Pillar '{pid}' appears in operating_score.json current snapshot "
                    "but is not defined in operating_score_spec.yaml"
                ),
            )
        )
    return violations


# ---------------------------------------------------------------------------
# Top-level validate()
# ---------------------------------------------------------------------------


def validate(
    *,
    repo_root: Path | None = None,
    data_dir: Path | None = None,
) -> KGValidationRun:
    """Run all KG validation rules and return a :class:`KGValidationRun`."""
    root = repo_root or _repo_root()
    dd = data_dir or _brain_data_dir()
    if data_dir is None:
        ws_path = _workstreams_path()
        spec_path = _operating_score_spec_path()
        score_path = _operating_score_json_path()
    else:
        ws_path = root / "apps" / "studio" / "src" / "data" / "workstreams.json"
        spec_path = dd / "operating_score_spec.yaml"
        score_path = dd / "operating_score.json"
    memory_path = _procedural_memory_path() if data_dir is None else dd / "procedural_memory.yaml"
    dispatch_path = _dispatch_log_path() if data_dir is None else dd / "agent_dispatch_log.json"

    files_checked: list[str] = []
    all_violations: list[KGViolation] = []

    ws_ids = _workstream_ids(ws_path)
    known_personas = _known_persona_ids()

    # Rule 1
    all_violations.extend(_rule_schema_validation(dd, files_checked))
    # Rule 2
    all_violations.extend(_rule_workstream_id_references(dd, ws_ids, files_checked))
    # Rule 3
    all_violations.extend(_rule_persona_owner_references(ws_path, known_personas, files_checked))
    # Rule 4
    all_violations.extend(_rule_procedural_memory_freshness(memory_path, files_checked))
    # Rule 5
    all_violations.extend(_rule_dangling_dispatch_log(dispatch_path, ws_ids, files_checked))
    # Rule 6
    all_violations.extend(
        _rule_operating_score_pillar_consistency(spec_path, score_path, files_checked)
    )

    files_checked_unique = sorted(set(files_checked))
    n_high = sum(1 for v in all_violations if v.severity == ViolationSeverity.high)
    n_medium = sum(1 for v in all_violations if v.severity == ViolationSeverity.medium)
    n_low = sum(1 for v in all_violations if v.severity == ViolationSeverity.low)

    passed = len(all_violations) == 0

    parts = [f"{len(files_checked_unique)} files checked"]
    if all_violations:
        sev_parts = []
        if n_high:
            sev_parts.append(f"{n_high} high")
        if n_medium:
            sev_parts.append(f"{n_medium} medium")
        if n_low:
            sev_parts.append(f"{n_low} low")
        parts.append(f"{len(all_violations)} violation(s) ({', '.join(sev_parts)})")
    else:
        parts.append("0 violations — all checks passed")

    summary = "; ".join(parts)
    now_str = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    return KGValidationRun(
        validated_at=now_str,
        files_checked=len(files_checked_unique),
        violations=all_violations,
        passed=passed,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def load_validation_file() -> KGValidationFile:
    """Read (or bootstrap) ``kg_validation.json``."""
    path = kg_validation_file_path()
    if not path.is_file():
        return KGValidationFile()
    raw = _safe_read_json(path)
    if not isinstance(raw, dict):
        return KGValidationFile()
    try:
        return KGValidationFile.model_validate(raw)
    except ValidationError:
        logger.warning("kg_validation.json failed validation — resetting to empty")
        return KGValidationFile()


def record_validation_run(run: KGValidationRun) -> None:
    """Atomic write: update current + append to history (capped at 30 entries)."""
    path = kg_validation_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = Path(str(path) + ".lock")

    file = load_validation_file()
    if file.current is not None:
        new_history = [file.current, *file.history]
        file = KGValidationFile(
            current=run,
            history=new_history[:_MAX_HISTORY],
        )
    else:
        file = KGValidationFile(current=run, history=[])

    payload = file.model_dump(mode="json", by_alias=True)
    payload["schema"] = "kg_validation/v1"
    raw = json.dumps(payload, indent=2) + "\n"

    tmp_fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            fh.write(raw)
        os.replace(tmp_name, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise

    lock_path.unlink(missing_ok=True)
    logger.info(
        "kg_validation: recorded run validated_at=%s passed=%s violations=%d",
        run.validated_at,
        run.passed,
        len(run.violations),
    )
