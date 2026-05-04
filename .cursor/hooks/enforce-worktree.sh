#!/usr/bin/env bash
# enforce-worktree.sh
#
# Cursor subagentStart hook — subagents MUST NOT run from the main repo checkout.
# Reads JSON from stdin; extracts cwd (multiple possible paths in the payload).
# Returns {"permission":"deny",...} when cwd resolves to ~/development/paperwork
# or /Users/paperworklabs/development/paperwork (excluding worktrees roots).
#
# Trade-off — missing cwd fields: Some Cursor payloads omit cwd entirely (orchestrator
# or tooling variants). Blocking would false-positive those sessions; ALLOW with a
# user_message NOTICE stating validation was skipped — NOT silent OK.
#
# Missing/invalid JSON: deny with explicit parser failure (never silently allow).
#
# failClosed: true in hooks.json
# See: .cursor/rules/cheap-agent-fleet.mdc procedural memory / worktree discipline

set -euo pipefail

MAIN_REPO_FIXED="/Users/paperworklabs/development/paperwork"
DENY_TEMPLATE='BLOCKED: subagent dispatched from main checkout. Always dispatch from a git worktree (~/development/paperwork-worktrees/<branch>). See .cursor/rules/cheap-agent-fleet.mdc procedural memory rule. To create one: git worktree add ~/development/paperwork-worktrees/<branch-name> -b <branch-name> main'
PARSE_ERR='BLOCKED: subagent dispatch payload could not be parsed as JSON — cannot enforce worktree policy. Fix stdin / tooling payload. Hook: enforce-worktree.sh'

INPUT="$(cat)"

main_home_candidate=""
if [[ -n "${HOME:-}" ]]; then
  main_home_candidate="${HOME}/development/paperwork"
fi

WORKDIR=""

if command -v jq >/dev/null 2>&1; then
  if ! printf '%s' "$INPUT" | jq empty >/dev/null 2>&1; then
    printf '{"permission":"deny","user_message":"%s"}\n' "$PARSE_ERR"
    exit 0
  fi
  WORKDIR="$(printf '%s' "$INPUT" | jq -r '
      ([
        (.cwd),
        (.workingDirectory),
        (.working_directory),
        (.input // {} | .cwd),
        (.input // {} | .workingDirectory),
        (.input // {} | .working_directory),
        (.params // {} | .cwd),
        (.params // {} | .workingDirectory),
        (.task // {} | .cwd),
        (.task // {} | .workingDirectory),
        (.taskParams // {} | .cwd)
      ] | map(select(type == "string" and length > 0 and (ascii_downcase | . != "null"))) | first) // ""
    ')"
else
  py_status=0
  WORKDIR=""
  PY_OUT="$(printf '%s' "$INPUT" | python3 -c '
import json, sys

raw = sys.stdin.read()

try:
    data = json.loads(raw)
except json.JSONDecodeError:
    sys.stderr.write("__JSON_ERROR__\\n")
    sys.exit(1)


def grab(d):
    if not isinstance(d, dict):
        return ""
    for k in ("cwd", "workingDirectory", "working_directory"):
        v = d.get(k)
        if isinstance(v, str):
            vv = v.strip()
            if vv and vv.lower() != "null":
                return vv
    return ""

for blk in (
    data,
    data.get("input") if isinstance(data.get("input"), dict) else {},
    data.get("params") if isinstance(data.get("params"), dict) else {},
    data.get("task") if isinstance(data.get("task"), dict) else {},
    data.get("taskParams") if isinstance(data.get("taskParams"), dict) else {},
):
    g = grab(blk)
    if g:
        print(g)
        sys.exit(0)
sys.exit(0)
  ')" || py_status=$?
  case "$py_status" in
    1)
      printf '{"permission":"deny","user_message":"%s"}\n' "$PARSE_ERR"
      exit 0
      ;;
  esac
  WORKDIR="$(printf '%s' "$PY_OUT")"
fi

WORKDIR="${WORKDIR//[$'\t\r']/}"
WORKDIR="${WORKDIR//$'\n'/}"

WORKDIR_LOW="$(printf '%s' "$WORKDIR" | tr '[:upper:]' '[:lower:]')"
if [[ -z "$WORKDIR" ]] || [[ "$WORKDIR_LOW" == "null" ]]; then
  printf '{"permission":"allow","user_message":"NOTICE: cwd not present on subagent payload — enforce-worktree.sh could not verify worktree vs main checkout (allowed by policy). Prefer dispatching subagents from a cwd under ~/development/paperwork-worktrees/<branch>.\\n"}\n'
  exit 0
fi

WORKDIR_NORM="${WORKDIR%/}"
FIXED_NORM="${MAIN_REPO_FIXED%/}"
HOME_NORM=""
if [[ -n "$main_home_candidate" ]]; then
  HOME_NORM="${main_home_candidate%/}"
fi

case "$WORKDIR_NORM" in
  */paperwork-worktrees/* )
    printf '{"permission":"allow"}\n'
    exit 0
    ;;
esac

if [[ "$WORKDIR_NORM" == "$FIXED_NORM" ]] || { [[ -n "$HOME_NORM" ]] && [[ "$WORKDIR_NORM" == "$HOME_NORM" ]]; }; then
  printf '{"permission":"deny","user_message":"%s"}\n' "${DENY_TEMPLATE}"
  exit 0
fi

printf '{"permission":"allow"}\n'
exit 0
