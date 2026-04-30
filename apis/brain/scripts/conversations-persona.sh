#!/usr/bin/env bash
# conversations-persona.sh — create a Brain Conversation from the terminal.
#
# Replaces scripts/slack-persona.sh (WS-69 PR J). Wraps POST /admin/conversations
# with the same ergonomics so persona dispatch from the terminal still works.
#
# Usage:
#   ./conversations-persona.sh <persona> <title> [body_md]
#
# Environment:
#   BRAIN_URL           Brain API base URL (default: http://localhost:8001)
#   BRAIN_API_SECRET    Bearer token for /admin/* endpoints
#
# Examples:
#   ./conversations-persona.sh ea "Deploy checklist" "Review the deploy steps."
#   ./conversations-persona.sh cfo "Q2 burn rate" "Check monthly spend."

set -euo pipefail

PERSONA="${1:-}"
TITLE="${2:-}"
BODY_MD="${3:-}"

if [[ -z "$PERSONA" || -z "$TITLE" ]]; then
  echo "Usage: $0 <persona> <title> [body_md]" >&2
  exit 1
fi

BRAIN_URL="${BRAIN_URL:-http://localhost:8001}"
BRAIN_API_SECRET="${BRAIN_API_SECRET:-}"

if [[ -z "$BRAIN_API_SECRET" ]]; then
  echo "Error: BRAIN_API_SECRET environment variable is required." >&2
  exit 1
fi

PAYLOAD=$(jq -n \
  --arg title "$TITLE" \
  --arg body_md "$BODY_MD" \
  --arg persona "$PERSONA" \
  '{
    title: $title,
    body_md: $body_md,
    tags: [$persona],
    urgency: "normal",
    persona: $persona,
    needs_founder_action: false
  }')

curl -sSf \
  -X POST \
  -H "Authorization: Bearer ${BRAIN_API_SECRET}" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  "${BRAIN_URL}/api/v1/admin/conversations" | jq .
