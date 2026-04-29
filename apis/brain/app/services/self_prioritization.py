"""Brain self-prioritization service for Phase G2 workstream proposals.

Scans founder objectives, POS pillars, procedural memory, stack-audit verdicts,
and PR outcomes to produce ranked candidate workstreams for founder review.

medallion: ops
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

import yaml
from pydantic import BaseModel, Field

from app.schemas.workstream import WorkstreamsFile
from app.schemas.workstream_candidates import (
    EstimatedImpact,
    SourceSignal,
    WorkstreamCandidate,
    WorkstreamCandidatesFile,
)
from app.services.workstreams_loader import invalidate_workstreams_cache

if TYPE_CHECKING:
    from collections.abc import Callable

_CANDIDATES_ENV = "BRAIN_WORKSTREAM_CANDIDATES_JSON"
_OBJECTIVES_ENV = "BRAIN_OBJECTIVES_YAML"
_POS_ENV = "BRAIN_OPERATING_SCORE_JSON"
_PROCEDURAL_MEMORY_ENV = "BRAIN_PROCEDURAL_MEMORY_YAML"
_STACK_AUDIT_ENV = "BRAIN_STACK_AUDIT_MD"
_PR_OUTCOMES_ENV = "BRAIN_PR_OUTCOMES_JSON"
_WORKSTREAMS_ENV = "BRAIN_WORKSTREAMS_JSON"
_TMP_PREFIX = ".workstream_candidates."
_HISTORY_AFTER = timedelta(days=14)
_T = TypeVar("_T")

_IMPACT_WEIGHTS: dict[EstimatedImpact, int] = {
    "critical": 40,
    "high": 25,
    "medium": 15,
    "low": 5,
}


class Signal(BaseModel):
    """A source signal that can become a founder-reviewed workstream candidate."""

    source_signal: SourceSignal
    source_ref: str
    title: str = Field(..., min_length=3, max_length=100)
    why_now: str
    estimated_effort_days: float = Field(ge=0)
    estimated_impact: EstimatedImpact
    observed_at: datetime
    stale_days: float = Field(default=0, ge=0)
    objective_aligned: bool = False


@dataclass(frozen=True)
class PromotionResult:
    """New workstream entry created by promoting a candidate."""

    candidate: WorkstreamCandidate
    workstream: dict[str, Any]


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _repo_root() -> Path:
    env = os.environ.get("REPO_ROOT")
    if env:
        return Path(env).resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "apis" / "brain").is_dir() and (parent / "apps" / "studio").is_dir():
            return parent
    return here.parents[4]


def candidates_file_path() -> Path:
    override = os.environ.get(_CANDIDATES_ENV, "").strip()
    if override:
        return Path(override)
    return _repo_root() / "apis" / "brain" / "data" / "workstream_candidates.json"


def objectives_path() -> Path:
    override = os.environ.get(_OBJECTIVES_ENV, "").strip()
    if override:
        return Path(override)
    return _repo_root() / "docs" / "strategy" / "OBJECTIVES.yaml"


def operating_score_path() -> Path:
    override = os.environ.get(_POS_ENV, "").strip()
    if override:
        return Path(override)
    return _repo_root() / "apis" / "brain" / "data" / "operating_score.json"


def procedural_memory_path() -> Path:
    override = os.environ.get(_PROCEDURAL_MEMORY_ENV, "").strip()
    if override:
        return Path(override)
    return _repo_root() / "apis" / "brain" / "data" / "procedural_memory.yaml"


def stack_audit_path() -> Path:
    override = os.environ.get(_STACK_AUDIT_ENV, "").strip()
    if override:
        return Path(override)
    return _repo_root() / "docs" / "STACK_AUDIT_2026-Q2.md"


def pr_outcomes_path() -> Path:
    override = os.environ.get(_PR_OUTCOMES_ENV, "").strip()
    if override:
        return Path(override)
    return _repo_root() / "apis" / "brain" / "data" / "pr_outcomes.json"


def workstreams_json_path() -> Path:
    override = os.environ.get(_WORKSTREAMS_ENV, "").strip()
    if override:
        return Path(override)
    return _repo_root() / "apps" / "studio" / "src" / "data" / "workstreams.json"


def _lock_path(path: Path) -> Path:
    return path.with_name(path.name + ".lock")


def _normalise_dt(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_dt(raw: object) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return _normalise_dt(raw)
    if not isinstance(raw, str) or not raw.strip():
        return None
    s = raw.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return _normalise_dt(datetime.fromisoformat(s))


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, indent=2, sort_keys=False) + "\n"
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            dir=path.parent,
            prefix=_TMP_PREFIX,
            suffix=".tmp",
            encoding="utf-8",
            delete=False,
        ) as handle:
            tmp_path = handle.name
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _with_file_lock(path: Path, fn: Callable[[], _T]) -> _T:
    lock_path = _lock_path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lockf:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
        try:
            return fn()
        finally:
            fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)


def _candidate_dump(file: WorkstreamCandidatesFile) -> dict[str, Any]:
    payload = file.model_dump(mode="json", by_alias=True)
    payload["generated_at"] = _to_z(payload["generated_at"]) if payload["generated_at"] else None
    for bucket in ("candidates", "history"):
        for row in payload[bucket]:
            row["proposed_at"] = _to_z(row["proposed_at"])
    return payload


def _to_z(value: str) -> str:
    return value.replace("+00:00", "Z")


def load_candidates_file() -> WorkstreamCandidatesFile:
    path = candidates_file_path()
    if not path.exists():
        return WorkstreamCandidatesFile()
    data = _read_json(path)
    if not isinstance(data, dict):
        msg = f"workstream_candidates: expected object at {path}"
        raise ValueError(msg)
    return WorkstreamCandidatesFile.model_validate(data)


def latest_candidates() -> list[WorkstreamCandidate]:
    """Return the current candidate list without mutating disk."""
    return load_candidates_file().candidates


def gather_signals() -> list[Signal]:
    """Collect prioritization signals from repo-local Brain data sources."""
    signals: list[Signal] = []
    signals.extend(_objective_gap_signals())
    signals.extend(_pos_pillar_signals())
    signals.extend(_procedural_rule_signals())
    signals.extend(_stack_audit_replace_signals())
    signals.extend(_pr_outcome_regression_signals())
    return signals


def _objective_gap_signals() -> list[Signal]:
    path = objectives_path()
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"objectives: expected mapping at {path}"
        raise ValueError(msg)
    objectives = raw.get("objectives") or []
    if not isinstance(objectives, list):
        msg = f"objectives: expected objectives list at {path}"
        raise ValueError(msg)

    last_reviewed = _parse_dt(raw.get("last_reviewed_at"))
    now = _utcnow()
    stale_days = 31.0 if last_reviewed is None else (now - last_reviewed).total_seconds() / 86400
    file_is_stale = stale_days > 30
    out: list[Signal] = []
    for objective in objectives:
        if not isinstance(objective, dict):
            continue
        objective_id = str(objective.get("id") or "").strip()
        if not objective_id:
            continue
        progress = _progress_number(objective.get("progress"))
        has_progress_gap = progress is not None and progress < 50
        if not has_progress_gap and not file_is_stale:
            continue
        objective_text = str(objective.get("objective") or objective_id)
        reason = (
            "progress is below 50%"
            if has_progress_gap
            else "objective review is older than 30 days"
        )
        out.append(
            Signal(
                source_signal="objective_gap",
                source_ref=f"OBJ:{objective_id}",
                title=_short_title(f"Close objective gap: {objective_text}"),
                why_now=f"Founder objective `{objective_id}` needs attention because {reason}.",
                estimated_effort_days=3.0,
                estimated_impact="high",
                observed_at=last_reviewed or now - timedelta(days=31),
                stale_days=max(stale_days, 0),
                objective_aligned=True,
            )
        )
    return out


def _progress_number(raw: object) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, int | float):
        return float(raw)
    if isinstance(raw, str):
        match = re.search(r"\d+(?:\.\d+)?", raw)
        if match:
            return float(match.group(0))
    return None


def _pos_pillar_signals() -> list[Signal]:
    path = operating_score_path()
    if not path.exists():
        return []
    data = _read_json(path)
    current = data.get("current") if isinstance(data, dict) else None
    if not isinstance(current, dict):
        return []
    computed_at = _parse_dt(current.get("computed_at")) or _utcnow()
    pillars = current.get("pillars") or {}
    if not isinstance(pillars, dict):
        msg = f"operating_score: expected current.pillars object at {path}"
        raise ValueError(msg)
    out: list[Signal] = []
    for pillar_id, pillar in pillars.items():
        if not isinstance(pillar, dict):
            continue
        score = pillar.get("score")
        if not isinstance(score, int | float):
            continue
        if score < 70 and pillar.get("measured") is True:
            out.append(
                Signal(
                    source_signal="pos_pillar_below_70",
                    source_ref=f"pillar:{pillar_id}",
                    title=_short_title(f"Raise POS pillar {pillar_id} above 70"),
                    why_now=(
                        f"Measured POS pillar `{pillar_id}` is {score:.1f}, below the 70 floor."
                    ),
                    estimated_effort_days=2.0,
                    estimated_impact="high" if score < 50 else "medium",
                    observed_at=computed_at,
                    stale_days=max((_utcnow() - computed_at).total_seconds() / 86400, 0),
                )
            )
    return out


def rule_use_count(rule_id: str) -> int:
    """Placeholder rule usage counter until Brain records rule-hit telemetry."""
    return 6 if rule_id else 0


def _procedural_rule_signals() -> list[Signal]:
    path = procedural_memory_path()
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"procedural_memory: expected mapping at {path}"
        raise ValueError(msg)
    rules = raw.get("rules") or []
    if not isinstance(rules, list):
        msg = f"procedural_memory: expected rules list at {path}"
        raise ValueError(msg)
    out: list[Signal] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        applies_to = rule.get("applies_to") or []
        if "orchestrator" not in applies_to:
            continue
        rule_id = str(rule.get("id") or "").strip()
        if rule_use_count(rule_id) <= 5:
            continue
        learned_at = _parse_dt(rule.get("learned_at")) or _utcnow()
        out.append(
            Signal(
                source_signal="procedural_rule_demand",
                source_ref=f"rule:{rule_id}",
                title=_short_title(f"Automate procedural rule: {rule_id.replace('_', ' ')}"),
                why_now=(
                    f"Procedural rule `{rule_id}` applies to orchestrator work and crossed the "
                    "placeholder weekly demand threshold."
                ),
                estimated_effort_days=1.0,
                estimated_impact="medium",
                observed_at=learned_at,
                stale_days=max((_utcnow() - learned_at).total_seconds() / 86400, 0),
            )
        )
    return out


def _stack_audit_replace_signals() -> list[Signal]:
    path = stack_audit_path()
    if not path.exists():
        return []
    out: list[Signal] = []
    audit_date = _stack_audit_date(path.read_text(encoding="utf-8"))
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or "REPLACE" not in line:
            continue
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if len(cells) < 5 or cells[3] != "REPLACE":
            continue
        layer = cells[0]
        replacement = cells[6] if len(cells) > 6 and cells[6] != "-" else "target replacement"
        source_ref = f"audit:{_slug(layer)}_replace"
        out.append(
            Signal(
                source_signal="stack_audit_replace",
                source_ref=source_ref,
                title=_short_title(f"Replace {layer} with {replacement}"),
                why_now=f"Q2 stack audit marks `{layer}` as REPLACE for operational consistency.",
                estimated_effort_days=5.0 if cells[5:6] == ["M"] else 8.0,
                estimated_impact="high",
                observed_at=audit_date,
                stale_days=max((_utcnow() - audit_date).total_seconds() / 86400, 0),
            )
        )
    return out


def _stack_audit_date(raw: str) -> datetime:
    match = re.search(r"\*\*Audit date:\*\*\s*(\d{4}-\d{2}-\d{2})", raw)
    if not match:
        return _utcnow()
    return datetime.fromisoformat(match.group(1)).replace(tzinfo=UTC)


def _pr_outcome_regression_signals() -> list[Signal]:
    path = pr_outcomes_path()
    if not path.exists():
        return []
    data = _read_json(path)
    outcomes = data.get("outcomes") if isinstance(data, dict) else None
    if outcomes is None:
        return []
    if not isinstance(outcomes, list):
        msg = f"pr_outcomes: expected outcomes list at {path}"
        raise ValueError(msg)
    out: list[Signal] = []
    for row in outcomes:
        if not isinstance(row, dict):
            continue
        h24 = (row.get("outcomes") or {}).get("h24")
        if not isinstance(h24, dict) or h24.get("regressed") is not True:
            continue
        pr_number = row.get("pr_number")
        merged_at = _parse_dt(row.get("merged_at")) or _utcnow()
        out.append(
            Signal(
                source_signal="pr_outcome_regression",
                source_ref=f"outcome:pr_{pr_number}",
                title=_short_title(f"Investigate PR #{pr_number} outcome regression"),
                why_now=f"PR #{pr_number} is merged and its 24h outcome is marked regressed.",
                estimated_effort_days=2.0,
                estimated_impact="critical",
                observed_at=merged_at,
                stale_days=max((_utcnow() - merged_at).total_seconds() / 86400, 0),
            )
        )
    return out


def score_signal(signal: Signal) -> float:
    """Return a 0-100 composite priority score for a signal."""
    impact = _IMPACT_WEIGHTS[signal.estimated_impact]
    urgency = min(30.0, max(0.0, signal.stale_days))
    effort_discount = max(0.0, signal.estimated_effort_days - 5.0) * 10.0
    alignment = 20.0 if signal.objective_aligned else 0.0
    return round(min(100.0, max(0.0, impact + urgency - effort_discount + alignment)), 2)


def propose_candidates(top_n: int = 5) -> list[WorkstreamCandidate]:
    """Gather, score, dedupe, and return the top-N candidate workstreams."""
    now = _utcnow()
    seen: dict[tuple[SourceSignal, str], tuple[Signal, float]] = {}
    for signal in gather_signals():
        key = (signal.source_signal, signal.source_ref)
        score = score_signal(signal)
        current = seen.get(key)
        if current is None or score > current[1]:
            seen[key] = (signal, score)

    ranked = sorted(
        seen.values(),
        key=lambda row: (
            row[1],
            _IMPACT_WEIGHTS[row[0].estimated_impact],
            -row[0].estimated_effort_days,
        ),
        reverse=True,
    )[:top_n]
    date_prefix = now.strftime("%Y-%m-%d")
    return [
        WorkstreamCandidate(
            candidate_id=f"C-{date_prefix}-{idx:03d}",
            proposed_at=now,
            title=signal.title,
            why_now=signal.why_now,
            source_signal=signal.source_signal,
            source_ref=signal.source_ref,
            estimated_effort_days=signal.estimated_effort_days,
            estimated_impact=signal.estimated_impact,
            score=score,
            status="proposed",
            promoted_workstream_id=None,
        )
        for idx, (signal, score) in enumerate(ranked, start=1)
    ]


def record_candidates(candidates: list[WorkstreamCandidate]) -> None:
    """Persist current candidates with a locked atomic write.

    Candidates displaced from the active set after 14 days are moved to history.
    Recent displaced candidates stay active so founder decisions do not vanish
    before the review window closes.
    """
    path = candidates_file_path()
    now = _utcnow()

    def _mutate() -> None:
        existing = load_candidates_file()
        incoming_keys = {(c.source_signal, c.source_ref) for c in candidates}
        active: list[WorkstreamCandidate] = list(candidates)
        history = list(existing.history)
        active_ids = {c.candidate_id for c in active}
        for old in existing.candidates:
            old_key = (old.source_signal, old.source_ref)
            if old_key in incoming_keys:
                continue
            age = now - _normalise_dt(old.proposed_at)
            if age > _HISTORY_AFTER:
                history.append(old)
            elif old.candidate_id not in active_ids:
                active.append(old)
        file = WorkstreamCandidatesFile(
            generated_at=now,
            candidates=active,
            history=history,
        )
        _write_json_atomic(path, _candidate_dump(file))

    _with_file_lock(path, _mutate)


def promote_candidate(candidate_id: str) -> PromotionResult:
    """Promote a proposed candidate into ``workstreams.json`` and update its status."""
    candidates_path = candidates_file_path()

    def _mutate() -> PromotionResult:
        file = load_candidates_file()
        candidate = _find_candidate(file, candidate_id)
        if candidate.status != "proposed":
            msg = f"candidate {candidate_id} is not proposed"
            raise ValueError(msg)
        workstream = _append_workstream_for_candidate(candidate)
        promoted = candidate.model_copy(
            update={
                "status": "approved_to_workstream",
                "promoted_workstream_id": workstream["id"],
            }
        )
        file.candidates = [
            promoted if c.candidate_id == candidate_id else c for c in file.candidates
        ]
        _write_json_atomic(candidates_path, _candidate_dump(file))
        return PromotionResult(candidate=promoted, workstream=workstream)

    return _with_file_lock(candidates_path, _mutate)


def reject_candidate(candidate_id: str, founder_reason: str) -> WorkstreamCandidate:
    """Mark a proposed candidate rejected with the founder's reason."""
    if not founder_reason.strip():
        msg = "founder_reason is required"
        raise ValueError(msg)
    path = candidates_file_path()

    def _mutate() -> WorkstreamCandidate:
        file = load_candidates_file()
        candidate = _find_candidate(file, candidate_id)
        if candidate.status != "proposed":
            msg = f"candidate {candidate_id} is not proposed"
            raise ValueError(msg)
        rejected = candidate.model_copy(
            update={"status": "rejected", "founder_reason": founder_reason.strip()}
        )
        file.candidates = [
            rejected if c.candidate_id == candidate_id else c for c in file.candidates
        ]
        _write_json_atomic(path, _candidate_dump(file))
        return rejected

    return _with_file_lock(path, _mutate)


def _find_candidate(file: WorkstreamCandidatesFile, candidate_id: str) -> WorkstreamCandidate:
    for candidate in file.candidates:
        if candidate.candidate_id == candidate_id:
            return candidate
    msg = f"candidate {candidate_id} not found"
    raise KeyError(msg)


def _append_workstream_for_candidate(candidate: WorkstreamCandidate) -> dict[str, Any]:
    path = workstreams_json_path()
    raw = _read_json(path)
    if not isinstance(raw, dict) or not isinstance(raw.get("workstreams"), list):
        msg = f"workstreams: expected workstreams list at {path}"
        raise ValueError(msg)
    WorkstreamsFile.model_validate(raw)
    workstreams = raw["workstreams"]
    new_id = _next_workstream_id(workstreams, candidate.title)
    now = _utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    entry: dict[str, Any] = {
        "id": new_id,
        "title": candidate.title,
        "track": "G2",
        "priority": _next_free_priority(workstreams),
        "status": "pending",
        "percent_done": 0,
        "owner": "brain",
        "brief_tag": f"track:{_slug(new_id.removeprefix('WS-'))}",
        "blockers": [],
        "last_pr": None,
        "last_activity": now,
        "last_dispatched_at": None,
        "notes": f"Brain-proposed from {candidate.source_signal} ({candidate.source_ref}).",
        "estimated_pr_count": 1,
        "github_actions_workflow": "agent-sprint-runner",
        "related_plan": "brain_self_prioritization_phase_g2",
        "proposed_by_brain": True,
    }
    raw["workstreams"].append(entry)
    raw["updated"] = now
    WorkstreamsFile.model_validate(raw)
    _write_json_atomic(path, raw)
    invalidate_workstreams_cache()
    return entry


def _next_free_priority(workstreams: list[dict[str, Any]]) -> int:
    used = {w.get("priority") for w in workstreams if isinstance(w.get("priority"), int)}
    priority = 0
    while priority in used:
        priority += 1
    return priority


def _next_workstream_id(workstreams: list[dict[str, Any]], title: str) -> str:
    max_num = 0
    for workstream in workstreams:
        raw_id = str(workstream.get("id") or "")
        match = re.match(r"^WS-(\d{2,3})-", raw_id)
        if match:
            max_num = max(max_num, int(match.group(1)))
    return f"WS-{max_num + 1:02d}-{_slug(title)[:72].strip('-')}"


def _short_title(value: str) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= 100:
        return cleaned
    return cleaned[:97].rstrip() + "..."


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "workstream"
