#!/usr/bin/env bash
# Populate the Studio Secrets Vault from .env.secrets
# Reads key=value pairs from .env.secrets and pushes each to the vault API.
# Usage: ./scripts/populate-vault.sh
#        VAULT_URL=https://custom.url ./scripts/populate-vault.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load SECRETS_API_KEY
if [ -f "$REPO_ROOT/.env.local" ]; then
  set -a; source "$REPO_ROOT/.env.local"; set +a
fi
if [ -f "$REPO_ROOT/apps/studio/.env.local" ]; then
  set -a; source "$REPO_ROOT/apps/studio/.env.local"; set +a
fi

VAULT_URL="${VAULT_URL:-https://paperworklabs.com}"
SECRETS_API_KEY="${SECRETS_API_KEY:?Set SECRETS_API_KEY in .env.local}"
SECRETS_FILE="${1:-$REPO_ROOT/.env.secrets}"

if [ ! -f "$SECRETS_FILE" ]; then
  echo "ERROR: $SECRETS_FILE not found. Run 'make secrets' first, or pass a file path."
  exit 1
fi

echo "Populating vault at ${VAULT_URL} from ${SECRETS_FILE}..."
echo ""

count=0
errors=0
current_service="general"
pending_expires=""

while IFS= read -r line; do
  # Track section headers (e.g. "# === OPENAI ===") to derive service name
  if [[ "$line" =~ ^#\ ===\ ([A-Z0-9_-]+) ]]; then
    current_service="${BASH_REMATCH[1],,}"
    current_service="${current_service//-/_}"
    continue
  fi

  # Track "Expires: YYYY-MM-DD" anywhere in a comment — applies to the NEXT key=value line
  if [[ "$line" =~ ^# ]] && [[ "$line" =~ [Ee]xpires:\ ([0-9]{4}-[0-9]{2}-[0-9]{2}) ]]; then
    pending_expires="${BASH_REMATCH[1]}T00:00:00Z"
    continue
  fi

  # Skip comments and empty lines
  [[ -z "$line" || "$line" =~ ^# ]] && continue
  
  name="${line%%=*}"
  value="${line#*=}"
  
  # Skip if name is empty
  [[ -z "$name" ]] && continue

  # Build JSON payload (with optional expires_at)
  if [ -n "$pending_expires" ]; then
    payload=$(jq -n --arg n "$name" --arg v "$value" --arg s "$current_service" --arg e "$pending_expires" \
      '{name: $n, value: $v, service: $s, expires_at: $e}')
    pending_expires=""
  else
    payload=$(jq -n --arg n "$name" --arg v "$value" --arg s "$current_service" \
      '{name: $n, value: $v, service: $s}')
  fi
  
  resp=$(curl -s -w "\n%{http_code}" -X POST "${VAULT_URL}/api/secrets" \
    -H "Authorization: Bearer ${SECRETS_API_KEY}" \
    -H "Content-Type: application/json" \
    -d "$payload" 2>/dev/null)
  
  http_code=$(echo "$resp" | tail -1)
  
  if [ "$http_code" = "201" ] || [ "$http_code" = "200" ]; then
    echo "  ✓ ${name} (${current_service})"
    ((count++))
  else
    body=$(echo "$resp" | sed '$d')
    echo "  ✗ ${name} (HTTP ${http_code}): ${body}"
    ((errors++))
  fi
done < "$SECRETS_FILE"

echo ""
echo "Done: ${count} pushed, ${errors} errors"
