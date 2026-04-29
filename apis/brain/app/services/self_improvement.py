"""Brain weekly retrospective and self-improvement loop.

The weekly retro turns PR outcomes, POS movement, incidents, candidate work,
and procedural memory changes into durable learning records.

medallion: ops
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar, cast

import yaml

from app.schemas.operating_score import OperatingScoreFile
from app.schemas.pr_outcomes import PrOutcomesFile
from app.schemas.procedural_memory import ProceduralMemoryFile, ProceduralRule
from app.schemas.strategic_objectives import StrategicObjective, StrategicObjectivesFile
from app.schemas.weekly_retro import RetroSummary, RuleChange, WeeklyRetro, WeeklyRetrosFile

if TYPE_CHECKING:
    from collections.abc import Callable

_T = TypeVar("_T")

_ENV_WEEKLY_RETROS = "BRAIN_WEEKLY_RETROS_JSON"
_ENV_CANDIDATES = "BRAIN_WORKSTREAM_CANDIDATES_JSON"
_ENV_INCIDENTS = "BRAIN_INCIDENTS_JSON"
_ENV_PROCEDURAL_MEMORY = "BRAIN_PROCEDURAL_MEMORY_YAML"
_ENV_WORKSTREAMS = "BRAIN_WORKSTREAMS_JSON"
_TMP_SUFFIX = ".tmp"


def _repo_root() -> Path:
    override = os.environ.get("REPO_ROOT", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[4]


def _brain_data_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data"


def weekly_retros_file_path() -> Path:
    override = os.environ.get(_ENV_WEEKLY_RETROS, "").strip()
    if override:
        return Path(override)
    return _brain_data_dir() / "weekly_retros.json"


def _operating_score_path() -> Path:
    override = os.environ.get("BRAIN_OPERATING_SCORE_JSON", "").strip()
    if override:
        return Path(override)
    return _brain_data_dir() / "operating_score.json"


def _pr_outcomes_path() -> Path:
    override = os.environ.get("BRAIN_PR_OUTCOMES_JSON", "").strip()
    if override:
        return Path(override)
    return _brain_data_dir() / "pr_outcomes.json"


def _incidents_path() -> Path:
    override = os.environ.get(_ENV_INCIDENTS, "").strip()
    if override:
        return Path(override)
    return _brain_data_dir() / "incidents.json"


def _candidates_path() -> Path:
    override = os.environ.get(_ENV_CANDIDATES, "").strip()
    if override:
        return Path(override)
    return _brain_data_dir() / "workstream_candidates.json"


def _procedural_memory_path() -> Path:
    override = os.environ.get(_ENV_PROCEDURAL_MEMORY, "").strip()
    if override:
        return Path(override)
    return _brain_data_dir() / "procedural_memory.yaml"


def _objectives_path() -> Path:
    override = os.environ.get("BRAIN_OBJECTIVES_YAML", "").strip()
    if override:
        return Path(override)
    return _repo_root() / "docs" / "strategy" / "OBJECTIVES.yaml"


def _workstreams_path() -> Path:
    override = os.environ.get(_ENV_WORKSTREAMS, "").strip()
    if override:
        return Path(override)
    return _repo_root() / "apps" / "studio" / "src" / "data" / "workstreams.json"


def _lock_path() -> Path:
    return weekly_retros_file_path().with_suffix(weekly_retros_file_path().suffix + ".lock")


def _normalise_week_ending(value: datetime | None) -> datetime:
    source = value or datetime.now(UTC)
    if source.tzinfo is None:
        msg = "week_ending must be timezone-aware"
        raise ValueError(msg)
    utc_value = source.astimezone(UTC)
    return utc_value.replace(hour=0, minute=0, second=0, microsecond=0)


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _in_window(value: object, start: datetime, end: datetime) -> bool:
    parsed = _parse_datetime(value)
    return parsed is not None and start <= parsed <= end


def _read_json_mapping(path: Path) -> dict[str, object]:
    data = _read_json_value(path)
    if not isinstance(data, dict):
        msg = f"{path} must contain a JSON object"
        raise ValueError(msg)
    return cast("dict[str, object]", data)


def _read_json_value(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_pos() -> OperatingScoreFile:
    path = _operating_score_path()
    if not path.is_file():
        return OperatingScoreFile()
    return OperatingScoreFile.model_validate(_read_json_mapping(path))


def _load_pr_outcomes() -> PrOutcomesFile:
    path = _pr_outcomes_path()
    if not path.is_file():
        return PrOutcomesFile()
    return PrOutcomesFile.model_validate(_read_json_mapping(path))


def _load_incidents_mapping() -> dict[str, object]:
    path = _incidents_path()
    if not path.is_file():
        return {"schema": "incidents/v1", "incidents": []}
    raw = _read_json_mapping(path)
    _incident_rows(raw)
    return raw


def _load_candidates() -> list[dict[str, object]]:
    path = _candidates_path()
    if not path.is_file():
        return []
    raw = _read_json_value(path)
    rows = raw.get("candidates", []) if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        msg = f"{path} candidates must be a list"
        raise ValueError(msg)
    if not all(isinstance(row, dict) for row in rows):
        msg = f"{path} candidates must contain objects"
        raise ValueError(msg)
    return cast("list[dict[str, object]]", rows)


def _load_procedural_rules() -> list[ProceduralRule]:
    path = _procedural_memory_path()
    if not path.is_file():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return []
    return ProceduralMemoryFile.model_validate(raw).rules


def _load_objectives() -> list[StrategicObjective]:
    path = _objectives_path()
    if not path.is_file():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return []
    return StrategicObjectivesFile.model_validate(raw).objectives


def _load_workstreams() -> list[dict[str, object]]:
    path = _workstreams_path()
    if not path.is_file():
        return []
    raw = _read_json_mapping(path)
    rows = raw.get("workstreams", [])
    if not isinstance(rows, list):
        msg = f"{path} workstreams must be a list"
        raise ValueError(msg)
    if not all(isinstance(row, dict) for row in rows):
        msg = f"{path} workstreams must contain objects"
        raise ValueError(msg)
    return cast("list[dict[str, object]]", rows)


def _load_retros_unlocked() -> WeeklyRetrosFile:
    path = weekly_retros_file_path()
    if not path.is_file():
        return WeeklyRetrosFile()
    return WeeklyRetrosFile.model_validate(_read_json_mapping(path))


def _with_lock(func: Callable[[], _T]) -> _T:
    lock = _lock_path()
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+", encoding="utf-8") as lock_f:
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
        try:
            return func()
        finally:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)


def _write_retros_unlocked(data: WeeklyRetrosFile) -> None:
    path = weekly_retros_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = data.model_dump(mode="json", by_alias=True)
    raw = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=_TMP_SUFFIX)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception:
        with suppress(OSError):
            os.unlink(tmp_path)
        raise


def _pos_total_change(pos_file: OperatingScoreFile) -> float:
    if pos_file.current is None or len(pos_file.history) < 2:
        return 0.0
    previous = pos_file.history[-2]
    return round(float(pos_file.current.total) - float(previous.total), 4)


def _pillar_threshold_highlights(pos_file: OperatingScoreFile) -> list[str]:
    if pos_file.current is None or len(pos_file.history) < 2:
        return []
    previous = pos_file.history[-2]
    highlights: list[str] = []
    for pillar_id, current_score in pos_file.current.pillars.items():
        prior = previous.pillars.get(pillar_id)
        if prior is None:
            continue
        prior_score = float(prior.score)
        now_score = float(current_score.score)
        if prior_score < 90.0 <= now_score:
            highlights.append(f"POS pillar {pillar_id} crossed the 90 threshold")
        elif prior_score < 80.0 <= now_score:
            highlights.append(f"POS pillar {pillar_id} crossed the 80 threshold")
    return highlights


def _incident_rows(raw: dict[str, object]) -> list[dict[str, object]]:
    rows = raw.get("incidents", [])
    if not isinstance(rows, list):
        msg = "incidents must be a list"
        raise ValueError(msg)
    if not all(isinstance(row, dict) for row in rows):
        msg = "incidents must contain objects"
        raise ValueError(msg)
    return cast("list[dict[str, object]]", rows)


def _incident_timestamp(row: dict[str, object]) -> object:
    for key in ("opened_at", "detected_at", "occurred_at", "created_at", "timestamp"):
        if key in row:
            return row[key]
    return None


def _is_revert_incident(row: dict[str, object]) -> bool:
    kind = str(row.get("kind", row.get("type", ""))).strip().lower()
    return kind in {"auto-revert", "brain-merge-revert"} or "revert_pr_number" in row


def _candidate_timestamp(row: dict[str, object]) -> object:
    for key in ("proposed_at", "created_at", "submitted_at"):
        if key in row:
            return row[key]
    return None


def _promotion_timestamp(row: dict[str, object]) -> object:
    for key in ("approved_at", "promoted_at", "status_updated_at", "updated_at", "proposed_at"):
        if key in row:
            return row[key]
    return None


def _candidate_score(row: dict[str, object]) -> float:
    value = row.get("score", row.get("priority_score", 0.0))
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def _candidate_label(row: dict[str, object]) -> str:
    for key in ("id", "title", "workstream_id"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "untitled candidate"


def _candidate_highlights(
    candidates: list[dict[str, object]],
    start: datetime,
    end: datetime,
) -> list[str]:
    proposed = [row for row in candidates if _in_window(_candidate_timestamp(row), start, end)]
    top = sorted(proposed, key=_candidate_score, reverse=True)[:3]
    return [
        f"Top candidate: {_candidate_label(row)} (score={_candidate_score(row):.2f})" for row in top
    ]


def _rule_changes(rules: list[ProceduralRule], start: datetime, end: datetime) -> list[RuleChange]:
    changes: list[RuleChange] = []
    stale_cutoff = end - timedelta(days=30)
    for rule in rules:
        learned_at = rule.learned_at.astimezone(UTC)
        if start <= learned_at <= end:
            changes.append(
                RuleChange(
                    action="added",
                    rule_id=rule.id,
                    reason=f"Rule learned during weekly retro window from {rule.source}",
                )
            )
        if rule.confidence == "low" and learned_at < stale_cutoff:
            changes.append(
                RuleChange(
                    action="deprecated",
                    rule_id=rule.id,
                    reason="Low-confidence rule has not been promoted after 30 days",
                )
            )
    return changes


def _workstream_objective_ids(row: dict[str, object]) -> set[str]:
    ids: set[str] = set()
    for key in (
        "objective_id",
        "related_plan",
    ):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            ids.add(value.strip())
    for key in (
        "objective_ids",
        "related_objectives",
        "depends_on_objectives",
        "dependent_objectives",
    ):
        values = row.get(key)
        if isinstance(values, list):
            ids.update(str(value).strip() for value in values if str(value).strip())
    return ids


def _objective_progress() -> dict[str, float]:
    objectives = _load_objectives()
    if not objectives:
        return {}
    workstreams = _load_workstreams()
    progress: dict[str, float] = {}
    for objective in objectives:
        dependent = [row for row in workstreams if objective.id in _workstream_objective_ids(row)]
        if not dependent:
            progress[objective.id] = 0.0
            continue
        complete = sum(1 for row in dependent if row.get("status") == "completed")
        progress[objective.id] = round(complete / len(dependent), 4)
    return progress


def _retro_notes(summary: RetroSummary, rule_changes: list[RuleChange]) -> str:
    return (
        "Weekly self-improvement retro: "
        f"POS change {summary.pos_total_change:+.2f}, "
        f"{summary.merges} merges, {summary.reverts} reverts, "
        f"{summary.incidents} incidents, {summary.candidates_proposed} candidates proposed, "
        f"{summary.candidates_promoted} promoted, {len(rule_changes)} rule changes flagged."
    )


def compute_weekly_retro(week_ending: datetime | None = None) -> WeeklyRetro:
    """Compute one seven-day Brain retrospective ending at ``week_ending``."""
    end = _normalise_week_ending(week_ending)
    start = end - timedelta(days=7)

    pos_file = _load_pos()
    pr_file = _load_pr_outcomes()
    incidents_raw = _load_incidents_mapping()
    incidents = _incident_rows(incidents_raw)
    candidates = _load_candidates()
    rules = _load_procedural_rules()

    merges = sum(1 for row in pr_file.outcomes if _in_window(row.merged_at, start, end))
    incident_rows = [row for row in incidents if _in_window(_incident_timestamp(row), start, end)]
    revert_rows = [row for row in incident_rows if _is_revert_incident(row)]
    proposed = sum(1 for row in candidates if _in_window(_candidate_timestamp(row), start, end))
    promoted = sum(
        1
        for row in candidates
        if row.get("status") == "approved_to_workstream"
        and _in_window(_promotion_timestamp(row), start, end)
    )

    summary = RetroSummary(
        pos_total_change=_pos_total_change(pos_file),
        merges=merges,
        reverts=len(revert_rows),
        incidents=len(incident_rows),
        candidates_proposed=proposed,
        candidates_promoted=promoted,
    )

    highlights = [
        *_candidate_highlights(candidates, start, end),
        *_pillar_threshold_highlights(pos_file),
        *[
            f"Incident triggered revert: {row.get('incident_id', row.get('id', 'unknown'))}"
            for row in revert_rows
        ],
    ][:10]
    rule_changes = [*_rule_changes(rules, start, end), *propose_rule_revisions()]

    return WeeklyRetro(
        week_ending=end,
        computed_at=datetime.now(UTC),
        summary=summary,
        highlights=highlights,
        rule_changes=rule_changes,
        objective_progress=_objective_progress(),
        notes=_retro_notes(summary, rule_changes),
    )


def record_retro(retro: WeeklyRetro) -> None:
    """Append or replace a weekly retro under an exclusive lock, capped to 52 entries."""

    def _apply() -> None:
        file = _load_retros_unlocked()
        keyed = {
            existing.week_ending.astimezone(UTC): existing
            for existing in file.retros
            if existing.week_ending.astimezone(UTC) != retro.week_ending.astimezone(UTC)
        }
        keyed[retro.week_ending.astimezone(UTC)] = retro
        file.retros = sorted(keyed.values(), key=lambda row: row.week_ending)[-52:]
        _write_retros_unlocked(file)

    _with_lock(_apply)


def latest_retros(n: int = 4) -> list[WeeklyRetro]:
    """Return the latest ``n`` retros, newest first."""

    def _read() -> list[WeeklyRetro]:
        file = _load_retros_unlocked()
        rows = sorted(file.retros, key=lambda row: row.week_ending, reverse=True)
        return rows[: max(0, n)]

    return _with_lock(_read)


def propose_rule_revisions() -> list[RuleChange]:
    """Analyze incidents/reverts and propose procedural rule updates.

    The corpus is still too small for reliable correlation, so WS-64 ships the
    API surface as an explicit stub and returns no revisions until enough
    revert/rule outcome data accumulates.
    """
    return []
