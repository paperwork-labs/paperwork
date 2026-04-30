"""Cost monitor audit — monthly budget utilization vs ledger spend.

Flags vendors at or above 80% of configured monthly budget, or over 100%.

medallion: ops
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.schemas.audits import AuditFinding, AuditRun
from app.services import cost_monitor

_AUDIT_ID = "cost_monitor"


def run() -> AuditRun:
    now = datetime.now(tz=UTC)
    month = now.strftime("%Y-%m")
    alerts = cost_monitor.check_budget_alerts(month=month, approaching_threshold=0.8)
    findings: list[AuditFinding] = []

    for a in alerts:
        if a.status == "exceeded":
            findings.append(
                AuditFinding(
                    audit_id=_AUDIT_ID,
                    severity="warn",
                    title=f"Over monthly budget: {a.budget_key}",
                    detail=(
                        f"{a.vendor} spend ${a.spent_usd:.2f} exceeds budget ${a.budget_usd:.2f} "
                        f"({a.utilization * 100:.1f}%) for {month}."
                    ),
                    file_path="apis/brain/data/cost_ledger.json",
                    line=None,
                )
            )
        else:
            findings.append(
                AuditFinding(
                    audit_id=_AUDIT_ID,
                    severity="warn",
                    title=f"Approaching monthly budget: {a.budget_key}",
                    detail=(
                        f"{a.vendor} spend ${a.spent_usd:.2f} is {a.utilization * 100:.1f}% of "
                        f"budget ${a.budget_usd:.2f} for {month} (threshold 80%)."
                    ),
                    file_path="apis/brain/data/cost_ledger.json",
                    line=None,
                )
            )

    if not findings:
        findings.append(
            AuditFinding(
                audit_id=_AUDIT_ID,
                severity="info",
                title="Budget utilization within range",
                detail=f"No vendors over 80% of configured monthly budgets for {month}.",
                file_path=None,
                line=None,
            )
        )

    warn_n = len([f for f in findings if f.severity == "warn"])
    summary = (
        f"{_AUDIT_ID}: {warn_n} budget alert(s) for {month}."
        if warn_n
        else f"{_AUDIT_ID}: clean — no budget alerts for {month}."
    )
    return AuditRun(
        audit_id=_AUDIT_ID,
        ran_at=now,
        findings=findings,
        summary=summary,
        next_cadence="weekly",
    )
