#!/usr/bin/env bash
# Request a one-time Studio secret intake URL (founder pastes value in browser).
# Usage: scripts/request-secret.sh NAME SERVICE [--description "..."] [--prefix "sk_live_"] [--expires-in 30] [--poll]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

POLL=0
NAME=""
SERVICE=""
DESCRIPTION=""
PREFIX=""
EXPIRES_IN=30
EXPIRES_N=30

print_help() {
  echo "Usage: $0 NAME SERVICE [options]" >&2
  echo "  --description \"...\"   Optional intake description" >&2
  echo "  --prefix PREFIX       Require value to start with PREFIX (e.g. sk_live_)" >&2
  echo "  --expires-in MIN      Expiry in minutes (default 30, max 1440)" >&2
  echo "  --poll                Wait until received or expired (timeout = expires-in)" >&2
}

if [ $# -lt 2 ]; then
  print_help
  exit 1
fi

NAME="$1"
SERVICE="$2"
shift 2

while [ $# -gt 0 ]; do
  case "$1" in
    --description)
      DESCRIPTION="${2:-}"
      shift 2
      ;;
    --prefix)
      PREFIX="${2:-}"
      shift 2
      ;;
    --expires-in)
      EXPIRES_IN="${2:-30}"
      EXPIRES_N=$((10#${EXPIRES_IN:-30}))
      shift 2
      ;;
    --poll)
      POLL=1
      shift
      ;;
    -h|--help)
      print_help
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      print_help
      exit 1
      ;;
  esac
done

EXPIRES_N=$((10#${EXPIRES_IN:-30}))

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
STUDIO_URL="${STUDIO_URL%/}"
SECRETS_API_KEY="$(printf '%s' "${SECRETS_API_KEY:-}" | tr -d '\r\n')"
export SECRETS_API_KEY

ADMIN_EMAIL_FIRST="$(printf '%s' "${ADMIN_EMAILS:-}" | cut -d, -f1 | tr -d ' \"')"
ADMIN_PASS_TRIM="$(printf '%s' "${ADMIN_ACCESS_PASSWORD:-}" | tr -d '\r\n')"

build_payload() {
  local desc_json prefix_json
  if [ -n "$DESCRIPTION" ]; then
    desc_json=$(jq -n --arg d "$DESCRIPTION" '$d')
  else
    desc_json="null"
  fi
  if [ -n "$PREFIX" ]; then
    prefix_json=$(jq -n --arg p "$PREFIX" '$p')
  else
    prefix_json="null"
  fi
  jq -n \
    --arg name "$NAME" \
    --arg service "$SERVICE" \
    --argjson description "$desc_json" \
    --argjson expected_prefix "$prefix_json" \
    --argjson expires_in_minutes "$EXPIRES_N" \
    '{name: $name, service: $service, description: $description, expected_prefix: $expected_prefix, expires_in_minutes: $expires_in_minutes}'
}

PAYLOAD="$(build_payload)"

CREATE_JSON=""
if [ -n "$SECRETS_API_KEY" ]; then
  CREATE_JSON=$(curl -sS -X POST "$STUDIO_URL/api/secrets/intake" \
    -H "Authorization: Bearer $SECRETS_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")
fi
if ! echo "$CREATE_JSON" | jq -e '.success == true and (.intake_url | length > 0)' >/dev/null 2>&1; then
  if [ -n "$ADMIN_EMAIL_FIRST" ] && [ -n "$ADMIN_PASS_TRIM" ]; then
    CREATE_JSON=$(curl -sS -X POST "$STUDIO_URL/api/secrets/intake" \
      -u "$ADMIN_EMAIL_FIRST:$ADMIN_PASS_TRIM" \
      -H "Content-Type: application/json" \
      -d "$PAYLOAD")
  fi
fi

if ! echo "$CREATE_JSON" | jq -e '.success == true and (.intake_url | length > 0)' >/dev/null 2>&1; then
  echo "Error: failed to create intake (set SECRETS_API_KEY or ADMIN_EMAILS+ADMIN_ACCESS_PASSWORD)" >&2
  echo "$CREATE_JSON" | jq . >&2 2>/dev/null || echo "$CREATE_JSON" >&2
  exit 1
fi

TOKEN="$(echo "$CREATE_JSON" | jq -r '.token')"
INTAKE_URL="$(echo "$CREATE_JSON" | jq -r '.intake_url')"

printf '%s\n' "$INTAKE_URL"

if [ "$POLL" -ne 1 ]; then
  exit 0
fi

deadline=$((SECONDS + EXPIRES_N * 60))
while [ $SECONDS -lt $deadline ]; do
  STATUS_JSON=""
  if [ -n "$SECRETS_API_KEY" ]; then
    STATUS_JSON=$(curl -sS -H "Authorization: Bearer $SECRETS_API_KEY" "$STUDIO_URL/api/secrets/intake/$TOKEN/status")
  fi
  if ! echo "$STATUS_JSON" | jq -e '.success == true' >/dev/null 2>&1; then
    STATUS_JSON=$(curl -sS -u "$ADMIN_EMAIL_FIRST:$ADMIN_PASS_TRIM" "$STUDIO_URL/api/secrets/intake/$TOKEN/status")
  fi

  ST="$(echo "$STATUS_JSON" | jq -r '.status // empty')"
  SN="$(echo "$STATUS_JSON" | jq -r '.secret_name // empty')"

  if [ "$ST" = "received" ]; then
    echo "✓ secret received: $SN" >&2
    exit 0
  fi
  if [ "$ST" = "expired" ]; then
    echo "Error: intake expired before the secret was submitted" >&2
    exit 1
  fi

  sleep 5
done

echo "Error: poll timed out after ${EXPIRES_N} minutes" >&2
exit 1
