#!/usr/bin/env python3
"""Validate agent_dispatch_log.json for cheap-agent-fleet compliance.

Reads apis/brain/data/agent_dispatch_log.json and for each dispatch entry:
  - Asserts agent_model is in the cheap allow-list OR is empty/missing (allowed for legacy no-model entries)
  - Asserts agent_model does NOT contain "opus" (Opus is forbidden as subagent)

Exits non-zero on violation; prints the offending entry.

Usage:
  python scripts/validate_agent_dispatch_log.py
  python scripts/validate_agent_dispatch_log.py --path path/to/log.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CHEAP_ALLOW_LIST = frozenset(
    {
        "composer-1.5",
        "composer-2-fast",
        "gpt-5.5-medium",
        "claude-4.6-sonnet-medium-thinking",
        "",
        "cheap",
        "expensive",
    }
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_LOG = _REPO_ROOT / "apis" / "brain" / "data" / "agent_dispatch_log.json"


def validate(log_path: Path) -> int:
    """Return 0 if all entries are compliant, non-zero otherwise."""
    if not log_path.exists():
        print(f"[validate_agent_dispatch_log] {log_path} not found — skipping")
        return 0

    try:
        raw = json.loads(log_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[validate_agent_dispatch_log] ERROR: cannot read {log_path}: {exc}", file=sys.stderr)
        return 1

    dispatches: list[dict] = raw.get("dispatches", [])
    if not dispatches:
        print("[validate_agent_dispatch_log] No dispatch entries — OK")
        return 0

    violations: list[tuple[int, dict, str]] = []

    for i, entry in enumerate(dispatches):
        model: str = str(entry.get("agent_model", "")).strip()

        if "opus" in model.lower():
            violations.append(
                (
                    i,
                    entry,
                    f"Model '{model}' contains 'opus' — Opus is FORBIDDEN as a subagent dispatch "
                    "(cheap-agent-fleet.mdc Rule #2). Only orchestrator sessions may use Opus.",
                )
            )
            continue

        if model and model not in CHEAP_ALLOW_LIST:
            violations.append(
                (
                    i,
                    entry,
                    f"Model '{model}' is not in the cheap allow-list. "
                    f"Allowed: {sorted(m for m in CHEAP_ALLOW_LIST if m)}. "
                    "See docs/PR_TSHIRT_SIZING.md.",
                )
            )

    if not violations:
        print(
            f"[validate_agent_dispatch_log] All {len(dispatches)} entries are compliant — OK"
        )
        return 0

    print(
        f"[validate_agent_dispatch_log] VIOLATIONS FOUND: {len(violations)} of {len(dispatches)} entries",
        file=sys.stderr,
    )
    for idx, entry, reason in violations:
        dispatch_id = entry.get("dispatch_id", f"index-{idx}")
        print(f"\n  Entry #{idx} (dispatch_id={dispatch_id}):", file=sys.stderr)
        print(f"  agent_model: {entry.get('agent_model', '<missing>')}", file=sys.stderr)
        print(f"  workstream_id: {entry.get('workstream_id', '<missing>')}", file=sys.stderr)
        print(f"  Reason: {reason}", file=sys.stderr)

    print(
        "\n  Fix: Update agent_model to a valid cheap model or remove the violating entry.",
        file=sys.stderr,
    )
    print(
        "  See: .cursor/rules/cheap-agent-fleet.mdc Rule #2 and docs/PR_TSHIRT_SIZING.md",
        file=sys.stderr,
    )
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path",
        type=Path,
        default=_DEFAULT_LOG,
        help="Path to agent_dispatch_log.json (default: %(default)s)",
    )
    args = parser.parse_args()
    sys.exit(validate(args.path))


if __name__ == "__main__":
    main()
