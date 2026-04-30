"""WS-67.E auto-distillation — cluster PR/dispatch failures and stage procedural rules.

Clusters repeated failure patterns (agent model x workstream type x error category)
from ``pr_outcomes.json`` and ``agent_dispatch_log.json``. When a cluster reaches
the occurrence threshold, emits candidate rules to ``proposed_rules.yaml`` for
founder review (not merged into ``procedural_memory.yaml`` automatically).

medallion: ops
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ValidationError

from app.schemas.procedural_memory import ProceduralMemoryFile, ProceduralRule
from app.services import procedural_memory as procedural_memory_svc

logger = logging.getLogger(__name__)

_MIN_CLUSTER_SIZE = 3

ErrorCategory = Literal["ci_failure", "merge_conflict", "review_rejection"]

_BRAIN_DATA_PARTS = ("apis", "brain", "data")


@dataclass(frozen=True)
class FailureCluster:
    """A group of failures sharing model, workstream type, category, and pattern."""

    agent_model: str
    workstream_type: str
    error_category: ErrorCategory
    ci_failure_type: str
    failure_pattern_norm: str
    count: int
    pr_numbers: tuple[int, ...] = field(default_factory=tuple)
    dispatch_ids: tuple[str, ...] = field(default_factory=tuple)


class ProposedRule(BaseModel):
    """Wrapper for a staged procedural rule candidate."""

    rule: ProceduralRule
    cluster_size: int


def _brain_data_dir() -> Path:
    repo_root = os.environ.get("REPO_ROOT", "").strip()
    if repo_root:
        return Path(repo_root).joinpath(*_BRAIN_DATA_PARTS)
    services_dir = Path(__file__).resolve().parent
    brain_root = services_dir.parent.parent
    return brain_root / "data"


def _pr_outcomes_path() -> Path:
    env = os.environ.get("BRAIN_PR_OUTCOMES_JSON", "").strip()
    if env:
        return Path(env)
    return _brain_data_dir() / "pr_outcomes.json"


def _dispatch_log_path() -> Path:
    env = os.environ.get("BRAIN_AGENT_DISPATCH_LOG_JSON", "").strip()
    if env:
        return Path(env)
    return _brain_data_dir() / "agent_dispatch_log.json"


def proposed_rules_path() -> Path:
    """Path to staged rules YAML (founder approval queue)."""
    return _brain_data_dir() / "proposed_rules.yaml"


def load_outcomes_rows(path: Path | None = None) -> list[dict[str, Any]]:
    """Load ``outcomes`` list from pr_outcomes.json (raw dict rows)."""
    p = path or _pr_outcomes_path()
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and isinstance(raw.get("outcomes"), list):
            return [r for r in raw["outcomes"] if isinstance(r, dict)]
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("auto_distillation: unreadable pr_outcomes — %s", exc)
    return []


def load_dispatch_rows(path: Path | None = None) -> list[dict[str, Any]]:
    """Load ``dispatches`` list from agent_dispatch_log.json."""
    p = path or _dispatch_log_path()
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and isinstance(raw.get("dispatches"), list):
            return [d for d in raw["dispatches"] if isinstance(d, dict)]
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("auto_distillation: unreadable dispatch log — %s", exc)
    return []


def _normalize_pattern(text: str) -> str:
    s = re.sub(r"\s+", " ", text.lower().strip())
    return s[:120] if s else "empty_summary"


def _infer_ci_failure_type(task_summary: str, explicit: str | None) -> str:
    if explicit and str(explicit).strip():
        return str(explicit).strip().lower().replace(" ", "_")[:48]
    s = task_summary.lower()
    for name in ("ruff", "mypy", "pytest", "eslint", "tsc", "format"):
        if name in s:
            return name
    if "ci" in s or "github actions" in s or "workflow" in s:
        return "ci_unspecified"
    return "unspecified"


_MERGE_CONFLICT_PATTERNS = (
    "merge conflict",
    "merge_conflicts",
    "could not merge",
    "conflicts in",
    "rebase conflict",
)


def _merge_conflict_hint(task_summary: str, outcome: dict[str, Any]) -> bool:
    if outcome.get("merge_conflict") is True:
        return True
    if str(outcome.get("failure_kind") or "").lower() in {"merge_conflict", "merge-conflict"}:
        return True
    low = task_summary.lower()
    return any(p in low for p in _MERGE_CONFLICT_PATTERNS)


@dataclass
class _FailureAcc:
    event_count: int = 0
    pr_numbers: set[int] = field(default_factory=set)
    dispatch_ids: set[str] = field(default_factory=set)


def _buckets_key(
    agent_model: str,
    workstream_type: str,
    error_category: ErrorCategory,
    ci_failure_type: str,
    pattern: str,
) -> tuple[str, str, str, str, str]:
    return (agent_model, workstream_type, error_category, ci_failure_type, pattern)


def cluster_failures(
    outcomes: list[dict[str, Any]],
    dispatch_log: list[dict[str, Any]],
) -> list[FailureCluster]:
    """Group failure events that share model, workstream type, category, and pattern."""
    buckets: dict[tuple[str, str, str, str, str], _FailureAcc] = defaultdict(_FailureAcc)

    for d in dispatch_log:
        oc_raw = d.get("outcome")
        oc: dict[str, Any] = oc_raw if isinstance(oc_raw, dict) else {}
        task_summary = str(d.get("task_summary") or "")
        agent_model = str(d.get("agent_model") or "unknown")
        workstream_type = str(d.get("workstream_type") or "unknown")
        pattern = _normalize_pattern(task_summary)
        explicit_ci = oc.get("ci_failure_type")
        ci_ft = explicit_ci if isinstance(explicit_ci, str) else None

        pr_raw = d.get("pr_number")
        pr_num: int | None = pr_raw if isinstance(pr_raw, int) else None
        dispatch_id = str(d.get("dispatch_id") or "")

        category: ErrorCategory | None = None
        ci_type = ""

        if _merge_conflict_hint(task_summary, oc):
            category = "merge_conflict"
        elif oc.get("review_pass") is False:
            category = "review_rejection"
        elif oc.get("ci_initial_pass") is False:
            category = "ci_failure"
            ci_type = _infer_ci_failure_type(task_summary, ci_ft)

        if category is None:
            continue

        if category != "ci_failure":
            ci_type = ""

        key = _buckets_key(agent_model, workstream_type, category, ci_type, pattern)
        acc = buckets[key]
        acc.event_count += 1
        if pr_num is not None:
            acc.pr_numbers.add(pr_num)
        if dispatch_id:
            acc.dispatch_ids.add(dispatch_id)

    covered_pr_ci: set[int] = set()
    for d in dispatch_log:
        oc2_raw = d.get("outcome")
        oc2: dict[str, Any] = oc2_raw if isinstance(oc2_raw, dict) else {}
        if oc2.get("ci_initial_pass") is False:
            pr_raw = d.get("pr_number")
            if isinstance(pr_raw, int):
                covered_pr_ci.add(pr_raw)

    for row in outcomes:
        pr_raw = row.get("pr_number")
        if not isinstance(pr_raw, int):
            continue
        h1 = row.get("h1")
        if not isinstance(h1, dict) or h1.get("ci_pass") is not False:
            continue
        if pr_raw in covered_pr_ci:
            continue
        agent_model = str(row.get("agent_model") or "unknown")
        ws_types = row.get("workstream_types")
        ws_type = str(ws_types[0]) if isinstance(ws_types, list) and ws_types else "unknown"
        key = _buckets_key(agent_model, ws_type, "ci_failure", "post_merge_h1", "h1_ci_regression")
        acc = buckets[key]
        acc.event_count += 1
        acc.pr_numbers.add(pr_raw)

    clusters: list[FailureCluster] = []
    for (am, wt, ec, cit, ptn), acc in buckets.items():
        if acc.event_count < _MIN_CLUSTER_SIZE:
            continue
        clusters.append(
            FailureCluster(
                agent_model=am,
                workstream_type=wt,
                error_category=ec,  # type: ignore[arg-type]
                ci_failure_type=cit,
                failure_pattern_norm=ptn,
                count=acc.event_count,
                pr_numbers=tuple(sorted(acc.pr_numbers)),
                dispatch_ids=tuple(sorted(acc.dispatch_ids)),
            )
        )

    return sorted(clusters, key=lambda c: (-c.count, c.agent_model, c.workstream_type))


def _cluster_rule_id(cluster: FailureCluster) -> str:
    payload = "|".join(
        (
            cluster.agent_model,
            cluster.workstream_type,
            cluster.error_category,
            cluster.ci_failure_type,
            cluster.failure_pattern_norm,
        )
    )
    digest = hashlib.sha256(payload.encode()).hexdigest()[:10]
    return f"auto_distill_{cluster.error_category}_{digest}"


def _rule_body_for_cluster(cluster: FailureCluster) -> tuple[str, str]:
    ci_part = f"; CI signal: {cluster.ci_failure_type}" if cluster.ci_failure_type else ""
    when = (
        f"Repeated {cluster.error_category.replace('_', ' ')} for agent_model="
        f"{cluster.agent_model!r}, workstream_type={cluster.workstream_type!r}"
        f"{ci_part}; pattern~{cluster.failure_pattern_norm!r} "
        f"({cluster.count} occurrences in cluster window)."
    )
    if cluster.error_category == "ci_failure":
        do = (
            "Before push, run CI-parity checks locally for the touched packages "
            "(e.g. ruff format --check, ruff check, mypy, pytest); fix failures "
            "before re-opening or updating the PR."
        )
    elif cluster.error_category == "merge_conflict":
        do = (
            "For parallel agents, use isolated worktrees; rebase early and resolve "
            "conflicts before push. Serialize edits to hot shared files when isolation "
            "is not possible."
        )
    else:
        do = (
            "Apply orchestrator diff-review checklist before merge; batch review "
            "feedback to reduce rejection rounds."
        )
    return when, do


def propose_rules(clusters: list[FailureCluster]) -> list[ProposedRule]:
    """Turn clusters into procedural rule candidates, skipping duplicates in memory."""
    try:
        existing = procedural_memory_svc.load_rules()
    except (FileNotFoundError, OSError, ValidationError) as exc:
        logger.info("auto_distillation: no/failed procedural_memory (%s) — empty existing", exc)
        existing = []
    existing_ids = {r.id for r in existing}
    existing_when = {r.when.strip().lower() for r in existing}

    proposed: list[ProposedRule] = []
    for cluster in clusters:
        if cluster.count < _MIN_CLUSTER_SIZE:
            continue
        rule_id = _cluster_rule_id(cluster)
        when, do = _rule_body_for_cluster(cluster)
        when_l = when.strip().lower()
        if rule_id in existing_ids or when_l in existing_when:
            continue
        source = (
            "WS-67.E auto-distillation — "
            f"{cluster.count} similar failures "
            f"(model={cluster.agent_model}, ws={cluster.workstream_type}, "
            f"category={cluster.error_category})"
        )
        rule = ProceduralRule(
            id=rule_id,
            when=when,
            do=do,
            source=source,
            learned_at=datetime.now(tz=UTC),
            confidence="medium",
            applies_to=["cheap-agents", "brain-self-dispatch"],
        )
        proposed.append(ProposedRule(rule=rule, cluster_size=cluster.count))

    return proposed


def _rules_to_yaml_dict(rules: list[ProceduralRule]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for rule in rules:
        rows.append(
            {
                "id": rule.id,
                "when": rule.when,
                "do": rule.do,
                "source": rule.source,
                "learned_at": rule.learned_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "confidence": rule.confidence,
                "applies_to": list(rule.applies_to),
            }
        )
    return {"version": 1, "rules": rows}


def write_proposed_rules(rules: list[ProposedRule], path: Path | None = None) -> int:
    """Merge *rules* into ``proposed_rules.yaml`` by rule id and atomically write.

    Returns number of new or updated staged rules written in this call (merged file
    total may include prior entries).
    """
    if not rules:
        return 0
    target = path or proposed_rules_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    prior_rules: list[ProceduralRule] = []
    if target.is_file():
        try:
            raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
            file = ProceduralMemoryFile.model_validate(raw)
            prior_rules = list(file.rules)
        except (OSError, ValidationError, yaml.YAMLError) as exc:
            logger.warning("auto_distillation: resetting proposed_rules — %s", exc)
            prior_rules = []

    by_id: dict[str, ProceduralRule] = {r.id: r for r in prior_rules}
    prior_ids = {r.id for r in prior_rules}
    batch_ids = {pr.rule.id for pr in rules}
    added = len(batch_ids - prior_ids)
    for pr in rules:
        by_id[pr.rule.id] = pr.rule

    merged = ProceduralMemoryFile(version=1, rules=list(by_id.values()))
    payload = _rules_to_yaml_dict(merged.rules)

    fd, tmp_path = tempfile.mkstemp(dir=target.parent, suffix=".yaml.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            yaml.dump(
                payload,
                fh,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
        os.replace(tmp_path, target)
    except Exception:
        import contextlib

        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise

    return added


def load_proposed_rules(path: Path | None = None) -> ProceduralMemoryFile:
    """Read and validate ``proposed_rules.yaml``."""
    target = path or proposed_rules_path()
    if not target.is_file():
        return ProceduralMemoryFile(version=1, rules=[])
    raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    return ProceduralMemoryFile.model_validate(raw)


def run_distillation(
    *,
    outcomes_path: Path | None = None,
    dispatch_path: Path | None = None,
    proposed_path: Path | None = None,
) -> tuple[int, list[ProposedRule]]:
    """Load logs, cluster, propose, and write proposed rules. Returns (written_count, proposals)."""
    target_proposed = proposed_path or proposed_rules_path()
    outcomes = load_outcomes_rows(outcomes_path) if outcomes_path else load_outcomes_rows()
    dispatches = load_dispatch_rows(dispatch_path) if dispatch_path else load_dispatch_rows()
    clusters = cluster_failures(outcomes, dispatches)
    proposals = propose_rules(clusters)
    already = load_proposed_rules(target_proposed)
    staged_ids = {r.id for r in already.rules}
    fresh = [p for p in proposals if p.rule.id not in staged_ids]
    written = write_proposed_rules(fresh, path=target_proposed) if fresh else 0
    return written, fresh
