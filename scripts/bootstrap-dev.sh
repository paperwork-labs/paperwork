#!/usr/bin/env bash
# Bootstrap a fresh clone: one key (SECRETS_API_KEY) pulls everything from Studio vault.
# Usage:
#   SECRETS_API_KEY=... ./scripts/bootstrap-dev.sh
#   ./scripts/bootstrap-dev.sh   # prompts if SECRETS_API_KEY unset
set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_LOCAL="$REPO_ROOT/.env.local"
STUDIO_URL="${STUDIO_URL:-https://paperworklabs.com}"

if [ -z "${SECRETS_API_KEY:-}" ]; then
  if [ -t 0 ]; then
    read -r -s -p "Enter SECRETS_API_KEY (Studio vault bearer): " SECRETS_API_KEY
    echo
  else
    echo "ERROR: Set SECRETS_API_KEY in the environment (non-interactive shell)." >&2
    exit 1
  fi
fi

SECRETS_API_KEY="$(printf '%s' "$SECRETS_API_KEY" | tr -d '\r\n')"
if [ -z "$SECRETS_API_KEY" ]; then
  echo "ERROR: SECRETS_API_KEY is empty." >&2
  exit 1
fi

echo "Writing SECRETS_API_KEY to $ENV_LOCAL (gitignored)..."
touch "$ENV_LOCAL"
TMP="${ENV_LOCAL}.tmp.$$"
if grep -q '^SECRETS_API_KEY=' "$ENV_LOCAL" 2>/dev/null; then
  grep -v '^SECRETS_API_KEY=' "$ENV_LOCAL" >"$TMP" || true
else
  cp "$ENV_LOCAL" "$TMP" 2>/dev/null || : >"$TMP"
fi
printf 'SECRETS_API_KEY=%s\n' "$SECRETS_API_KEY" >>"$TMP"
mv "$TMP" "$ENV_LOCAL"
chmod 600 "$ENV_LOCAL"

echo "Checking Studio reachability..."
BASE="${STUDIO_URL%/}"
HTTP_CODE="$(curl -sS -o /dev/null -w "%{http_code}" --max-time 15 "${BASE}/health" 2>/dev/null || echo "000")"
CHECK_URL="${BASE}/health"
if ! echo "$HTTP_CODE" | grep -qE '^[23][0-9][0-9]$'; then
  HTTP_CODE="$(curl -sS -o /dev/null -w "%{http_code}" --max-time 15 "$BASE" 2>/dev/null || echo "000")"
  CHECK_URL="$BASE"
fi
if echo "$HTTP_CODE" | grep -qE '^[23][0-9][0-9]$'; then
  echo "OK: Studio responded HTTP $HTTP_CODE ($CHECK_URL)"
else
  echo "WARN: Studio check returned HTTP $HTTP_CODE ($CHECK_URL). Continuing with vault sync..."
fi

echo "Syncing secrets from vault → .env.secrets ..."
(
  cd "$REPO_ROOT"
  export SECRETS_API_KEY
  export STUDIO_URL
  ./scripts/sync-secrets.sh
)

echo ""
echo "Bootstrap complete."
echo "  • $ENV_LOCAL — SECRETS_API_KEY"
echo "  • $REPO_ROOT/.env.secrets — all vault secrets (gitignored)"
echo "Next: source .env.secrets or use tooling that loads it; run Brain API from apis/brain/ per README."
