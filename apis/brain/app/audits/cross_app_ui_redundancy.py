"""Cross-app UI redundancy audit runner — AST-based read-only component scan.

Walks apps/*/src/components/ and packages/ui/src/components/ for component
definitions with common structural patterns (Tabs, Page, *Shell, FilterChip, etc.).
Also flags `apps/*/src/components/ui/*.tsx` files whose basename matches a
top-level primitive in `packages/ui` (migration candidates).
Compares name similarity and prop/tailwind density across apps.

If ≥3 warn-severity findings persist for 4 consecutive runs, this runner writes
a proposal to apis/brain/data/long_tail.json for a PR to extract the shared
pattern into @paperwork-labs/ui.

SAFETY: read-only AST walk — never renames, deletes, or modifies any source file.

medallion: ops
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import re
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas.audits import AuditFinding, AuditRun

logger = logging.getLogger(__name__)

_AUDIT_ID = "cross_app_ui_redundancy"

_PATTERN_NAMES = re.compile(
    r"^(Tabs|Tab|Page|.*Shell|FilterChip|.*Filter|.*Layout|.*Panel|.*Card|.*Modal|.*Dialog)$",
    re.IGNORECASE,
)
_TAILWIND_RE = re.compile(r'(?:className|class)=["\']([^"\']+)["\']')

# Threshold for long_tail proposal: >=3 warn findings x 4 consecutive runs
_WARN_THRESHOLD = 3
_CONSECUTIVE_RUNS_THRESHOLD = 4


def _find_repo_root() -> Path | None:
    here = Path(__file__).resolve()
    for anc in here.parents:
        if (anc / "apps").is_dir() and (anc / "packages").is_dir():
            return anc
    return None


def _brain_data_dir() -> Path:
    services_dir = Path(__file__).resolve().parent.parent / "services"
    brain_app = services_dir.parent
    brain_root = brain_app.parent
    return brain_root / "data"


def _extract_component_names_from_file(path: Path) -> list[str]:
    """Return top-level React component names from a TSX/JSX/TS/JS file."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    names: list[str] = []

    # Named exports: export function Foo / export const Foo = / export default function Foo
    export_fn = re.findall(r"export\s+(?:default\s+)?function\s+([A-Z][A-Za-z0-9_]*)", source)
    names.extend(export_fn)

    export_const = re.findall(r"export\s+const\s+([A-Z][A-Za-z0-9_]*)\s*[=:]", source)
    names.extend(export_const)

    return list(dict.fromkeys(names))  # deduplicate, preserve order


def _tailwind_density(path: Path) -> int:
    """Count distinct tailwind class tokens in file."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    classes: set[str] = set()
    for match in _TAILWIND_RE.finditer(source):
        classes.update(match.group(1).split())
    return len(classes)


def _collect_ui_primitive_basenames(pkg_components: Path) -> dict[str, list[str]]:
    """Map lowercase filename → paths under packages/ui/src/components/*.tsx (non-recursive)."""
    basenames: dict[str, list[str]] = defaultdict(list)
    if not pkg_components.is_dir():
        return dict(basenames)
    for path in sorted(pkg_components.glob("*.tsx")):
        basenames[path.name.lower()].append(str(path))
    return dict(basenames)


def _primitive_overlap_findings(repo_root: Path, audit_id: str) -> list[AuditFinding]:
    """Flag apps/*/src/components/ui/*.tsx whose basename matches packages/ui primitives."""
    pkg_basenames = _collect_ui_primitive_basenames(repo_root / "packages" / "ui" / "src" / "components")
    findings: list[AuditFinding] = []
    apps_dir = repo_root / "apps"
    if not apps_dir.is_dir():
        return findings

    for app_dir in sorted(apps_dir.iterdir()):
        local_ui = app_dir / "src" / "components" / "ui"
        if not local_ui.is_dir():
            continue
        for path in sorted(local_ui.glob("*.tsx")):
            key = path.name.lower()
            if key not in pkg_basenames:
                continue
            ui_refs = pkg_basenames[key]
            findings.append(
                AuditFinding(
                    audit_id=audit_id,
                    severity="info",
                    title=f"Local UI primitive overlaps packages/ui: {path.name}",
                    detail=(
                        f"`apps/{app_dir.name}/src/components/ui/{path.name}` shares a basename with "
                        f"@paperwork-labs/ui ({'; '.join(ui_refs[:2])}). "
                        "Candidate for consolidation when styling and behavior align."
                    ),
                    file_path=str(path),
                    line=None,
                )
            )
    return findings


def _collect_components(root: Path) -> dict[str, list[dict[str, Any]]]:
    """Map component_name → list of occurrences {app, file, tailwind_density}."""
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)

    scan_dirs: list[tuple[str, Path]] = []

    apps_dir = root / "apps"
    if apps_dir.is_dir():
        for app_dir in sorted(apps_dir.iterdir()):
            comp_dir = app_dir / "src" / "components"
            if comp_dir.is_dir():
                scan_dirs.append((app_dir.name, comp_dir))

    pkg_ui = root / "packages" / "ui" / "src" / "components"
    if pkg_ui.is_dir():
        scan_dirs.append(("@paperwork-labs/ui", pkg_ui))

    for app_name, comp_dir in scan_dirs:
        for path in sorted(comp_dir.rglob("*")):
            if path.suffix not in (".tsx", ".jsx", ".ts", ".js"):
                continue
            name_lower = path.name.lower()
            if path.name.startswith("_") or "test" in name_lower or "spec" in name_lower:
                continue
            names = _extract_component_names_from_file(path)
            density = _tailwind_density(path)
            for name in names:
                result[name].append(
                    {
                        "app": app_name,
                        "file": str(path),
                        "tailwind_density": density,
                    }
                )

    return dict(result)


def _write_long_tail_proposal(_warn_count: int) -> None:
    path = _brain_data_dir() / "long_tail.json"
    try:
        if path.is_file():
            with path.open("r", encoding="utf-8") as fh:
                fcntl.flock(fh, fcntl.LOCK_SH)
                existing = json.load(fh)
                fcntl.flock(fh, fcntl.LOCK_UN)
        else:
            existing = []

        entry_id = "cross_app_ui_pattern_extraction_threshold_two"
        for item in existing:
            if isinstance(item, dict) and item.get("id") == entry_id:
                return  # already proposed

        existing.append(
            {
                "id": entry_id,
                "source": _AUDIT_ID,
                "created_at": datetime.now(tz=UTC).isoformat(),
                "title": "Extract repeated cross-app UI patterns into @paperwork-labs/ui",
                "detail": (
                    f"cross_app_ui_redundancy audit found >={_WARN_THRESHOLD} warn findings "
                    f"for {_CONSECUTIVE_RUNS_THRESHOLD} consecutive runs. "
                    "Propose PR to extract shared component patterns "
                    "(Tabs, Shell, FilterChip, etc.) into packages/ui."
                ),
                "priority": "medium",
                "procedural_rule": entry_id,
            }
        )

        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            json.dump(existing, fh, indent=2, default=str)
            fcntl.flock(fh, fcntl.LOCK_UN)
        os.replace(tmp_path, path)
        logger.info("audits: wrote long_tail proposal %s", entry_id)
    except Exception:
        logger.exception("audits: failed to write long_tail proposal")


def _check_consecutive_warn_threshold(current_warn_count: int) -> bool:
    """Returns True if ≥3 warn findings persisted for 4+ consecutive runs."""
    from app.services.audits import load_runs_for

    past_runs = load_runs_for(_AUDIT_ID)
    if len(past_runs) < _CONSECUTIVE_RUNS_THRESHOLD - 1:
        return False
    limit = _CONSECUTIVE_RUNS_THRESHOLD - 1
    recent = sorted(past_runs, key=lambda r: r.ran_at, reverse=True)[:limit]
    for r in recent:
        w = sum(1 for f in r.findings if f.severity == "warn")
        if w < _WARN_THRESHOLD:
            return False
    return current_warn_count >= _WARN_THRESHOLD


def run() -> AuditRun:
    now = datetime.now(tz=UTC)
    findings: list[AuditFinding] = []

    root = _find_repo_root()
    if root is None:
        findings.append(
            AuditFinding(
                audit_id=_AUDIT_ID,
                severity="warn",
                title="Cannot locate repo root",
                detail="Could not find repo root (expected apps/ and packages/ dirs).",
                file_path=None,
                line=None,
            )
        )
        return AuditRun(
            audit_id=_AUDIT_ID,
            ran_at=now,
            findings=findings,
            summary="cross_app_ui_redundancy: repo root not found.",
            next_cadence="weekly",
        )

    components = _collect_components(root)

    findings.extend(_primitive_overlap_findings(root, _AUDIT_ID))

    # Find components in >=2 apps (excluding @paperwork-labs/ui, which is expected)
    for name, occurrences in sorted(components.items()):
        apps_present = {o["app"] for o in occurrences}
        # If present in @paperwork-labs/ui and at least one app → expected (already extracted)
        if "@paperwork-labs/ui" in apps_present:
            continue
        # If present in ≥2 non-ui apps AND matches known pattern names
        if len(apps_present) >= 2 and _PATTERN_NAMES.match(name):
            avg_density = (
                sum(o["tailwind_density"] for o in occurrences) / len(occurrences)
                if occurrences
                else 0
            )
            files = ", ".join(o["file"] for o in occurrences[:3])
            findings.append(
                AuditFinding(
                    audit_id=_AUDIT_ID,
                    severity="warn",
                    title=f"Duplicate component pattern: {name}",
                    detail=(
                        f"Component '{name}' found in {len(apps_present)} apps "
                        f"({', '.join(sorted(apps_present))}). "
                        f"avg tailwind_density={avg_density:.0f}. "
                        f"Files: {files}"
                    ),
                    file_path=occurrences[0]["file"] if occurrences else None,
                    line=None,
                )
            )

    warn_count = sum(1 for f in findings if f.severity == "warn")
    has_primitive_overlap = any(
        f.title.startswith("Local UI primitive overlaps") for f in findings
    )
    if warn_count == 0 and not has_primitive_overlap:
        findings.append(
            AuditFinding(
                audit_id=_AUDIT_ID,
                severity="info",
                title="No cross-app UI redundancy detected",
                detail="All matched patterns already in @paperwork-labs/ui or are unique.",
                file_path=None,
                line=None,
            )
        )

    # Check if proposal threshold hit
    if _check_consecutive_warn_threshold(warn_count):
        _write_long_tail_proposal(warn_count)

    overlap_info = sum(
        1 for f in findings if f.title.startswith("Local UI primitive overlaps")
    )
    next_cadence = "weekly"
    summary = (
        f"cross_app_ui_redundancy: {warn_count} duplicate-pattern warn(s), "
        f"{overlap_info} packages/ui basename overlap(s); "
        f"{len(components)} component name(s) scanned."
    )
    return AuditRun(
        audit_id=_AUDIT_ID,
        ran_at=now,
        findings=findings,
        summary=summary,
        next_cadence=next_cadence,
    )
