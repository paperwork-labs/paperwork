#!/usr/bin/env bash
# enforce-rules-attachment.sh
#
# Cursor subagentStart hook — pinned rules MUST be wired on every dispatch.
# Accepts EITHER a nested `rules` JSON array containing at least one entry,
# OR a prompt body containing `# rules:` or ## Pinned rules (markdown heading).
#
# Invalid JSON ⇒ deny with explicit parse error (no silent fallback).
# Parser: validates with jq when installed; evaluates rules/prompt markers in Python
# with the payload streamed via a tempfile (avoids env size limits vs bash export).
#
# failClosed: true — see .cursor/rules/cheap-agent-fleet.mdc Rule #2

set -euo pipefail

TMP_JSON="$(mktemp "${TMPDIR:-/tmp}/pw-hook-rules-json.XXXXXX")"
cleanup() {
  rm -f "$TMP_JSON"
}
trap cleanup EXIT

INPUT="$(cat)"
printf '%s' "$INPUT" >"$TMP_JSON"

if command -v jq >/dev/null 2>&1 && ! jq empty "$TMP_JSON" 2>/dev/null; then
  printf '{"permission":"deny","user_message":"%s"}\n' \
    "BLOCKED: subagent dispatch payload could not be parsed as JSON — cannot enforce rules attachment policy. Hook: enforce-rules-attachment.sh"
  exit 0
fi

export PW_HOOK_RULES_JSON_PATH="$TMP_JSON"

python3 <<'PY'
import json
import os
import re
import sys

path = os.environ.get("PW_HOOK_RULES_JSON_PATH", "")
DENY_MISSING = (
    "BLOCKED: subagent dispatch missing pinned rules. "
    "Include 'rules: [...]' field in the dispatch payload OR a '## Pinned rules' markdown section "
    "in the prompt with at minimum: cheap-agent-fleet.mdc, git-workflow.mdc, no-silent-fallback.mdc, "
    "plus product persona (.mdc) if applicable. See .cursor/rules/cheap-agent-fleet.mdc Rule #2."
)

DENY_PARSE = (
    "BLOCKED: subagent dispatch payload could not be parsed as JSON — cannot enforce "
    "rules attachment policy. Hook: enforce-rules-attachment.sh"
)

try:
    with open(path, "r", encoding="utf-8") as handle:
        raw = handle.read()
    data = json.loads(raw)
except (OSError, json.JSONDecodeError):
    print(json.dumps({"permission": "deny", "user_message": DENY_PARSE}))
    sys.exit(0)

rules_candidates = [data.get("rules")]
for blob_key in ("input", "params", "task", "taskParams"):
    child = data.get(blob_key)
    if isinstance(child, dict):
        rules_candidates.append(child.get("rules"))

rules_ok = any(isinstance(candidate, list) and len(candidate) > 0 for candidate in rules_candidates)


def gather_prompt_chunks(d_obj):
    texts = []

    def add(obj):
        if not isinstance(obj, dict):
            return
        prompt = obj.get("prompt")
        if isinstance(prompt, str) and prompt.strip():
            texts.append(prompt)

    add(d_obj)
    for child_key in ("input", "params", "task", "taskParams"):
        child_obj = d_obj.get(child_key)
        add(child_obj)

    return "\n".join(texts)


combined_prompt = gather_prompt_chunks(data)

markers_ok = False
if combined_prompt:
    markers_ok = bool(re.search(r"(?mi)^#\s*rules\s*:", combined_prompt))
    markers_ok = markers_ok or bool(re.search(r"(?mi)^##\s*pinned\s+rules\b", combined_prompt))

if rules_ok or markers_ok:
    print(json.dumps({"permission": "allow"}))
else:
    print(json.dumps({"permission": "deny", "user_message": DENY_MISSING}))
PY
