#!/usr/bin/env bash
# Retrieve a single secret value from the Studio vault by name (stdout only).
# Usage: scripts/vault-get.sh OPENAI_API_KEY
# Requires: SECRETS_API_KEY, curl, jq
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ "${1:-}" = "" ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
  echo "Usage: $0 SECRET_NAME" >&2
  echo "Prints decrypted secret value to stdout (pipe-friendly)." >&2
  exit 1
fi

SECRET_NAME="$1"

if [ -f "$REPO_ROOT/.env.local" ]; then
  set -a
  # shellcheck source=/dev/null
  source "$REPO_ROOT/.env.local"
  set +a
fi
if [ -f "$REPO_ROOT/apps/studio/.env.local" ]; then
  set -a
  # shellcheck source=/dev/null
  source "$REPO_ROOT/apps/studio/.env.local"
  set +a
fi

STUDIO_URL="${STUDIO_URL:-https://paperworklabs.com}"
SECRETS_API_KEY="$(printf '%s' "${SECRETS_API_KEY:-}" | tr -d '\r\n')"
export SECRETS_API_KEY

ADMIN_EMAIL_FIRST="$(printf '%s' "${ADMIN_EMAILS:-}" | cut -d, -f1 | tr -d ' \"')"
ADMIN_PASS_TRIM="$(printf '%s' "${ADMIN_ACCESS_PASSWORD:-}" | tr -d '\r\n')"

LIST_JSON=""
if [ -n "$SECRETS_API_KEY" ]; then
  LIST_JSON=$(curl -sS -H "Authorization: Bearer $SECRETS_API_KEY" "$STUDIO_URL/api/secrets")
fi
if ! echo "$LIST_JSON" | jq -e '.success == true and (.data | length > 0)' >/dev/null 2>&1; then
  if [ -n "$ADMIN_EMAIL_FIRST" ] && [ -n "$ADMIN_PASS_TRIM" ]; then
    LIST_JSON=$(curl -sS -u "$ADMIN_EMAIL_FIRST:$ADMIN_PASS_TRIM" "$STUDIO_URL/api/secrets")
  fi
fi

ID=$(echo "$LIST_JSON" | jq -r --arg n "$SECRET_NAME" '.data[]? | select(.name == $n) | .id' | head -1)

if [ -z "$ID" ] || [ "$ID" = "null" ]; then
  echo "Error: secret '$SECRET_NAME' not found or auth failed (set SECRETS_API_KEY or ADMIN_EMAILS+ADMIN_ACCESS_PASSWORD)" >&2
  exit 1
fi

GET_JSON=""
if [ -n "$SECRETS_API_KEY" ]; then
  GET_JSON=$(curl -sS -H "Authorization: Bearer $SECRETS_API_KEY" "$STUDIO_URL/api/secrets/$ID")
fi
if ! echo "$GET_JSON" | jq -e '.success == true' >/dev/null 2>&1; then
  GET_JSON=$(curl -sS -u "$ADMIN_EMAIL_FIRST:$ADMIN_PASS_TRIM" "$STUDIO_URL/api/secrets/$ID")
fi
echo "$GET_JSON" | jq -r '.data.value // empty'
