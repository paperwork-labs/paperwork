#!/usr/bin/env bash
# enforce-no-direct-main-push.sh
#
# Cursor beforeShellExecution hook — forbid direct pushes to main/master regardless of caller.
#
# Applies to EVERY shell invocation (Cursor does not classify orchestrator vs subagent payloads
# for beforeShellExecution), which matches `.cursor/rules/git-workflow.mdc` — never push to main.
#
# Reads JSON stdin; extracts the command string (.command/.input.command/.shell.command/.params.command).
#
# Missing command after successful JSON parse ⇒ allow (nothing to fingerprint as a forbidden push).
# Invalid JSON ⇒ deny — never silently approve an unparsed wrapper.
#
# failClosed: true

set -euo pipefail

TMP_JSON="$(mktemp "${TMPDIR:-/tmp}/pw-hook-shell-json.XXXXXX")"
cleanup() {
  rm -f "$TMP_JSON"
}
trap cleanup EXIT

INPUT="$(cat)"
printf '%s' "$INPUT" >"$TMP_JSON"

export PW_HOOK_SHELL_JSON_PATH="$TMP_JSON"

python3 <<'PY'
from __future__ import annotations

import json
import os
import re
import sys


def dumps_deny(reason: str) -> None:
    print(json.dumps({"permission": "deny", "user_message": reason}))


PATH_ENV = os.environ.get("PW_HOOK_SHELL_JSON_PATH", "")

DENY_PARSE = (
    "BLOCKED: beforeShellExecution payload could not be parsed as JSON — "
    "cannot validate push safety. Hook: enforce-no-direct-main-push.sh"
)
DENY_PUSH = (
    "BLOCKED: direct push to main is forbidden. All changes go through PR per "
    ".cursor/rules/git-workflow.mdc. Push your feature branch and open a PR with "
    "'gh pr create' instead."
)


def extract_command(blob: dict) -> str:
    buckets = []

    candidates = []
    candidates.append(blob.get("command"))

    inp = blob.get("input") if isinstance(blob.get("input"), dict) else None
    candidates.append(inp.get("command") if inp else None)

    shell_blob = blob.get("shell") if isinstance(blob.get("shell"), dict) else None
    candidates.append(shell_blob.get("command") if shell_blob else None)

    params_blob = blob.get("params") if isinstance(blob.get("params"), dict) else None
    candidates.append(params_blob.get("command") if params_blob else None)

    for cand in candidates:
        if cand is None:
            continue
        if isinstance(cand, str):
            trimmed = cand.strip()
            if trimmed:
                buckets.append(trimmed)
    return "\n".join(buckets)


blocked_patterns = [
    re.compile(r"git\s+push.*?\borigin\s+(?:main|master)\b", re.IGNORECASE | re.DOTALL),
    re.compile(
        r"git\s+push.*?\b(?:--force|--force-with-lease).*?\b(?:main|master)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"git\s+push.*?(\s|^)-f[^\n]*(main|master)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(r"git\s+push[^\n]+\bHEAD\s*:\s*(?:main|master)\b", re.IGNORECASE | re.DOTALL),
    re.compile(r"git\s+push\s+origin\s+:\s*(?:main|master)\b", re.IGNORECASE | re.DOTALL),
]


def should_block(raw_cmd: str) -> bool:
    if not raw_cmd.strip():
        return False
    if not re.search(r"^\s*git\s+push\b", raw_cmd, re.IGNORECASE):
        return False
    return any(pat.search(raw_cmd) for pat in blocked_patterns)


try:
    with open(PATH_ENV, "r", encoding="utf-8") as handle:
        raw_blob = handle.read()
    blob = json.loads(raw_blob)
    if not isinstance(blob, dict):
        raise ValueError("payload must be an object")
except (OSError, ValueError, json.JSONDecodeError):
    dumps_deny(DENY_PARSE)
    sys.exit(0)

cmd_txt = extract_command(blob)
if not cmd_txt.strip():
    print(json.dumps({"permission": "allow"}))
    sys.exit(0)

if should_block(cmd_txt):
    dumps_deny(DENY_PUSH)
else:
    print(json.dumps({"permission": "allow"}))
PY
