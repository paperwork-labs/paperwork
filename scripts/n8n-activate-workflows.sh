#!/usr/bin/env bash
# Activate specific n8n workflows by exact name via the public REST API.
# Use when Infra Health Check reports inactive workflows (e.g. after manual toggle or a bad import).
#
# Requires (same as Studio / ops):
#   N8N_HOST or N8N_API_URL — base URL, e.g. https://n8n.paperworklabs.com
#   N8N_API_KEY — Settings → API in n8n (X-N8N-API-KEY)
#
# Usage:
#   ./scripts/n8n-activate-workflows.sh
#   ./scripts/n8n-activate-workflows.sh "Agent Thread Handler" "CPA Tax Review"
#
# Webhook-heavy workflows: if Slack/webhook still 404s after API activate, open the workflow
# in the n8n editor, Save, and toggle Active once (n8n occasionally needs UI to register webhooks).

set -euo pipefail

RAW_BASE="${N8N_API_URL:-${N8N_HOST:-}}"
if [[ -z "$RAW_BASE" ]]; then
  echo "Error: set N8N_HOST or N8N_API_URL" >&2
  exit 1
fi
if [[ -z "${N8N_API_KEY:-}" ]]; then
  echo "Error: set N8N_API_KEY" >&2
  exit 1
fi

BASE="${RAW_BASE%/}"
if [[ "$BASE" != *"/api/v1" ]]; then
  BASE="${BASE}/api/v1"
fi

DEFAULT_NAMES=("Agent Thread Handler" "CPA Tax Review")
if [[ $# -gt 0 ]]; then
  NAMES=("$@")
else
  NAMES=("${DEFAULT_NAMES[@]}")
fi

list_json="$(curl -sfS -H "X-N8N-API-KEY: ${N8N_API_KEY}" "${BASE}/workflows?limit=250")" || {
  echo "Error: failed to list workflows from ${BASE}/workflows" >&2
  exit 1
}

activate_one() {
  local id="$1"
  local name="$2"
  local tmp
  tmp="$(mktemp)"
  local code
  code="$(curl -sS -o "$tmp" -w '%{http_code}' -X POST \
    -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
    -H "Content-Type: application/json" \
    -d '{}' \
    "${BASE}/workflows/${id}/activate")"
  if [[ "$code" =~ ^2 ]]; then
    echo "OK: activated [$name] (id=$id)"
  else
    echo "FAIL: [$name] id=$id HTTP $code — $(cat "$tmp" 2>/dev/null || true)" >&2
    rm -f "$tmp"
    return 1
  fi
  rm -f "$tmp"
}

any_fail=0
for want in "${NAMES[@]}"; do
  id="$(echo "$list_json" | jq -r --arg n "$want" '[.data[]? | select(.name == $n)] | first | .id // empty')"
  if [[ -z "$id" || "$id" == "null" ]]; then
    echo "WARN: no workflow named \"$want\" (skipped)" >&2
    continue
  fi
  active="$(echo "$list_json" | jq -r --arg n "$want" '[.data[]? | select(.name == $n)] | first | .active // false')"
  if [[ "$active" == "true" ]]; then
    echo "Skip: already active [$want] (id=$id)"
    continue
  fi
  activate_one "$id" "$want" || any_fail=1
done

exit "$any_fail"
