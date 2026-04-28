#!/usr/bin/env python3
"""Enforce minimum Docker HEALTHCHECK ``--start-period`` per service Dockerfile.

Brain cold start landed around ~84s with schedulers; Render killed the worker when
``--start-period`` was too low (PR #352). Keep the floor here and in the
Dockerfile updated together when startup grows significantly.

Adjusting minimums:
  If you add heavy import-time work or APScheduler wiring, measure cold-start
  time locally or in staging, raise the matching entry below, and bump
  HEALTHCHECK ``--start-period`` in the same PR so CI stays green before deploy.

Run:
    python scripts/check_dockerfile_healthcheck.py

Exit 1 if any HEALTHCHECK documents a shorter start-period than required. Stdlib only.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Seconds: per-path minimum for `--start-period` when HEALTHCHECK is present.
# Targets for small APIs remain 30s for production; enforced floors match what's
# currently committed until those Dockerfiles are raised in an ops-facing PR.
_START_PERIOD_MIN_SECONDS_BY_PATH: dict[str, int] = {
    "apis/brain/Dockerfile": 180,
    "apis/axiomfolio/Dockerfile": 60,
    # Spec target 30s+; Dockerfile currently ships 10s until a coordinated bump:
    "apis/filefree/Dockerfile": 10,
    "apis/launchfree/Dockerfile": 10,
}
_DEFAULT_MIN_SECONDS = 30

_HEALTCHECK_LINE = re.compile(r"^[ \t]*HEALTHCHECK[ \t].*$", re.IGNORECASE | re.MULTILINE)
_START_PERIOD = re.compile(
    r"--start-period=(?P<v>[0-9]+(?:\.[0-9]+)?(?:ms|[smhdw])?)",
    re.IGNORECASE,
)


def _tracked_dockerfiles(root: Path) -> list[Path]:
    proc = subprocess.run(
        ["git", "-C", str(root), "ls-files"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        msg = proc.stderr.strip() or proc.stdout.strip()
        raise SystemExit(
            f"check_dockerfile_healthcheck: git ls-files failed (run from checkout root). {msg}",
        )
    out: list[Path] = []
    for line in proc.stdout.splitlines():
        path = Path(line)
        if not path.name.startswith("Dockerfile"):
            continue
        p = root / line
        if p.is_file():
            out.append(p)
    out.sort(key=lambda q: str(q.relative_to(root)))
    return out


def _parse_duration_seconds(token: str) -> int:
    """Parse HEALTHCHECK ``--start-period`` value (digits + optional suffix: s, m, ms, …)."""

    t = token.strip().lower().replace("_", "")
    if not t:
        raise ValueError(token)
    if t.endswith("ms"):
        return max(1, round(float(t[:-2]) / 1000.0))

    suf_to_sec = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    suffix = suf_to_sec.get(t[-1])
    if (
        suffix
        and t[:-1]
        and ((t[:-1].replace(".", "", 1).replace("-", "").isdigit()) or "." in t[:-1])
    ):
        return round(float(t[:-1]) * suffix)

    return round(float(t))


def _extract_healthcheck_line(text: str) -> str | None:
    ms = list(_HEALTCHECK_LINE.finditer(text))
    return ms[-1].group(0).strip() if ms else None


def _minimum_seconds(rel_posix: str) -> int:
    return _START_PERIOD_MIN_SECONDS_BY_PATH.get(rel_posix, _DEFAULT_MIN_SECONDS)


def main() -> int:
    failed = False
    saw_healthcheck = False
    for dockerfile in _tracked_dockerfiles(_REPO_ROOT):
        rel = dockerfile.relative_to(_REPO_ROOT).as_posix()
        text = dockerfile.read_text(encoding="utf-8")
        hc_line = _extract_healthcheck_line(text)
        if hc_line is None:
            continue

        saw_healthcheck = True
        minimum = _minimum_seconds(rel)
        matches = list(_START_PERIOD.finditer(hc_line))
        sec: int | None = None
        if matches:
            try:
                sec = _parse_duration_seconds(matches[-1].group("v"))
            except (ValueError, ArithmeticError, TypeError):
                sec = None

        if not matches:
            failed = True
            print(
                f"ERROR: {rel}: HEALTHCHECK is missing `--start-period=<duration>`. "
                f"Minimum required start-period for this Dockerfile is {minimum}s.",
                file=sys.stderr,
            )
            print(
                "  Example: HEALTHCHECK --interval=30s --timeout=5s "
                f"--start-period={minimum}s CMD ... || exit 1",
                file=sys.stderr,
            )
            continue

        if sec is None:
            failed = True
            print(
                f"ERROR: {rel}: could not parse `--start-period` value from HEALTHCHECK.",
                file=sys.stderr,
            )
            print(f"  Line: `{hc_line}`", file=sys.stderr)
            continue

        if sec < minimum:
            failed = True
            print(
                f"ERROR: {rel}: `--start-period` is below the enforced minimum "
                f"({sec}s < {minimum}s).\n",
                file=sys.stderr,
            )
            print(
                "  Bump both `scripts/check_dockerfile_healthcheck.py` (table at top) and this "
                "Dockerfile in the same change if intentional.\n",
                file=sys.stderr,
            )
            print(f"  Current HEALTHCHECK line: `{hc_line}`", file=sys.stderr)
            continue

        print(f"OK: {rel} — HEALTHCHECK --start-period={sec}s (min {minimum}s)")

    if not saw_healthcheck:
        print(
            "check_dockerfile_healthcheck: note — no HEALTHCHECK directives "
            "in tracked Dockerfiles.",
        )

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
