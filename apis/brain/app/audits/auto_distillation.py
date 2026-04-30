"""Auto-distillation audit — failure clusters → staged procedural_memory rules (WS-67.E).

Runs :func:`app.services.auto_distillation.run_distillation` and records an
``AuditRun`` with info-level findings for each staged proposal.

medallion: ops
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.schemas.audits import AuditFinding, AuditRun
from app.services.auto_distillation import run_distillation

_AUDIT_ID = "auto_distillation"


def run() -> AuditRun:
    now = datetime.now(tz=UTC)
    _written, proposals = run_distillation()
    findings: list[AuditFinding] = []
    for p in proposals:
        findings.append(
            AuditFinding(
                audit_id=_AUDIT_ID,
                severity="info",
                title=f"Staged procedural rule candidate: {p.rule.id}",
                detail=p.rule.when[:2000],
                file_path="apis/brain/data/proposed_rules.yaml",
                line=None,
            )
        )
    if not findings:
        findings.append(
            AuditFinding(
                audit_id=_AUDIT_ID,
                severity="info",
                title="No new failure clusters above threshold",
                detail=(
                    "Fewer than three matching failures per cluster, or all candidates "
                    "already exist in procedural_memory.yaml."
                ),
                file_path=None,
                line=None,
            )
        )
    summary = (
        f"{_AUDIT_ID}: staged {len(proposals)} proposed rule(s) "
        f"({_written} new id(s) in proposed_rules.yaml this run)."
    )
    return AuditRun(
        audit_id=_AUDIT_ID,
        ran_at=now,
        findings=findings,
        summary=summary,
        next_cadence="weekly",
    )
