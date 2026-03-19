#!/usr/bin/env bash
# Populate the Studio Secrets Vault with all known credentials.
# Run AFTER PR #27 is merged and SECRETS_API_KEY is set on Vercel.
#
# Usage: VAULT_API_KEY=<your-key> ./scripts/populate-vault.sh
#        VAULT_API_KEY=<your-key> VAULT_URL=https://preview.vercel.app ./scripts/populate-vault.sh

set -euo pipefail

VAULT_URL="${VAULT_URL:-https://paperworklabs.com}"
API_KEY="${VAULT_API_KEY:?Set VAULT_API_KEY env var}"

push_secret() {
  local name="$1" value="$2" service="$3" location="${4:-}" description="${5:-}"

  resp=$(curl -s -w "\n%{http_code}" -X POST "${VAULT_URL}/api/secrets" \
    -H "Authorization: Bearer ${API_KEY}" \
    -H "Content-Type: application/json" \
    -d "$(jq -n \
      --arg n "$name" \
      --arg v "$value" \
      --arg s "$service" \
      --arg l "$location" \
      --arg d "$description" \
      '{name: $n, value: $v, service: $s, location: $l, description: $d}')")

  http_code=$(echo "$resp" | tail -1)
  body=$(echo "$resp" | sed '$d')

  if [ "$http_code" = "201" ] || [ "$http_code" = "200" ]; then
    echo "  ✓ ${name}"
  else
    echo "  ✗ ${name} (HTTP ${http_code}): ${body}"
  fi
}

echo "Populating vault at ${VAULT_URL}..."
echo ""

# ---------- Hetzner VPS ----------
echo "=== Hetzner ==="
push_secret "HETZNER_HOST" "204.168.147.100" "hetzner" "Hetzner CX33 VPS" "Primary ops server IP address"
push_secret "HETZNER_HOST_FINGERPRINT_ECDSA" "SHA256:Ewa+mlgkgScmUYc9KJEEZNoo/npMasQFPM4U2DtjEWI" "hetzner" "GitHub Actions" "ECDSA host key fingerprint (used by appleboy/ssh-action)"
push_secret "HETZNER_HOST_FINGERPRINT_ED25519" "SHA256:uFSWEJnDTQwB9lLJGFw75QdVV7R4UUv1nQLImzYTh5g" "hetzner" "Hetzner VPS" "ED25519 host key fingerprint"

# ---------- Hetzner PostgreSQL ----------
echo ""
echo "=== Hetzner PostgreSQL ==="
push_secret "HETZNER_POSTGRES_USER" "filefree_ops" "hetzner-postgres" "Hetzner Docker" "PostgreSQL user for n8n + Postiz"
push_secret "HETZNER_POSTGRES_PASSWORD" "5b75e81bb6f35fbd3c351eb3d548b380" "hetzner-postgres" "Hetzner Docker" "PostgreSQL password"
push_secret "HETZNER_POSTGRES_DB" "filefree_ops" "hetzner-postgres" "Hetzner Docker" "Default database name"

# ---------- Hetzner Redis ----------
echo ""
echo "=== Hetzner Redis ==="
push_secret "HETZNER_REDIS_PASSWORD" "d309ee5757561f096a6033e110205b30" "hetzner-redis" "Hetzner Docker" "Redis password for n8n + Postiz"

# ---------- n8n ----------
echo ""
echo "=== n8n ==="
push_secret "N8N_HOST" "n8n.paperworklabs.com" "n8n" "Hetzner VPS" "n8n hostname"
push_secret "N8N_BASIC_AUTH_USER" "admin" "n8n" "Hetzner .env" "n8n admin username"
push_secret "N8N_BASIC_AUTH_PASSWORD" "fd293ff5accdd1e2" "n8n" "Hetzner .env" "n8n admin password"
push_secret "N8N_ENCRYPTION_KEY" "KQuERdDSTgyVuq5Yu83KdsZHSEg0k1f1" "n8n" "n8n container config" "Internal credential encryption key"

# ---------- Postiz ----------
echo ""
echo "=== Postiz ==="
push_secret "POSTIZ_HOST" "social.paperworklabs.com" "postiz" "Hetzner .env" "Postiz hostname"
push_secret "POSTIZ_JWT_SECRET" "8037076ef3cf2ad3e50a6dce7a81f1f896c14b50dce1d4afa2dfe7956f65387d" "postiz" "Hetzner .env" "JWT signing secret"

# ---------- Slack ----------
echo ""
echo "=== Slack ==="
push_secret "SLACK_BOT_TOKEN" "xoxb-10719522530500-10719920126772-JDSk1R4TD4mKYrMoC0EH7Idt" "slack" "Slack API / n8n / .env.local" "Bot User OAuth Token for Paperwork Labs workspace"
push_secret "SLACK_ALERTS_WEBHOOK_URL" "***REDACTED***" "slack" "Hetzner .env / GitHub Actions" "Incoming webhook for #alerts channel"

# ---------- GitHub ----------
echo ""
echo "=== GitHub ==="
push_secret "GITHUB_PAT" "***REDACTED***" "github" "Hetzner .env / n8n" "GitHub OAuth token for n8n workflows"
push_secret "GITHUB_PAT_FINEGRAINED" "***REDACTED***" "github" "n8n credential" "Fine-grained PAT (paperwork-labs org, repo read)"

# ---------- OpenAI ----------
echo ""
echo "=== OpenAI ==="
push_secret "OPENAI_API_KEY" "***REDACTED***" "openai" "n8n credential" "OpenAI project API key for GPT-4o / GPT-4o-mini"

# ---------- Studio / Vercel ----------
echo ""
echo "=== Studio / Vercel ==="
push_secret "ADMIN_EMAILS" "sankalp@paperworklabs.com" "studio" "Vercel env vars" "Comma-separated admin emails for Studio Basic Auth"
push_secret "ADMIN_ACCESS_PASSWORD" "olgamila" "studio" "Vercel env vars" "Studio admin panel password"
push_secret "VERCEL_PROJECT_ID" "prj_FZvJJnDdQqawjBpJAwC0SuwyMzFT" "vercel" ".vercel/project.json" "Studio Vercel project ID"
push_secret "VERCEL_TEAM_ID" "team_RwfzJ9ySyLuVcoWdKJfXC7h5" "vercel" "Vercel API" "Vercel team/account ID"

# ---------- FileFree ----------
echo ""
echo "=== FileFree ==="
push_secret "FILEFREE_API_URL" "https://api.filefree.ai" "filefree" "apps/filefree/.env.production" "FileFree backend API URL"

echo ""
echo "=========================================="
echo "Done! ${VAULT_URL}/admin/secrets to review"
echo ""
echo "MISSING SECRETS (user must add manually):"
echo "  - VERCEL_TOKEN (vercel.com/account/tokens)"
echo "  - NEON_DATABASE_URL (console.neon.tech)"
echo "  - NEON_API_KEY (console.neon.tech/app/settings/api-keys)"
echo "  - UPSTASH_REDIS_REST_URL (console.upstash.com)"
echo "  - UPSTASH_REDIS_REST_TOKEN (console.upstash.com)"
echo "  - RENDER_API_KEY (dashboard.render.com/u/settings#api)"
echo "  - GCP_SERVICE_ACCOUNT_JSON (console.cloud.google.com)"
echo "  - POSTHOG_PROJECT_API_KEY (us.posthog.com project settings)"
echo "  - STRIPE_SECRET_KEY (dashboard.stripe.com/apikeys)"
echo "  - HETZNER_SSH_KEY (GitHub Actions — too large for API)"
echo "=========================================="
