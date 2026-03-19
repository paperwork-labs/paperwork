#!/usr/bin/env bash
set -euo pipefail

# Paperwork Labs — Environment Variable Validator
# Checks Studio code, Vercel production, .env.local, and Hetzner/n8n for consistency.
# Usage: make env-check  (or: bash scripts/env-check.sh)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

PASS=0
WARN=0
FAIL=0

pass()  { echo -e "  ${GREEN}PASS${NC}  $1"; PASS=$((PASS + 1)); }
warn()  { echo -e "  ${YELLOW}WARN${NC}  $1"; WARN=$((WARN + 1)); }
fail()  { echo -e "  ${RED}FAIL${NC}  $1"; FAIL=$((FAIL + 1)); }
header(){ echo -e "\n${BOLD}${CYAN}── $1 ──${NC}"; }

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STUDIO_DIR="$REPO_ROOT/apps/studio"
WORKFLOW_DIR="$REPO_ROOT/infra/hetzner/workflows"
ENV_LOCAL="$STUDIO_DIR/.env.local"

STUDIO_CRITICAL=(DATABASE_URL SECRETS_ENCRYPTION_KEY ADMIN_EMAILS ADMIN_ACCESS_PASSWORD)
STUDIO_IMPORTANT=(N8N_API_URL N8N_API_KEY GITHUB_TOKEN SLACK_BOT_TOKEN SECRETS_API_KEY)
STUDIO_OPTIONAL=(RENDER_API_KEY VERCEL_API_TOKEN NEON_API_KEY UPSTASH_REDIS_REST_URL UPSTASH_REDIS_REST_TOKEN POSTIZ_URL N8N_BASIC_AUTH_USER N8N_BASIC_AUTH_PASSWORD NEXT_PUBLIC_POSTHOG_KEY NEXT_PUBLIC_POSTHOG_HOST POSTHOG_DASHBOARD_URL)

HETZNER_HOST="${HETZNER_HOST:-204.168.147.100}"
N8N_CONTAINER="paperwork-ops-n8n-1"

# ── 1. Studio .env.local ──

header "Studio .env.local"

if [[ ! -f "$ENV_LOCAL" ]]; then
  fail ".env.local does not exist — run: make env-pull"
else
  for var in "${STUDIO_CRITICAL[@]}"; do
    if grep -qE "^${var}=" "$ENV_LOCAL" 2>/dev/null; then
      val=$(grep -E "^${var}=" "$ENV_LOCAL" | head -1 | cut -d= -f2-)
      if [[ -z "$val" ]]; then
        fail "$var is set but EMPTY in .env.local"
      else
        pass "$var"
      fi
    elif grep -qE "^#.*${var}=" "$ENV_LOCAL" 2>/dev/null; then
      fail "$var is COMMENTED OUT in .env.local"
    else
      fail "$var is MISSING from .env.local"
    fi
  done

  for var in "${STUDIO_IMPORTANT[@]}"; do
    if grep -qE "^${var}=" "$ENV_LOCAL" 2>/dev/null; then
      val=$(grep -E "^${var}=" "$ENV_LOCAL" | head -1 | cut -d= -f2-)
      if [[ -z "$val" ]]; then
        warn "$var is set but EMPTY in .env.local"
      else
        pass "$var"
      fi
    elif grep -qE "^#.*${var}=" "$ENV_LOCAL" 2>/dev/null; then
      warn "$var is COMMENTED OUT in .env.local"
    else
      warn "$var is MISSING from .env.local (important)"
    fi
  done

  for var in "${STUDIO_OPTIONAL[@]}"; do
    if grep -qE "^${var}=" "$ENV_LOCAL" 2>/dev/null; then
      pass "$var"
    else
      : # optional vars don't generate output
    fi
  done
fi

# ── 2. Vercel Production ──

header "Vercel Production"

if command -v vercel &>/dev/null && [[ -f "$STUDIO_DIR/.vercel/project.json" ]]; then
  VERCEL_VARS=$(cd "$STUDIO_DIR" && vercel env ls production 2>/dev/null | awk 'NR>2 && NF{print $1}' || true)
  if [[ -z "$VERCEL_VARS" ]]; then
    warn "Could not list Vercel env vars (auth issue or no project link)"
  else
    for var in "${STUDIO_CRITICAL[@]}" "${STUDIO_IMPORTANT[@]}"; do
      if echo "$VERCEL_VARS" | grep -qx "$var"; then
        pass "$var in Vercel"
      else
        fail "$var MISSING from Vercel production"
      fi
    done
  fi
else
  warn "Vercel CLI not available or project not linked — skipping Vercel check"
fi

# ── 3. Vercel vs .env.local drift ──

header "Vercel vs .env.local drift"

if [[ -n "${VERCEL_VARS:-}" ]] && [[ -f "$ENV_LOCAL" ]]; then
  LOCAL_VARS=$(grep -E '^[A-Z0-9_]+=.' "$ENV_LOCAL" 2>/dev/null | cut -d= -f1 | sort -u || true)
  DRIFT_COUNT=0
  for var in "${STUDIO_CRITICAL[@]}" "${STUDIO_IMPORTANT[@]}"; do
    IN_VERCEL=$(echo "$VERCEL_VARS" | grep -cx "$var" || true)
    IN_LOCAL=$(echo "$LOCAL_VARS" | grep -cx "$var" || true)
    if [[ "$IN_VERCEL" -gt 0 ]] && [[ "$IN_LOCAL" -eq 0 ]]; then
      fail "$var is in Vercel but not active in .env.local — run: make env-pull"
      ((DRIFT_COUNT++))
    fi
  done
  if [[ "$DRIFT_COUNT" -eq 0 ]]; then
    pass "No drift detected between Vercel and .env.local"
  fi
else
  warn "Skipping drift check (Vercel vars or .env.local unavailable)"
fi

# ── 4. n8n Workflow env vars ──

header "n8n Workflow env references"

if [[ -d "$WORKFLOW_DIR" ]]; then
  WORKFLOW_ENVS=$(grep -ohE '\$env\.[A-Z0-9_]+' "$WORKFLOW_DIR"/*.json 2>/dev/null | sed 's/\$env\.//' | sort -u || true)
  if [[ -n "$WORKFLOW_ENVS" ]]; then
    echo -e "  Workflows reference: $(echo "$WORKFLOW_ENVS" | tr '\n' ', ' | sed 's/,$//')"
  fi
fi

# ── 5. Hetzner / n8n container (optional — skips if SSH fails) ──

header "Hetzner n8n container"

if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o BatchMode=yes "root@$HETZNER_HOST" "true" 2>/dev/null; then
  CONTAINER_ENVS=$(ssh -o ConnectTimeout=5 "root@$HETZNER_HOST" \
    "docker exec $N8N_CONTAINER printenv 2>/dev/null | grep -E '^(GITHUB_TOKEN|SLACK_BOT_TOKEN|N8N_API_KEY|SLACK_ALERTS_WEBHOOK_URL)=' | cut -d= -f1" 2>/dev/null || true)

  for var in GITHUB_TOKEN SLACK_BOT_TOKEN N8N_API_KEY; do
    if echo "$CONTAINER_ENVS" | grep -qx "$var"; then
      pass "$var in n8n container"
    else
      fail "$var MISSING from n8n container"
    fi
  done

  for var in SLACK_ALERTS_WEBHOOK_URL; do
    if echo "$CONTAINER_ENVS" | grep -qx "$var"; then
      pass "$var in n8n container"
    else
      warn "$var missing from n8n container (optional)"
    fi
  done
else
  warn "Cannot reach Hetzner ($HETZNER_HOST) — skipping container check"
fi

# ── Summary ──

echo ""
echo -e "${BOLD}━━━ Summary ━━━${NC}"
echo -e "  ${GREEN}PASS${NC}: $PASS   ${YELLOW}WARN${NC}: $WARN   ${RED}FAIL${NC}: $FAIL"

if [[ "$FAIL" -gt 0 ]]; then
  echo -e "\n${RED}Environment has $FAIL issue(s). Fix before deploying.${NC}"
  exit 1
elif [[ "$WARN" -gt 0 ]]; then
  echo -e "\n${YELLOW}Environment OK with $WARN warning(s).${NC}"
  exit 0
else
  echo -e "\n${GREEN}All checks passed.${NC}"
  exit 0
fi
