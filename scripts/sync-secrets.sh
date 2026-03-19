#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load env vars from .env.local if it exists
if [ -f "$REPO_ROOT/.env.local" ]; then
  set -a
  source "$REPO_ROOT/.env.local"
  set +a
fi

STUDIO_URL="${STUDIO_URL:-https://paperworklabs.com}"
API_KEY="${SECRETS_API_KEY:?SECRETS_API_KEY is required. Set it in .env.local or export it.}"

OUTPUT_FILE="$REPO_ROOT/.env.secrets"

echo "Syncing secrets from $STUDIO_URL/api/secrets/export..."

HTTP_CODE=$(curl -s -o "$OUTPUT_FILE" -w "%{http_code}" \
  -H "Authorization: Bearer $API_KEY" \
  "$STUDIO_URL/api/secrets/export")

if [ "$HTTP_CODE" != "200" ]; then
  echo "ERROR: API returned HTTP $HTTP_CODE"
  cat "$OUTPUT_FILE"
  rm -f "$OUTPUT_FILE"
  exit 1
fi

SECRET_COUNT=$(grep -c "^[A-Z]" "$OUTPUT_FILE" 2>/dev/null || echo "0")
echo "Synced $SECRET_COUNT secrets to $OUTPUT_FILE"
