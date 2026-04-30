"""Audit registry service — Brain-owned adaptive cadence for 12 audits.

File-locked JSON stores live in apis/brain/data/:
  audit_registry.json   — AuditDef list (seeded once, founder-overridable)
  audit_runs.json       — capped 100 latest AuditRun records
  audit_cadence_log.json — CadenceAdjustment history

Adaptive cadence logic:
  - 4 consecutive clean (zero error/warn) weekly runs → relax one step
    (weekly→monthly, monthly→quarterly)
  - Any run with error/warn findings → tighten back to weekly
  - Manual overrides are logged with manual_override=True and respected
    (not overridden by auto-adjust)

medallion: ops
"""

from __future__ import annotations

import fcntl
import importlib
import json
import logging
import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.schemas.audits import (
    AuditCadence,
    AuditDef,
    AuditRun,
    CadenceAdjustment,
)

logger = logging.getLogger(__name__)

_MAX_RUNS = 100
_RELAX_AFTER_CLEAN_RUNS = 4

_CADENCE_RELAX: dict[AuditCadence, AuditCadence] = {
    "weekly": "monthly",
    "monthly": "quarterly",
    "quarterly": "quarterly",
}
_CADENCE_TIGHTEN: dict[AuditCadence, AuditCadence] = {
    "weekly": "weekly",
    "monthly": "weekly",
    "quarterly": "weekly",
}

_SEED_AUDITS: list[dict[str, Any]] = [
    {
        "id": "stack",
        "name": "Stack Modernity Audit",
        "cadence": "weekly",
        "runner_module": "app.audits.stack",
        "pillar": "stack_modernity",
        "enabled": True,
    },
    {
        "id": "runbook_completeness",
        "name": "Runbook Completeness Audit",
        "cadence": "weekly",
        "runner_module": "app.audits.runbook_completeness",
        "pillar": "knowledge_capital",
        "enabled": True,
    },
    {
        "id": "persona_coverage",
        "name": "Persona Coverage Audit",
        "cadence": "weekly",
        "runner_module": "app.audits.persona_coverage",
        "pillar": "persona_coverage",
        "enabled": True,
    },
    {
        "id": "docs_freshness",
        "name": "Docs Freshness Audit",
        "cadence": "weekly",
        "runner_module": "app.audits.docs_freshness",
        "pillar": "knowledge_capital",
        "enabled": True,
    },
    {
        "id": "cost",
        "name": "Cost Anomaly Audit",
        "cadence": "weekly",
        "runner_module": "app.audits.cost",
        "pillar": "autonomy",
        "enabled": True,
    },
    {
        "id": "secrets_drift",
        "name": "Secrets Drift Audit",
        "cadence": "weekly",
        "runner_module": "app.audits.secrets_drift",
        "pillar": "reliability_security",
        "enabled": True,
    },
    {
        "id": "kg_self_validate",
        "name": "Knowledge Graph Self-Validation Audit",
        "cadence": "weekly",
        "runner_module": "app.audits.kg_self_validate",
        "pillar": "knowledge_capital",
        "enabled": True,
    },
    {
        "id": "a11y",
        "name": "Accessibility (a11y) Audit",
        "cadence": "weekly",
        "runner_module": "app.audits.a11y",
        "pillar": "a11y_design_system",
        "enabled": True,
    },
    {
        "id": "lighthouse",
        "name": "Lighthouse Performance Audit",
        "cadence": "weekly",
        "runner_module": "app.audits.lighthouse",
        "pillar": "web_perf_ux",
        "enabled": True,
    },
    {
        "id": "vendor_renewal",
        "name": "Vendor Renewal Audit",
        "cadence": "weekly",
        "runner_module": "app.audits.vendor_renewal",
        "pillar": "reliability_security",
        "enabled": True,
    },
    {
        "id": "cross_app_ui_redundancy",
        "name": "Cross-App UI Redundancy Audit",
        "cadence": "weekly",
        "runner_module": "app.audits.cross_app_ui_redundancy",
        "pillar": "code_quality",
        "enabled": True,
    },
    {
        "id": "auto_distillation",
        "name": "Auto-Distillation (failure clusters to procedural rules)",
        "cadence": "weekly",
        "runner_module": "app.audits.auto_distillation",
        "pillar": "autonomy",
        "enabled": True,
    },
]


# ---------------------------------------------------------------------------
# Path helpers — follow medallion three-level traversal
# ---------------------------------------------------------------------------


def _brain_data_dir() -> Path:
    services_dir = Path(__file__).resolve().parent
    brain_app = services_dir.parent
    brain_root = brain_app.parent
    return brain_root / "data"


def _registry_path() -> Path:
    return _brain_data_dir() / "audit_registry.json"


def _runs_path() -> Path:
    return _brain_data_dir() / "audit_runs.json"


def _cadence_log_path() -> Path:
    return _brain_data_dir() / "audit_cadence_log.json"


# ---------------------------------------------------------------------------
# File-locked JSON helpers
# ---------------------------------------------------------------------------


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        with path.open("r", encoding="utf-8") as fh:
            fcntl.flock(fh, fcntl.LOCK_SH)
            try:
                return json.load(fh)
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
    except Exception:
        logger.exception("audits: failed to read %s", path)
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                json.dump(data, fh, indent=2, default=str)
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
        os.replace(tmp_path, path)
    except Exception:
        import contextlib

        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def _seed_registry() -> None:
    path = _registry_path()
    if path.is_file():
        return
    _write_json(path, _SEED_AUDITS)
    logger.info("audits: seeded audit_registry.json with %d audits", len(_SEED_AUDITS))


def load_registry() -> list[AuditDef]:
    _seed_registry()
    raw = _read_json(_registry_path(), _SEED_AUDITS)
    return [AuditDef.model_validate(r) for r in raw]


def _save_registry(defs: list[AuditDef]) -> None:
    _write_json(_registry_path(), [d.model_dump() for d in defs])


def get_audit_def(audit_id: str) -> AuditDef | None:
    for d in load_registry():
        if d.id == audit_id:
            return d
    return None


def set_audit_cadence(audit_id: str, cadence: AuditCadence, *, manual: bool = True) -> None:
    defs = load_registry()
    for d in defs:
        if d.id == audit_id:
            old = d.cadence
            d.cadence = cadence
            _save_registry(defs)
            adj = CadenceAdjustment(
                audit_id=audit_id,
                from_cadence=old,
                to_cadence=cadence,
                reason=(
                    "manual override via admin API" if manual else "auto-adjust by cadence engine"
                ),
                adjusted_at=datetime.now(tz=UTC),
                manual_override=manual,
            )
            _append_cadence_log(adj)
            return
    msg = f"audit not found: {audit_id}"
    raise ValueError(msg)


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


def load_runs() -> list[AuditRun]:
    raw = _read_json(_runs_path(), [])
    return [AuditRun.model_validate(r) for r in raw]


def _save_runs(runs: list[AuditRun]) -> None:
    trimmed = runs[-_MAX_RUNS:] if len(runs) > _MAX_RUNS else runs
    _write_json(_runs_path(), [r.model_dump() for r in trimmed])


def load_runs_for(audit_id: str) -> list[AuditRun]:
    return [r for r in load_runs() if r.audit_id == audit_id]


# ---------------------------------------------------------------------------
# Cadence log
# ---------------------------------------------------------------------------


def load_cadence_log() -> list[CadenceAdjustment]:
    raw = _read_json(_cadence_log_path(), [])
    return [CadenceAdjustment.model_validate(r) for r in raw]


def _append_cadence_log(adj: CadenceAdjustment) -> None:
    log = load_cadence_log()
    log.append(adj)
    _write_json(_cadence_log_path(), [a.model_dump() for a in log])


# ---------------------------------------------------------------------------
# Cadence evaluation
# ---------------------------------------------------------------------------


def _count_consecutive_clean_runs(runs: list[AuditRun]) -> int:
    """Count trailing runs (most-recent first) with no error/warn findings."""
    ordered = sorted(runs, key=lambda r: r.ran_at, reverse=True)
    count = 0
    for run in ordered:
        has_issue = any(f.severity in ("error", "warn") for f in run.findings)
        if has_issue:
            break
        count += 1
    return count


def _has_recent_manual_override(audit_id: str) -> bool:
    log = load_cadence_log()
    return any(adj.audit_id == audit_id and adj.manual_override for adj in reversed(log))


def evaluate_cadence_adjustment(audit_id: str) -> CadenceAdjustment | None:
    """Evaluate whether to relax or tighten cadence. Returns adjustment if changed."""
    defn = get_audit_def(audit_id)
    if defn is None:
        return None

    if _has_recent_manual_override(audit_id):
        logger.info("audits: skipping auto-adjust for %s (manual override active)", audit_id)
        return None

    runs = load_runs_for(audit_id)
    if not runs:
        return None

    latest = sorted(runs, key=lambda r: r.ran_at)[-1]
    has_latest_issue = any(f.severity in ("error", "warn") for f in latest.findings)

    if has_latest_issue:
        # Tighten immediately on any error/warn finding
        new_cadence = _CADENCE_TIGHTEN[defn.cadence]
        if new_cadence == defn.cadence:
            return None
        adj = CadenceAdjustment(
            audit_id=audit_id,
            from_cadence=defn.cadence,
            to_cadence=new_cadence,
            reason="findings detected → tightening to weekly",
            adjusted_at=datetime.now(tz=UTC),
            manual_override=False,
        )
    else:
        # Check for 4 consecutive clean runs
        clean_streak = _count_consecutive_clean_runs(runs)
        if clean_streak < _RELAX_AFTER_CLEAN_RUNS:
            return None
        new_cadence = _CADENCE_RELAX[defn.cadence]
        if new_cadence == defn.cadence:
            return None
        adj = CadenceAdjustment(
            audit_id=audit_id,
            from_cadence=defn.cadence,
            to_cadence=new_cadence,
            reason=f"0 findings x {clean_streak} consecutive runs -> relax to {new_cadence}",
            adjusted_at=datetime.now(tz=UTC),
            manual_override=False,
        )

    # Apply
    defs = load_registry()
    for d in defs:
        if d.id == audit_id:
            d.cadence = adj.to_cadence
            break
    _save_registry(defs)
    _append_cadence_log(adj)
    logger.info(
        "audits: cadence adjusted %s → %s for audit %s (%s)",
        adj.from_cadence,
        adj.to_cadence,
        audit_id,
        adj.reason,
    )
    return adj


# ---------------------------------------------------------------------------
# Run dispatch
# ---------------------------------------------------------------------------


def run_audit(audit_id: str) -> AuditRun:
    """Dynamically import runner module, call run(), persist result, evaluate cadence."""
    defn = get_audit_def(audit_id)
    if defn is None:
        msg = f"unknown audit: {audit_id}"
        raise ValueError(msg)

    try:
        mod = importlib.import_module(defn.runner_module)
    except ImportError as exc:
        msg = f"audit runner module not found: {defn.runner_module} — {exc}"
        raise RuntimeError(msg) from exc

    run_fn = getattr(mod, "run", None)
    if not callable(run_fn):
        msg = f"audit runner {defn.runner_module} must expose a callable run() function"
        raise RuntimeError(msg)

    result: AuditRun = run_fn()
    if not isinstance(result, AuditRun):
        msg = f"audit runner {defn.runner_module}.run() must return an AuditRun instance"
        raise RuntimeError(msg)

    runs = load_runs()
    runs.append(result)
    _save_runs(runs)
    evaluate_cadence_adjustment(audit_id)

    # Post high-severity findings immediately (PR E Conversations dependency)
    _handle_high_severity_findings(result)

    return result


def _handle_high_severity_findings(run: AuditRun) -> None:
    """Post error-severity findings immediately.

    DEPENDENCY: Conversations API (PR E). If PR E is not yet merged, findings
    are written to apis/brain/data/pending_audit_conversations.json for later
    ingestion by PR E's Conversations service.
    """
    high = [f for f in run.findings if f.severity == "error"]
    if not high:
        return
    pending_path = _brain_data_dir() / "pending_audit_conversations.json"
    existing = _read_json(pending_path, [])
    for finding in high:
        existing.append(
            {
                "source": "audit",
                "audit_id": run.audit_id,
                "ran_at": run.ran_at.isoformat(),
                "severity": finding.severity,
                "title": finding.title,
                "detail": finding.detail,
                "file_path": finding.file_path,
                "tag": f"audit-finding-{run.audit_id}",
                "urgency": "high",
            }
        )
    _write_json(pending_path, existing)
    logger.info(
        "audits: queued %d high-severity finding(s) for Conversations (pending PR E)", len(high)
    )


# ---------------------------------------------------------------------------
# Weekly digest
# ---------------------------------------------------------------------------


def weekly_audit_digest() -> dict[str, Any]:
    """Bundle all info-severity findings from past 7 days into a digest payload.

    DEPENDENCY: Conversations API (PR E). Digest is written to
    apis/brain/data/pending_audit_conversations.json with tag weekly-audit-digest.
    """
    cutoff = datetime.now(tz=UTC) - timedelta(days=7)
    all_runs = load_runs()
    recent_runs = [r for r in all_runs if r.ran_at >= cutoff]

    info_findings: list[dict[str, Any]] = []
    for run in recent_runs:
        for f in run.findings:
            if f.severity == "info":
                info_findings.append(
                    {
                        "audit_id": run.audit_id,
                        "ran_at": run.ran_at.isoformat(),
                        **f.model_dump(),
                    }
                )

    digest_payload = {
        "source": "audit_digest",
        "tag": "weekly-audit-digest",
        "urgency": "info",
        "period_start": cutoff.isoformat(),
        "period_end": datetime.now(tz=UTC).isoformat(),
        "finding_count": len(info_findings),
        "findings": info_findings,
        "summary": (
            f"Weekly audit digest: {len(info_findings)} info finding(s) "
            f"across {len(recent_runs)} audit run(s) in the past 7 days."
        ),
    }

    pending_path = _brain_data_dir() / "pending_audit_conversations.json"
    existing = _read_json(pending_path, [])
    existing.append(digest_payload)
    _write_json(pending_path, existing)

    logger.info(
        "audits: weekly digest queued (%d info findings, %d runs)",
        len(info_findings),
        len(recent_runs),
    )
    return digest_payload


# ---------------------------------------------------------------------------
# POS pillar: audit_freshness
# ---------------------------------------------------------------------------


def audit_freshness() -> tuple[float, bool, str]:
    """POS collector: % of enabled audits with a run within 1.5x their cadence period.

    Returns (score_0_to_100, measured, notes).
    """
    _CADENCE_HOURS: dict[AuditCadence, float] = {
        "weekly": 7 * 24,
        "monthly": 30 * 24,
        "quarterly": 91 * 24,
    }

    defs = load_registry()
    enabled = [d for d in defs if d.enabled]
    if not enabled:
        return (0.0, False, "no enabled audits")

    runs_by_id: dict[str, list[AuditRun]] = {}
    for run in load_runs():
        runs_by_id.setdefault(run.audit_id, []).append(run)

    now = datetime.now(tz=UTC)
    fresh_count = 0
    notes_parts: list[str] = []

    for defn in enabled:
        audit_runs = runs_by_id.get(defn.id, [])
        if not audit_runs:
            notes_parts.append(f"{defn.id}:never-run")
            continue
        latest_run = max(audit_runs, key=lambda r: r.ran_at)
        window_hours = _CADENCE_HOURS[defn.cadence] * 1.5
        elapsed_hours = (now - latest_run.ran_at).total_seconds() / 3600
        if elapsed_hours <= window_hours:
            fresh_count += 1
        else:
            notes_parts.append(f"{defn.id}:stale({elapsed_hours:.0f}h>{window_hours:.0f}h)")

    score = round(fresh_count / len(enabled) * 100, 2)
    stale_note = ("; stale: " + ", ".join(notes_parts)) if notes_parts else ""
    notes = f"{fresh_count}/{len(enabled)} audits fresh{stale_note}"
    return (score, True, notes)
