"""Runbook completeness audit — scans ``docs/runbooks/*.md`` for required sections
and frontmatter per the repo's canonical runbook shape.

medallion: ops
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal, cast

import yaml

from app.schemas.audits import AuditFinding, AuditRun
from app.schemas.conversation import ConversationCreate
from app.services.conversations import create_conversation

logger = logging.getLogger(__name__)

_AUDIT_ID = "runbook_completeness"

COMPLETENESS_ALERT_THRESHOLD = 80.0
_MAX_CONVERSATION_ATTEMPTS = 3

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Section groups: each tuple is (gap_slug_suffix, regex matching an H2 line).
_SECTION_GROUPS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "purpose-or-when-to-use",
        re.compile(r"(?m)^##\s+(Purpose|When to use)\s*$", re.IGNORECASE),
    ),
    (
        "prerequisites-or-inputs",
        re.compile(r"(?m)^##\s+(Prerequisites|Inputs)\s*$", re.IGNORECASE),
    ),
    ("steps-or-procedure", re.compile(r"(?m)^##\s+(Steps|Procedure)\s*$", re.IGNORECASE)),
    (
        "verification-or-success-criteria",
        re.compile(
            r"(?m)^##\s+(Verification|Success criteria)\s*$",
            re.IGNORECASE,
        ),
    ),
    ("rollback-or-recovery", re.compile(r"(?m)^##\s+(Rollback|Recovery)\s*$", re.IGNORECASE)),
)

_FM_BOUNDARY_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", re.DOTALL)

Severity = Literal["info", "warn", "error"]


@dataclass(frozen=True)
class RunbookGap:
    path: str
    gaps: list[str]


@dataclass(frozen=True)
class RunbookCompletenessReport:
    total: int
    complete: int
    completeness_pct: float
    per_doc: list[RunbookGap]


def _find_repo_root() -> Path:
    env = os.environ.get("BRAIN_RUNBOOK_REPO_ROOT", "").strip()
    if env:
        return Path(env).resolve()
    here = Path(__file__).resolve()
    for anc in here.parents:
        if (anc / "apps").is_dir() and (anc / "docs").is_dir():
            return anc
    msg = "runbook_completeness: could not locate repo root (expected parents with apps/ and docs/)"
    raise RuntimeError(msg)


def _split_frontmatter(text: str) -> tuple[str | None, str, bool]:
    """Returns (frontmatter_yaml_or_none, body_after_frontmatter, had_opening_delimiter)."""
    m = _FM_BOUNDARY_RE.match(text)
    if not m:
        return None, text, False
    return m.group(1), text[m.end() :], True


def _check_mapping_fields(fm: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    owner = fm.get("owner")
    if owner is None or (isinstance(owner, str) and not owner.strip()):
        gaps.append("missing-frontmatter-owner")
    elif not isinstance(owner, str):
        gaps.append("invalid-frontmatter-owner-type")

    lr = fm.get("last_reviewed")
    if lr is None or (isinstance(lr, str) and not lr.strip()):
        gaps.append("missing-frontmatter-last_reviewed")
    elif isinstance(lr, str):
        if not _ISO_DATE_RE.match(lr.strip()):
            gaps.append("invalid-frontmatter-last_reviewed-format")
    elif isinstance(lr, date):
        pass  # YAML parses YYYY-MM-DD as datetime.date (datetime is a date subclass)
    else:
        gaps.append("invalid-frontmatter-last_reviewed-type")

    dk = fm.get("doc_kind")
    if dk is None or (isinstance(dk, str) and not dk.strip()):
        gaps.append("missing-frontmatter-doc_kind")
    elif dk != "runbook":
        gaps.append("invalid-frontmatter-doc_kind-expected-runbook")

    return gaps


def _check_frontmatter_yaml(fm_yaml: str | None, had_fm_block: bool) -> list[str]:
    if not had_fm_block:
        return ["missing-frontmatter"]
    if fm_yaml is None or not str(fm_yaml).strip():
        return ["empty-frontmatter"]
    try:
        loaded = yaml.safe_load(fm_yaml)
    except yaml.YAMLError as exc:
        logger.error("runbook_completeness: YAML parse error in frontmatter: %s", exc)
        return [f"frontmatter-yaml-error:{exc}"]

    if not isinstance(loaded, dict):
        return ["frontmatter-not-a-mapping"]
    return _check_mapping_fields(cast("dict[str, Any]", loaded))


def _check_sections(body: str) -> list[str]:
    gaps: list[str] = []
    for slug_suffix, pattern in _SECTION_GROUPS:
        if not pattern.search(body):
            gaps.append(f"missing-section-{slug_suffix}")
    return gaps


def _check_runbook(_path: Path, text: str) -> list[str]:
    fm_yaml, body, had_fm = _split_frontmatter(text)
    gaps = _check_frontmatter_yaml(fm_yaml, had_fm)
    if any(g.startswith("frontmatter-yaml-error") for g in gaps):
        gaps.extend(_check_sections(body))
        return gaps
    gaps.extend(_check_sections(body))
    return gaps


def audit_runbooks(repo_root: Path) -> RunbookCompletenessReport:
    runbooks_dir = repo_root / "docs" / "runbooks"
    per_doc: list[RunbookGap] = []

    if not runbooks_dir.is_dir():
        return RunbookCompletenessReport(
            total=0,
            complete=0,
            completeness_pct=0.0,
            per_doc=[],
        )

    for runbook_path in sorted(runbooks_dir.glob("*.md")):
        if runbook_path.name.startswith("_"):
            continue
        rel = str(runbook_path.relative_to(repo_root))
        try:
            text = runbook_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.error("runbook_completeness: failed to read %s: %s", rel, exc)
            per_doc.append(RunbookGap(path=rel, gaps=[f"read-error:{exc}"]))
            continue
        try:
            gaps = _check_runbook(runbook_path, text)
        except Exception as exc:
            logger.exception("runbook_completeness: unexpected error checking %s", rel)
            per_doc.append(RunbookGap(path=rel, gaps=[f"check-error:{exc}"]))
            continue
        per_doc.append(RunbookGap(path=rel, gaps=gaps))

    total = len(per_doc)
    complete = sum(1 for d in per_doc if not d.gaps)
    pct = (complete / total) * 100.0 if total else 0.0
    return RunbookCompletenessReport(
        total=total,
        complete=complete,
        completeness_pct=pct,
        per_doc=per_doc,
    )


def _format_debt_body(report: RunbookCompletenessReport) -> str:
    lines: list[str] = [
        "**Space:** paperwork-labs",
        "",
        f"**Completeness:** {report.complete}/{report.total} runbooks "
        f"({report.completeness_pct:.1f}%).",
        "",
        "**Gaps (per file):**",
    ]
    for doc in report.per_doc:
        if not doc.gaps:
            continue
        lines.append(f"- [`{doc.path}`]({doc.path})")
        for g in doc.gaps:
            lines.append(f"  - {g}")
    return "\n".join(lines)


def _create_runbook_debt_conversation(report: RunbookCompletenessReport) -> None:
    title = f"Runbook completeness at {report.completeness_pct:.1f}%"
    body_md = _format_debt_body(report)
    create = ConversationCreate(
        title=title[:500],
        body_md=body_md,
        tags=["runbook-debt"],
        urgency="normal",
        persona="ea",
        needs_founder_action=True,
    )
    last_exc: BaseException | None = None
    for attempt in range(1, _MAX_CONVERSATION_ATTEMPTS + 1):
        try:
            create_conversation(create)
            logger.info(
                "runbook_completeness: opened debt conversation (attempt %s)",
                attempt,
            )
            return
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "runbook_completeness: create_conversation failed attempt %s/%s: %s",
                attempt,
                _MAX_CONVERSATION_ATTEMPTS,
                exc,
            )
    assert last_exc is not None
    raise last_exc


def _finding_severity_for_gaps(gaps: list[str]) -> Severity:
    for g in gaps:
        if g.startswith(("read-error:", "check-error:", "frontmatter-yaml-error")):
            return "error"
    return "warn"


def run() -> AuditRun:
    now = datetime.now(tz=UTC)
    findings: list[AuditFinding] = []

    try:
        repo_root = _find_repo_root()
    except RuntimeError as exc:
        findings.append(
            AuditFinding(
                audit_id=_AUDIT_ID,
                severity="error",
                title="Cannot locate repository root",
                detail=str(exc),
                file_path=None,
                line=None,
            )
        )
        return AuditRun(
            audit_id=_AUDIT_ID,
            ran_at=now,
            findings=findings,
            summary=f"{_AUDIT_ID}: failed — {exc}",
            next_cadence="weekly",
        )

    runbooks_dir = repo_root / "docs" / "runbooks"
    if not runbooks_dir.is_dir():
        findings.append(
            AuditFinding(
                audit_id=_AUDIT_ID,
                severity="error",
                title="docs/runbooks directory missing",
                detail="Expected docs/runbooks/ under repository root.",
                file_path="docs/runbooks",
                line=None,
            )
        )
        return AuditRun(
            audit_id=_AUDIT_ID,
            ran_at=now,
            findings=findings,
            summary=f"{_AUDIT_ID}: docs/runbooks directory missing.",
            next_cadence="weekly",
        )

    report = audit_runbooks(repo_root)

    if report.total == 0:
        findings.append(
            AuditFinding(
                audit_id=_AUDIT_ID,
                severity="warn",
                title="No runbooks found under docs/runbooks",
                detail="No *.md files (non-underscore) present to audit.",
                file_path="docs/runbooks",
                line=None,
            )
        )
        return AuditRun(
            audit_id=_AUDIT_ID,
            ran_at=now,
            findings=findings,
            summary=f"{_AUDIT_ID}: 0 runbooks.",
            next_cadence="weekly",
        )

    for doc in report.per_doc:
        if not doc.gaps:
            continue
        sev = _finding_severity_for_gaps(doc.gaps)
        findings.append(
            AuditFinding(
                audit_id=_AUDIT_ID,
                severity=sev,
                title=f"Runbook gaps: {doc.path}",
                detail="; ".join(doc.gaps),
                file_path=doc.path,
                line=None,
            )
        )

    if not any(d.gaps for d in report.per_doc):
        findings.append(
            AuditFinding(
                audit_id=_AUDIT_ID,
                severity="info",
                title="Runbook completeness clean",
                detail=(
                    f"{report.complete}/{report.total} runbooks pass "
                    f"({report.completeness_pct:.1f}%)."
                ),
                file_path=None,
                line=None,
            )
        )

    if report.completeness_pct < COMPLETENESS_ALERT_THRESHOLD and report.total > 0:
        try:
            _create_runbook_debt_conversation(report)
        except Exception as exc:
            logger.exception("runbook_completeness: failed to open debt conversation")
            findings.append(
                AuditFinding(
                    audit_id=_AUDIT_ID,
                    severity="error",
                    title="Failed to open runbook-debt conversation",
                    detail=str(exc),
                    file_path=None,
                    line=None,
                )
            )

    warn_n = sum(1 for f in findings if f.severity == "warn")
    err_n = sum(1 for f in findings if f.severity == "error")
    summary = (
        f"{_AUDIT_ID}: {report.complete}/{report.total} complete "
        f"({report.completeness_pct:.1f}%); {warn_n} warn, {err_n} error."
    )
    return AuditRun(
        audit_id=_AUDIT_ID,
        ran_at=now,
        findings=findings,
        summary=summary,
        next_cadence="weekly",
    )
