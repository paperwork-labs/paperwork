"""Code quality pillar — coverage, mypy, ruff, cyclomatic complexity (AST).

medallion: ops
"""

from __future__ import annotations

import ast
import json
import math
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_BOOTSTRAP = (75.0, False, "tooling unavailable")

_SCHEMA = "code_quality_metrics/v1"


def _monorepo_root() -> Path:
    env = os.environ.get("BRAIN_REPO_ROOT", "").strip()
    if env:
        return Path(env)
    from app.utils.paths import repo_root

    return repo_root()


def _brain_dir() -> Path:
    """Path to ``apis/brain`` (package root containing ``app/``)."""
    env = os.environ.get("BRAIN_PACKAGE_ROOT", "").strip()
    if env:
        return Path(env)
    from app.utils.paths import brain_root

    return brain_root()


def _run(
    cmd: list[str],
    cwd: Path,
    *,
    timeout: float = 600,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _read_coverage_pct(coverage_xml: Path) -> tuple[float, bool]:
    """Return (coverage percent 0-100, measured)."""
    if not coverage_xml.is_file():
        return (0.0, False)
    try:
        root = ET.parse(coverage_xml).getroot()
        rate = root.attrib.get("line-rate")
        if rate is None:
            return (0.0, True)
        pct = float(rate) * 100.0
        return (max(0.0, min(100.0, pct)), True)
    except (ET.ParseError, OSError, ValueError):
        return (0.0, True)


def _mypy_error_count(cp: subprocess.CompletedProcess[str]) -> int:
    text = (cp.stdout or "") + "\n" + (cp.stderr or "")
    m = re.search(r"Found\s+(\d+)\s+error", text)
    if m:
        return int(m.group(1))
    if cp.returncode == 0:
        return 0
    # Count "error:" lines as fallback
    return sum(1 for line in text.splitlines() if "error:" in line.lower())


def _ruff_violation_count(cp: subprocess.CompletedProcess[str]) -> int:
    if cp.returncode == 0 and not (cp.stdout or "").strip():
        return 0
    raw = (cp.stdout or "").strip()
    if not raw:
        return (
            0
            if cp.returncode == 0
            else len([ln for ln in (cp.stderr or "").splitlines() if ln.strip()])
        )
    try:
        rows = json.loads(raw)
        if isinstance(rows, list):
            return len(rows)
    except json.JSONDecodeError:
        pass
    m = re.search(r"Found\s+(\d+)\s+error", (cp.stdout or "") + (cp.stderr or ""))
    if m:
        return int(m.group(1))
    return 1 if cp.returncode != 0 else 0


def _score_mypy(errors: int) -> float:
    if errors <= 0:
        return 100.0
    return max(0.0, 100.0 - (errors / 50.0) * 100.0)


def _score_ruff(violations: int) -> float:
    if violations <= 0:
        return 100.0
    return max(0.0, 100.0 - (violations / 100.0) * 100.0)


class _CCVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.value = 0

    def visit_If(self, node: ast.If) -> None:
        self.value += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.value += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.value += 1
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:
        self.value += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.value += max(0, len(node.values) - 1)
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        if len(node.ops) > 1:
            self.value += len(node.ops) - 1
        self.generic_visit(node)


def _function_complexity(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    vis = _CCVisitor()
    for stmt in node.body:
        vis.visit(stmt)
    return 1 + vis.value


def _cyclomatic_p95(app_dir: Path) -> float:
    complexities: list[int] = []
    if not app_dir.is_dir():
        return 0.0
    for path in sorted(app_dir.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            src = path.read_text(encoding="utf-8")
            tree = ast.parse(src, filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for child in ast.walk(tree):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                complexities.append(_function_complexity(child))
    if not complexities:
        return 0.0
    complexities.sort()
    k = (len(complexities) - 1) * 0.95
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return float(complexities[int(lo)])
    return float(complexities[int(lo)] + (complexities[int(hi)] - complexities[int(lo)]) * (k - lo))


def _score_complexity_p95(p95: float) -> float:
    if p95 < 10:
        return 100.0
    if p95 < 15:
        return 80.0
    if p95 < 25:
        return 50.0
    return 0.0


def _write_metrics(blob: dict[str, Any], brain: Path) -> None:
    out = brain / "data" / "code_quality_metrics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(blob, indent=2) + "\n", encoding="utf-8")


def collect() -> tuple[float, bool, str]:
    brain = _brain_dir()
    repo = _monorepo_root()
    coverage_xml = brain / "coverage.xml"

    try:
        cov_pct, cov_measured = _read_coverage_pct(coverage_xml)
        sub_cov = cov_pct if cov_measured else 50.0

        mypy_cp = _run(
            ["uv", "run", "mypy", "app", "--config-file", "pyproject.toml"],
            brain,
        )
        if mypy_cp.returncode not in (0, 1):
            return _BOOTSTRAP
        mypy_n = _mypy_error_count(mypy_cp)
        sub_mypy = _score_mypy(mypy_n)

        ruff_cp = _run(
            [
                "uv",
                "run",
                "ruff",
                "check",
                "apis/brain",
                "apis/axiomfolio",
                "apis/filefree",
                "apis/launchfree",
                "--output-format=json",
            ],
            repo,
        )
        if ruff_cp.returncode not in (0, 1):
            return _BOOTSTRAP
        ruff_n = _ruff_violation_count(ruff_cp)
        sub_ruff = _score_ruff(ruff_n)

        p95 = _cyclomatic_p95(brain / "app")
        sub_cc = _score_complexity_p95(p95)

        pillars_avg = (sub_cov + sub_mypy + sub_ruff + sub_cc) / 4.0
        total = max(0.0, min(100.0, math.floor(pillars_avg * 10000 + 0.5) / 10000))

        now = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
        blob = {
            "schema": _SCHEMA,
            "computed_at": now,
            "test_coverage_pct": round(float(cov_pct), 4) if cov_measured else 0.0,
            "mypy_errors": mypy_n,
            "ruff_violations": ruff_n,
            "cyclomatic_p95": round(float(p95), 4),
            "sub_scores": {
                "test_coverage": round(sub_cov, 4),
                "type_check": round(sub_mypy, 4),
                "lint": round(sub_ruff, 4),
                "complexity": round(sub_cc, 4),
            },
        }
        _write_metrics(blob, brain)

        notes = (
            f"code_quality: coverage_measured={cov_measured} cov_pct={cov_pct:.1f} "
            f"mypy={mypy_n} ruff={ruff_n} cyclomatic_p95={p95:.2f}"
        )
        return (total, True, notes)
    except (
        FileNotFoundError,
        OSError,
        subprocess.TimeoutExpired,
        ValueError,
    ):
        return _BOOTSTRAP
