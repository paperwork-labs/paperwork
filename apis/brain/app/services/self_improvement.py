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

from app.schemas.brain_improvement import BrainImprovementCurrent, BrainImprovementResponse
from app.schemas.operating_score import OperatingScoreFile
from app.schemas.pr_outcomes import PrOutcomesFile
from app.schemas.procedural_memory import ProceduralMemoryFile, ProceduralRule
from app.schemas.self_merge import SelfMergePromotionsFile
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
_ENV_SELF_MERGE_PROMOTIONS = "BRAIN_SELF_MERGE_PROMOTIONS_JSON"
_TMP_SUFFIX = ".tmp"

# ---------------------------------------------------------------------------
# Brain Improvement Index — weights (must sum to 1.0)
# acceptance_rate: are Brain-merged PRs sticking (not reverting at h24)?
# promotion_progress: how far along the self-merge graduation track?
# rules_learning: richness of procedural memory (proxy for learning velocity)
# retro_delta: is POS trending up from Brain's weekly retro?
# ---------------------------------------------------------------------------
_BII_W_ACCEPTANCE = 0.40
_BII_W_PROMOTION = 0.30
_BII_W_RULES = 0.20
_BII_W_RETRO = 0.10
_BII_RULES_CAP = 50  # rules_count at which rules sub-metric saturates at 100
_BII_PROMOTION_THRESHOLD = 50  # clean merges required per tier transition
_BII_RETRO_NEUTRAL = 50.0  # normalized score when pos_total_change == 0
_BII_RETRO_SCALE = 2.5  # 1 POS point → 2.5 normalized points (±20 → 0..100)


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


# ---------------------------------------------------------------------------
# Brain Improvement Index (WS-69 PR D)
# ---------------------------------------------------------------------------


def _self_merge_promotions_path() -> Path:
    override = os.environ.get(_ENV_SELF_MERGE_PROMOTIONS, "").strip()
    if override:
        return Path(override)
    return _brain_data_dir() / "self_merge_promotions.json"


def _load_self_merge_promotions() -> SelfMergePromotionsFile | None:
    path = _self_merge_promotions_path()
    if not path.is_file():
        return None
    raw = _read_json_mapping(path)
    return SelfMergePromotionsFile.model_validate(raw)


def _acceptance_rate(pr_file: PrOutcomesFile) -> float:
    """Return % of h24-measured PRs where reverted=False.

    Returns 0.0 if no measured outcomes exist — honest zero, not a fabrication.
    """
    measured = [o for o in pr_file.outcomes if o.outcomes.h24 is not None]
    if not measured:
        return 0.0
    not_reverted = sum(1 for o in measured if not o.outcomes.h24.reverted)  # type: ignore[union-attr]
    return round(not_reverted / len(measured) * 100.0, 2)


def _promotion_progress(promotions: SelfMergePromotionsFile) -> float:
    """Return progress toward next tier as a 0-100 float.

    Counts clean merges for the current tier (all merges in the current tier,
    ignoring reverted ones from the last 30 days to mirror self_merge_gate).
    Caps at 100.0 when fully graduated (tier == app-code).
    """
    if promotions.current_tier == "app-code":
        return 100.0

    tier = promotions.current_tier
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=30)

    reverted_originals: set[int] = set()
    for revert in promotions.reverts:
        rev_at = revert.reverted_at
        if rev_at.tzinfo is None:
            rev_at = rev_at.replace(tzinfo=UTC)
        else:
            rev_at = rev_at.astimezone(UTC)
        if rev_at < cutoff:
            continue
        for merge in promotions.merges:
            if merge.pr_number == revert.original_pr and merge.tier == tier:
                reverted_originals.add(revert.original_pr)

    clean = sum(
        1 for m in promotions.merges if m.tier == tier and m.pr_number not in reverted_originals
    )
    progress = min(clean / _BII_PROMOTION_THRESHOLD * 100.0, 100.0)
    return round(progress, 2)


def compute_brain_improvement_index(
    at: datetime | None = None,
) -> BrainImprovementCurrent:
    """Compute the Brain Improvement Index at a point-in-time snapshot.

    Score formula (weighted average of normalized 0-100 sub-metrics):
      score = round(
          0.40 * acceptance_rate_pct +   # PRs not reverting at h24
          0.30 * promotion_progress_pct + # progress toward next self-merge tier
          0.20 * rules_normalized +       # procedural memory richness (cap=50 rules)
          0.10 * retro_delta_normalized   # POS trend from latest weekly retro
      )

    Empty-state contract (no-silent-fallback):
      - If pr_outcomes.json, self_merge_promotions.json, or
        procedural_memory.yaml is MISSING from disk, return score=0 with
        note="insufficient data: <filename> not found".
      - Never divide by zero.
      - Never fabricate counts.
    """
    computed_at = at or datetime.now(UTC)
    if computed_at.tzinfo is None:
        computed_at = computed_at.replace(tzinfo=UTC)

    # --- load sources (file-missing = hard 0) ---
    pr_path = _pr_outcomes_path()
    if not pr_path.is_file():
        return BrainImprovementCurrent(
            score=0,
            acceptance_rate_pct=0.0,
            promotion_progress_pct=0.0,
            rules_count=0,
            retro_delta_pct=0.0,
            computed_at=computed_at,
            note="insufficient data: pr_outcomes.json not found",
        )
    pr_file = _load_pr_outcomes()

    promotions = _load_self_merge_promotions()
    if promotions is None:
        return BrainImprovementCurrent(
            score=0,
            acceptance_rate_pct=0.0,
            promotion_progress_pct=0.0,
            rules_count=0,
            retro_delta_pct=0.0,
            computed_at=computed_at,
            note="insufficient data: self_merge_promotions.json not found",
        )

    mem_path = _procedural_memory_path()
    if not mem_path.is_file():
        return BrainImprovementCurrent(
            score=0,
            acceptance_rate_pct=0.0,
            promotion_progress_pct=0.0,
            rules_count=0,
            retro_delta_pct=0.0,
            computed_at=computed_at,
            note="insufficient data: procedural_memory.yaml not found",
        )

    # --- sub-metric: acceptance rate ---
    acceptance_rate_pct = _acceptance_rate(pr_file)

    # --- sub-metric: promotion progress ---
    promotion_progress_pct = _promotion_progress(promotions)

    # --- sub-metric: rules count (proxy for learning velocity) ---
    rules = _load_procedural_rules()
    rules_count = len(rules)
    rules_normalized = min(rules_count / _BII_RULES_CAP * 100.0, 100.0)

    # --- sub-metric: retro delta (0 when no retros recorded yet — honest zero) ---
    retros = _load_retros_unlocked()
    if retros.retros:
        latest_retro = max(retros.retros, key=lambda r: r.week_ending)
        retro_delta_pct = float(latest_retro.summary.pos_total_change)
        retro_normalized = max(
            0.0, min(100.0, _BII_RETRO_NEUTRAL + retro_delta_pct * _BII_RETRO_SCALE)
        )
    else:
        retro_delta_pct = 0.0
        retro_normalized = 0.0  # no retro history — honest zero, never fabricated

    # --- composite score ---
    raw_score = (
        _BII_W_ACCEPTANCE * acceptance_rate_pct
        + _BII_W_PROMOTION * promotion_progress_pct
        + _BII_W_RULES * rules_normalized
        + _BII_W_RETRO * retro_normalized
    )
    score = max(0, min(100, round(raw_score)))

    note = ""
    if not pr_file.outcomes:
        note = "insufficient data: no PR outcomes measured yet"

    return BrainImprovementCurrent(
        score=score,
        acceptance_rate_pct=acceptance_rate_pct,
        promotion_progress_pct=promotion_progress_pct,
        rules_count=rules_count,
        retro_delta_pct=retro_delta_pct,
        computed_at=computed_at,
        note=note,
    )


def brain_improvement_response() -> BrainImprovementResponse:
    """Return the full BrainImprovementResponse including empty history_12w.

    History accumulates once a weekly score-storage cron (PR P+) is wired up.
    Until then, history_12w is always an empty list — honest, never fabricated.
    """
    current = compute_brain_improvement_index()
    return BrainImprovementResponse(current=current, history_12w=[])
