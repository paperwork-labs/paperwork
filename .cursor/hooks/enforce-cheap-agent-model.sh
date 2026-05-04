#!/usr/bin/env bash
# enforce-cheap-agent-model.sh
#
# Cursor subagentStart hook — enforces the PR T-Shirt Sizing taxonomy.
# Reads JSON from stdin; extracts the model field; validates against allow-list.
# Non-composer allow-list entries require a `# justification:` line inside the dispatched
# prompt blob (warn-only soft enforcement — dispatch still succeeds).
#
# Opus-containing models remain a hard deny. Composer XS/S paths stay silent allows.
#
# failClosed: true in hooks.json — if this script crashes, the dispatch is blocked.
# See: .cursor/rules/cheap-agent-fleet.mdc Rule #2 + Rule #5
# See: docs/PR_TSHIRT_SIZING.md

set -euo pipefail

ALLOW_LIST=(
  "composer-1.5"
  "composer-2-fast"
  "gpt-5.5-medium"
  "claude-4.6-sonnet-medium-thinking"
)

DENY_MSG='BLOCKED: Task dispatch missing or invalid model. Specify one of: composer-1.5 (XS, ~$0.10), composer-2-fast (S, ~$0.40), gpt-5.5-medium (M, ~$1.00), claude-4.6-sonnet-medium-thinking (L, ~$3.00). Opus is FORBIDDEN as subagent (orchestrator-only). See .cursor/rules/cheap-agent-fleet.mdc Rule #2 and docs/PR_TSHIRT_SIZING.md.'
DENY_PARSE='BLOCKED: subagent dispatch payload could not be parsed as JSON — cannot enforce model taxonomy. Hook: enforce-cheap-agent-model.sh'

INPUT="$(cat)"
TMP_PAYLOAD="$(mktemp "${TMPDIR:-/tmp}/pw-hook-agent-model-json.XXXXXX")"
cleanup() {
  rm -f "$TMP_PAYLOAD"
}
trap cleanup EXIT
printf '%s' "$INPUT" >"$TMP_PAYLOAD"

export PW_HOOK_MODEL_PAYLOAD_PATH="$TMP_PAYLOAD"

if command -v jq >/dev/null 2>&1 && ! jq empty "$TMP_PAYLOAD" 2>/dev/null; then
  printf '{"permission":"deny","user_message":"%s"}\n' "$DENY_PARSE"
  exit 0
fi

META_JSON="$(python3 <<'PY'
import json
import os
import sys

payload_path = os.environ.get("PW_HOOK_MODEL_PAYLOAD_PATH", "")

DENY_DETAIL = (
    "BLOCKED: subagent dispatch payload could not be parsed as JSON — cannot enforce "
    "model taxonomy. Hook: enforce-cheap-agent-model.sh"
)

try:
    with open(payload_path, "r", encoding="utf-8") as handle:
        raw_blob = handle.read()
    blob = json.loads(raw_blob)
    if not isinstance(blob, dict):
        raise ValueError("payload_root_not_object")
except (OSError, ValueError, json.JSONDecodeError):
    print(json.dumps({"parse_error": True, "detail": DENY_DETAIL}))
    sys.exit(0)


def pick_model(obj: dict) -> str:
    for parent in ("", "input", "params", "task", "taskParams"):
        fragment = obj if parent == "" else obj.get(parent)
        if not isinstance(fragment, dict):
            continue

        cand = fragment.get("model")

        if isinstance(cand, str):
            trimmed = cand.strip()
            lowered = trimmed.lower()
            if trimmed and lowered not in {"null", "none"}:
                return trimmed

    return ""


prompt_chunks = []


def scoop_prompt(fragment):
    if not isinstance(fragment, dict):
        return
    blob = fragment.get("prompt")
    if isinstance(blob, str) and blob.strip():
        prompt_chunks.append(blob)


scoop_prompt(blob)
for nested_key in ("input", "params", "task", "taskParams"):
    child = blob.get(nested_key)
    scoop_prompt(child if isinstance(child, dict) else None)

combined_prompt = "\n".join(prompt_chunks)

print(
    json.dumps(
        {"parse_error": False, "model": pick_model(blob), "prompt_blob": combined_prompt}
    )
)
PY
)"

if printf '%s' "$META_JSON" | python3 -c 'import json,sys
data=json.loads(sys.stdin.read())
sys.exit(0 if data.get("parse_error") else 1)'
then
  DETAIL="$(printf '%s' "$META_JSON" | python3 -c 'import json,sys; print(json.loads(sys.stdin.read()).get("detail",""))')"
  if [[ -z "$DETAIL" ]]; then
    DETAIL="$DENY_PARSE"
  fi
  printf '{"permission":"deny","user_message":"%s"}\n' "$DETAIL"
  exit 0
fi

MODEL="$(printf '%s' "$META_JSON" | python3 -c 'import json,sys; print(json.loads(sys.stdin.read()).get("model",""))')"
MODEL="${MODEL//[$'\t\r']/}"
PROMPT_BLOB="$(printf '%s' "$META_JSON" | python3 -c 'import json,sys; blob=json.loads(sys.stdin.read()).get("prompt_blob"); print(blob if isinstance(blob,str) else "")')"

# Empty or null model → deny
if [[ -z "$MODEL" ]] || [[ "$(printf '%s' "$MODEL" | tr '[:upper:]' '[:lower:]')" == "null" ]]; then
  printf '{"permission":"deny","user_message":"%s"}\n' "$DENY_MSG"
  exit 0
fi

LOWER_MODEL="$(printf '%s' "$MODEL" | tr '[:upper:]' '[:lower:]')"
if [[ "$LOWER_MODEL" == *"opus"* ]]; then
  printf '{"permission":"deny","user_message":"BLOCKED: Opus models (%s) are FORBIDDEN as subagents. Opus is orchestrator-only. Use a cheap model (XS–L). See .cursor/rules/cheap-agent-fleet.mdc Rule #2."}\n' "$MODEL"
  exit 0
fi

for allowed in "${ALLOW_LIST[@]}"; do
  if [[ "$MODEL" == "$allowed" ]]; then
    case "$MODEL" in
      composer-1.5 | composer-2-fast)
        printf '{"permission":"allow"}\n'
        ;;
      gpt-5.5-medium | claude-4.6-sonnet-medium-thinking)
        if printf '%s' "$PROMPT_BLOB" | grep -qiE '#[[:space:]]*justification:'; then
          printf '{"permission":"allow"}\n'
        else
          PW_DISPATCH_MODEL="$MODEL" python3 <<'WARNPY'
import json
import os

model_slug = os.environ.get("PW_DISPATCH_MODEL", "").strip()

warning = (
    f"WARNING: dispatching {model_slug} without a '# justification:' line. "
    "Composer-only is the doctrine; non-composer requires justification per "
    ".cursor/rules/cheap-agent-fleet.mdc Rule #5. Allowing this dispatch but "
    "please add a '# justification:' line going forward."
)
print(json.dumps({"permission": "allow", "user_message": warning}))
WARNPY
        fi
        ;;
      *)
        printf '{"permission":"allow"}\n'
        ;;
    esac
    exit 0
  fi
done

printf '{"permission":"deny","user_message":"BLOCKED: Model \"%s\" is not in the T-Shirt Size allow-list. Allowed: composer-1.5 (XS), composer-2-fast (S), gpt-5.5-medium (M), claude-4.6-sonnet-medium-thinking (L). See docs/PR_TSHIRT_SIZING.md."}\n' "$MODEL"
exit 0
