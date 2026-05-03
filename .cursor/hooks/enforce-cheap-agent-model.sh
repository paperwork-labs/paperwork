#!/usr/bin/env bash
# enforce-cheap-agent-model.sh
#
# Cursor subagentStart hook — enforces the PR T-Shirt Sizing taxonomy.
# Reads JSON from stdin; extracts the model field; validates against allow-list.
# Returns {"permission":"deny",...} for missing or forbidden (Opus) models.
# Returns {"permission":"allow"} for valid cheap models (XS–L).
#
# failClosed: true in hooks.json — if this script crashes, the dispatch is blocked.
# See: .cursor/rules/cheap-agent-fleet.mdc Rule #2
# See: docs/PR_TSHIRT_SIZING.md

set -euo pipefail

ALLOW_LIST=(
  "composer-1.5"
  "composer-2-fast"
  "gpt-5.5-medium"
  "claude-4.6-sonnet-medium-thinking"
)

DENY_MSG='BLOCKED: Task dispatch missing or invalid model. Specify one of: composer-1.5 (XS, ~$0.10), composer-2-fast (S, ~$0.40), gpt-5.5-medium (M, ~$1.00), claude-4.6-sonnet-medium-thinking (L, ~$3.00). Opus is FORBIDDEN as subagent (orchestrator-only). See .cursor/rules/cheap-agent-fleet.mdc Rule #2 and docs/PR_TSHIRT_SIZING.md.'

# Read full stdin into variable (hooks pass JSON payload)
INPUT="$(cat)"

# Extract model field — try multiple possible paths in the payload.
# subagentStart payload shape may vary; try common paths.
MODEL=""
if command -v jq >/dev/null 2>&1; then
  # Try direct .model, then .input.model, then .params.model, then .task.model
  MODEL="$(printf '%s' "$INPUT" | jq -r '
    .model //
    .input.model //
    .params.model //
    .task.model //
    .taskParams.model //
    ""
  ' 2>/dev/null || true)"
else
  # Fallback: python3 for environments without jq
  MODEL="$(printf '%s' "$INPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for key in ('model', ('input','model'), ('params','model'), ('task','model'), ('taskParams','model')):
    if isinstance(key, tuple):
        val = data
        for k in key:
            val = val.get(k, {}) if isinstance(val, dict) else {}
        if val and isinstance(val, str):
            print(val)
            sys.exit(0)
    else:
        val = data.get(key, '')
        if val and isinstance(val, str):
            print(val)
            sys.exit(0)
print('')
" 2>/dev/null || true)"
fi

# Trim whitespace
MODEL="${MODEL// /}"
MODEL="${MODEL//[$'\t\r\n']/}"

# Empty or null model → deny
if [ -z "$MODEL" ] || [ "$MODEL" = "null" ]; then
  printf '{"permission":"deny","user_message":"%s"}\n' "$DENY_MSG"
  exit 0
fi

# Opus check — any model containing "opus" (case-insensitive) is forbidden as subagent
LOWER_MODEL="$(printf '%s' "$MODEL" | tr '[:upper:]' '[:lower:]')"
if [[ "$LOWER_MODEL" == *"opus"* ]]; then
  printf '{"permission":"deny","user_message":"BLOCKED: Opus models (%s) are FORBIDDEN as subagents. Opus is orchestrator-only. Use a cheap model (XS–L). See .cursor/rules/cheap-agent-fleet.mdc Rule #2."}\n' "$MODEL"
  exit 0
fi

# Allow-list check
for allowed in "${ALLOW_LIST[@]}"; do
  if [ "$MODEL" = "$allowed" ]; then
    printf '{"permission":"allow"}\n'
    exit 0
  fi
done

# Model present but not in allow-list
printf '{"permission":"deny","user_message":"BLOCKED: Model \"%s\" is not in the T-Shirt Size allow-list. Allowed: composer-1.5 (XS), composer-2-fast (S), gpt-5.5-medium (M), claude-4.6-sonnet-medium-thinking (L). See docs/PR_TSHIRT_SIZING.md."}\n' "$MODEL"
exit 0
