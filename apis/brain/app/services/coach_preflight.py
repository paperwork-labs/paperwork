"""Coach preflight service — surfaces relevant procedural rules, recent incidents,
and cost predictions for Opus before non-trivial dispatches/merges.

medallion: ops
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from app.schemas.coach_preflight import (
    CoachPreflightRequest,
    CoachPreflightResponse,
    CostPredict,
    MatchedRule,
    RecentIncident,
)
from app.schemas.procedural_memory import ProceduralMemoryFile, ProceduralRule

logger = logging.getLogger(__name__)

_CONFIDENCE_SCORE: dict[str, float] = {"high": 3.0, "medium": 2.0, "low": 1.0}
_MUST_WORDS = {"must", "MUST", "never", "NEVER"}

# Cost per Vercel build-minute (approximate)
_VERCEL_BUILD_MIN_COST_USD = 0.005
_VERCEL_BUILD_MINS_PER_APP = 3.0


def _brain_data_dir() -> Path:
    repo_root = os.environ.get("REPO_ROOT")
    if repo_root:
        return Path(repo_root) / "apis" / "brain" / "data"
    return Path(__file__).parent.parent.parent / "data"


def _memory_path() -> Path:
    return _brain_data_dir() / "procedural_memory.yaml"


def _incidents_path() -> Path:
    return _brain_data_dir() / "incidents.json"


def _load_rules() -> tuple[list[ProceduralRule], bool, str | None]:
    """Load procedural rules.  Returns (rules, degraded, reason)."""
    path = _memory_path()
    try:
        raw = path.read_text(encoding="utf-8")
        data: dict[str, Any] = yaml.safe_load(raw)
        file = ProceduralMemoryFile.model_validate(data)
        return file.rules, False, None
    except FileNotFoundError:
        logger.warning("coach_preflight: procedural_memory.yaml not found at %s", path)
        return [], True, "procedural_memory.yaml not found"
    except Exception as exc:
        logger.warning("coach_preflight: failed to parse procedural_memory.yaml: %s", exc)
        return [], True, f"procedural_memory.yaml parse error: {exc}"


def _load_incidents() -> list[dict[str, Any]]:
    path = _incidents_path()
    if not path.exists():
        return []
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        # Handle envelope format: {"incidents": [...]}
        if isinstance(data, dict) and "incidents" in data:
            return list(data["incidents"])
        return []
    except Exception as exc:
        logger.warning("coach_preflight: could not read incidents.json: %s", exc)
        return []


def _path_keywords(file_path: str) -> list[str]:
    """Extract searchable keywords from a file path."""
    parts = file_path.replace("\\", "/").split("/")
    # Include the full path, each path segment, and the filename stem
    keywords = [file_path, *parts]
    # Also add parent path prefixes for broader matching
    for part in parts:
        if "." in part:
            keywords.append(part.rsplit(".", 1)[0])
    return [k.lower() for k in keywords if k]


def _action_type_scopes(action_type: str) -> set[str]:
    """Map action_type to the applies_to scopes that should match."""
    if action_type in ("merge", "dispatch"):
        return {"orchestrator", "cheap-agents", "brain-self-dispatch"}
    if action_type == "plan":
        return {"orchestrator", "brain-self-dispatch"}
    if action_type == "deploy":
        return {"orchestrator"}
    return set()


def _rule_matches(
    rule: ProceduralRule,
    req: CoachPreflightRequest,
    file_keywords: list[str],
) -> tuple[bool, float, float]:
    """Return (matched, confidence_score, specificity_score)."""
    conf_score = _CONFIDENCE_SCORE.get(rule.confidence, 1.0)
    action_scopes = _action_type_scopes(req.action_type)
    rule_scopes = set(rule.applies_to)

    # Persona match: check if any requested persona appears in the rule's when text
    persona_match = bool(req.personas and any(p.lower() in rule.when.lower() for p in req.personas))
    # Also check applies_to against requested personas (for agent-type persona names)
    persona_direct = any(p in rule.applies_to for p in req.personas)

    # Action-type scope match
    scope_match = bool(rule_scopes.intersection(action_scopes))

    # Path/keyword match against rule's when field
    rule_when_lower = rule.when.lower()
    path_match = any(kw in rule_when_lower for kw in file_keywords if kw)
    path_specificity = 0.0
    if path_match:
        # Higher specificity for longer matching keyword (more specific path)
        matching_kws = [kw for kw in file_keywords if kw and kw in rule_when_lower]
        path_specificity = max(len(kw) for kw in matching_kws) / 100.0

    matched = persona_match or persona_direct or scope_match or path_match
    specificity = (
        path_specificity + (0.5 if scope_match else 0.0) + (0.3 if persona_direct else 0.0)
    )

    return matched, conf_score, specificity


def _assign_severity(rule: ProceduralRule) -> str:
    """Assign severity based on confidence and must-clause presence."""
    if rule.confidence == "high":
        do_lower = rule.do.lower()
        if any(w in rule.do or w in do_lower for w in _MUST_WORDS):
            return "blocker"
        return "warning"
    if rule.confidence == "medium":
        return "warning"
    return "info"


def _match_rules(
    rules: list[ProceduralRule],
    req: CoachPreflightRequest,
) -> list[MatchedRule]:
    """Return top-10 matched rules sorted by (confidence x specificity) descending."""
    # Build keyword set from files_touched
    file_keywords: list[str] = []
    for f in req.files_touched:
        file_keywords.extend(_path_keywords(f))

    scored: list[tuple[float, ProceduralRule, str]] = []
    for rule in rules:
        matched, conf_score, specificity = _rule_matches(rule, req, file_keywords)
        if not matched:
            continue
        composite = conf_score * (1.0 + specificity)
        rationale_parts: list[str] = []
        if any(kw in rule.when.lower() for kw in file_keywords if kw):
            rationale_parts.append("path match")
        if any(p in rule.applies_to for p in req.personas):
            rationale_parts.append("persona match")
        if set(rule.applies_to).intersection(_action_type_scopes(req.action_type)):
            rationale_parts.append(f"action_type={req.action_type}")
        rationale = "; ".join(rationale_parts) if rationale_parts else "scope match"
        scored.append((composite, rule, rationale))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:10]

    results: list[MatchedRule] = []
    for _score, rule, rationale in top:
        severity = _assign_severity(rule)
        # Truncate fields to schema limits
        do_text = rule.do[:2000]
        when_text = rule.when[:1000]
        rationale_text = rationale[:500]
        results.append(
            MatchedRule(
                id=rule.id,
                confidence=rule.confidence,
                do=do_text,
                when=when_text,
                rationale=rationale_text,
                severity=severity,
            )
        )
    return results


def _filter_incidents(
    incidents: list[dict[str, Any]],
    files_touched: list[str],
) -> list[RecentIncident]:
    """Return incidents from the last 30 days whose related_files overlap files_touched."""
    cutoff = datetime.now(UTC) - timedelta(days=30)
    files_set = set(files_touched)
    results: list[RecentIncident] = []

    for inc in incidents:
        # Parse timestamp — try opened_at, then occurred_at, then learned_at
        raw_ts = inc.get("opened_at") or inc.get("occurred_at") or inc.get("learned_at")
        if raw_ts:
            try:
                ts_str = str(raw_ts).strip()
                if ts_str.endswith("Z"):
                    ts_str = ts_str[:-1] + "+00:00"
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                if ts < cutoff:
                    continue
            except Exception:
                pass  # include if we can't parse the timestamp

        related_files: list[str] = inc.get("related_files", []) or []
        if files_set and not set(related_files).intersection(files_set):
            continue

        incident_id = str(inc.get("incident_id") or inc.get("id") or "unknown")
        severity = str(inc.get("severity") or inc.get("kind") or "unknown")
        root_cause = inc.get("root_cause") or inc.get("notes")
        learned_at = str(raw_ts or "")

        results.append(
            RecentIncident(
                incident_id=incident_id,
                severity=severity,
                root_cause=root_cause,
                related_files=related_files,
                learned_at=learned_at,
            )
        )

    return results


def _predict_cost(req: CoachPreflightRequest) -> CostPredict:
    """Estimate Vercel build cost based on files_touched."""
    affected_apps: set[str] = set()
    for f in req.files_touched:
        parts = f.replace("\\", "/").split("/")
        if len(parts) >= 2 and parts[0] == "apps":
            affected_apps.add(parts[1])

    app_count = len(affected_apps)
    if app_count == 0:
        return CostPredict(note="No apps/* changes detected")

    builds = app_count
    build_mins = builds * _VERCEL_BUILD_MINS_PER_APP
    cost_usd = build_mins * _VERCEL_BUILD_MIN_COST_USD
    note = f"Affected apps: {', '.join(sorted(affected_apps))}"

    return CostPredict(
        vercel_builds_likely=builds,
        vercel_build_min_estimate=build_mins,
        agent_compute_estimate_usd=round(cost_usd, 4),
        note=note,
    )


def get_coach_preflight_for_task(
    task_description: str,
    persona_id: str,
) -> CoachPreflightResponse:
    """Autopilot helper — surfaces procedural rules + past PR outcomes for a task.

    Before dispatching any cheap-agent, Autopilot calls this to get:
    - Matched procedural rules from procedural_memory.yaml whose ``when`` field
      overlaps with the task description or persona_id.
    - Recent PR outcomes (from incidents.json) related to the task.
    - A cost prediction stub (no files_touched → no Vercel build estimate).

    This is a thin wrapper over ``run_preflight``; it constructs a
    ``CoachPreflightRequest`` from the task context so callers don't need to
    know the internal schema.

    Args:
        task_description: Free-text description of the work to be done.
        persona_id: Persona slug (e.g. "cpa", "ea", "portfolio-manager").

    Returns:
        CoachPreflightResponse with matched rules, recent incidents, and
        predicted cost.  May be degraded if procedural_memory.yaml is missing.

    Example:
        preflight = get_coach_preflight_for_task(
            task_description="Refactor TypeScript imports in packages/ui",
            persona_id="ea",
        )
        if any(r.severity == "blocker" for r in preflight.matched_rules):
            raise RuntimeError("Blocker rules matched — review before dispatch")
    """
    req = CoachPreflightRequest(
        action_type="dispatch",
        files_touched=[],
        personas=[persona_id],
        branch=None,
        pr_number=None,
        pr_path_globs=[],
    )

    response = run_preflight(req)

    # Supplement: also try matching by task description keywords so rules
    # whose ``when`` field mentions the task domain surface even when no
    # files_touched overlap.
    if not response.degraded:
        task_keywords = [
            w.lower()
            for w in task_description.replace("/", " ").replace("-", " ").split()
            if len(w) > 3
        ]
        if task_keywords:
            rules, _, _ = _load_rules()
            extra_req = CoachPreflightRequest(
                action_type="dispatch",
                files_touched=task_keywords,  # abuse files_touched for keyword matching
                personas=[persona_id],
            )
            from app.schemas.coach_preflight import MatchedRule as _MatchedRule
            extra_matched = _match_rules(rules, extra_req)
            existing_ids = {r.id for r in response.matched_rules}
            for rule in extra_matched:
                if rule.id not in existing_ids:
                    response.matched_rules.append(rule)
                    existing_ids.add(rule.id)

    return response


def run_preflight(req: CoachPreflightRequest) -> CoachPreflightResponse:
    """Main entry point — pure sync, O(n) over rules, no LLM calls."""
    rules, degraded, degraded_reason = _load_rules()

    if degraded:
        return CoachPreflightResponse(
            matched_rules=[],
            recent_incidents=[],
            predicted_cost=CostPredict(note=degraded_reason),
            degraded=True,
            degraded_reason=degraded_reason,
        )

    matched = _match_rules(rules, req)

    incidents_raw = _load_incidents()
    recent_incidents = _filter_incidents(incidents_raw, req.files_touched)

    predicted_cost = _predict_cost(req)

    warnings: list[str] = []
    blocker_count = sum(1 for r in matched if r.severity == "blocker")
    if blocker_count > 0:
        warnings.append(f"{blocker_count} blocker rule(s) matched — review before proceeding")

    return CoachPreflightResponse(
        matched_rules=matched,
        recent_incidents=recent_incidents,
        predicted_cost=predicted_cost,
        warnings=warnings,
        degraded=False,
        degraded_reason=None,
    )
