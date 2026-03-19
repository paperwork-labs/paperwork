#!/usr/bin/env bash
set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load env vars — merge repo root + Studio (Vercel pull writes apps/studio/.env.local; SECRETS_API_KEY lives there)
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
# Trim accidental newlines from .env sourcing
SECRETS_API_KEY="$(printf '%s' "${SECRETS_API_KEY:-}" | tr -d '\r\n')"
export SECRETS_API_KEY

OUTPUT_FILE="$REPO_ROOT/.env.secrets"

ADMIN_EMAIL_FIRST="$(printf '%s' "${ADMIN_EMAILS:-}" | cut -d, -f1 | tr -d ' \"')"
ADMIN_PASS_TRIM="$(printf '%s' "${ADMIN_ACCESS_PASSWORD:-}" | tr -d '\r\n')"

echo "Syncing secrets from $STUDIO_URL/api/secrets/export..."

HTTP_CODE="000"
if [ -n "$SECRETS_API_KEY" ]; then
  HTTP_CODE=$(curl -s -o "$OUTPUT_FILE" -w "%{http_code}" \
    -H "Authorization: Bearer $SECRETS_API_KEY" \
    "$STUDIO_URL/api/secrets/export")
fi

if [ "$HTTP_CODE" != "200" ] && [ -n "$ADMIN_EMAIL_FIRST" ] && [ -n "$ADMIN_PASS_TRIM" ]; then
  echo "Bearer token failed or missing (HTTP ${HTTP_CODE:-n/a}); trying Studio Basic Auth..."
  HTTP_CODE=$(curl -s -o "$OUTPUT_FILE" -w "%{http_code}" \
    -u "$ADMIN_EMAIL_FIRST:$ADMIN_PASS_TRIM" \
    "$STUDIO_URL/api/secrets/export")
fi

if [ "$HTTP_CODE" != "200" ]; then
  echo "ERROR: API returned HTTP $HTTP_CODE"
  cat "$OUTPUT_FILE" 2>/dev/null || true
  rm -f "$OUTPUT_FILE"
  echo "Set SECRETS_API_KEY or ADMIN_EMAILS+ADMIN_ACCESS_PASSWORD in apps/studio/.env.local" >&2
  exit 1
fi

chmod 600 "$OUTPUT_FILE"
SECRET_COUNT=$(grep -c "^[A-Z]" "$OUTPUT_FILE" 2>/dev/null || echo "0")
echo "Synced $SECRET_COUNT secrets to $OUTPUT_FILE"
