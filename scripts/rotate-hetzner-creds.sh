#!/usr/bin/env bash
# Rotate all credentials on the Hetzner VPS (postgres, redis, n8n, postiz).
# Run from your local machine: ./scripts/rotate-hetzner-creds.sh
# Requires: SSH access to root@204.168.147.100
#
# After running, copy the printed values and update:
#   1. .env.secrets (locally)
#   2. Vault (via populate-vault.sh)
#   3. n8n credentials (via n8n API — handled separately)

set -euo pipefail

HETZNER_HOST="204.168.147.100"
HETZNER_USER="root"
COMPOSE_DIR="/opt/paperwork-ops"

echo "=== Hetzner Credential Rotation ==="
echo ""

NEW_POSTGRES_PASS=$(openssl rand -hex 16)
NEW_REDIS_PASS=$(openssl rand -hex 16)
NEW_N8N_PASSWORD=$(openssl rand -hex 8)
NEW_N8N_ENCRYPTION_KEY=$(openssl rand -hex 16)
NEW_POSTIZ_JWT=$(openssl rand -hex 32)

echo "Generated new credentials locally."
echo ""

ssh "${HETZNER_USER}@${HETZNER_HOST}" bash -s -- \
  "$NEW_POSTGRES_PASS" "$NEW_REDIS_PASS" "$NEW_N8N_PASSWORD" "$NEW_N8N_ENCRYPTION_KEY" "$NEW_POSTIZ_JWT" \
  <<'REMOTE_SCRIPT'
set -euo pipefail

NEW_PG_PASS="$1"
NEW_REDIS_PASS="$2"
NEW_N8N_PASS="$3"
NEW_N8N_ENC="$4"
NEW_POSTIZ_JWT="$5"
COMPOSE_DIR="/opt/paperwork-ops"

cd "$COMPOSE_DIR"

echo "[1/5] Changing PostgreSQL password in running container..."
docker compose exec -T postgres psql -U ops -d ops -c "ALTER USER ops PASSWORD '$NEW_PG_PASS';" 2>/dev/null && echo "  OK" || echo "  WARN: psql command failed (may need different user)"

echo "[2/5] Changing Redis password in running container..."
OLD_REDIS_PASS=$(grep '^REDIS_PASSWORD=' .env | cut -d= -f2-)
docker compose exec -T redis redis-cli -a "$OLD_REDIS_PASS" CONFIG SET requirepass "$NEW_REDIS_PASS" 2>/dev/null && echo "  OK" || echo "  WARN: redis-cli command failed"

echo "[3/5] Backing up current .env..."
cp .env ".env.backup.$(date +%Y%m%d%H%M%S)"
echo "  OK"

echo "[4/5] Updating .env with new values..."
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$NEW_PG_PASS|" .env
sed -i "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=$NEW_REDIS_PASS|" .env
sed -i "s|^N8N_PASSWORD=.*|N8N_PASSWORD=$NEW_N8N_PASS|" .env
sed -i "s|^POSTIZ_JWT_SECRET=.*|POSTIZ_JWT_SECRET=$NEW_POSTIZ_JWT|" .env

if grep -q '^N8N_ENCRYPTION_KEY=' .env; then
  sed -i "s|^N8N_ENCRYPTION_KEY=.*|N8N_ENCRYPTION_KEY=$NEW_N8N_ENC|" .env
else
  echo "N8N_ENCRYPTION_KEY=$NEW_N8N_ENC" >> .env
fi

if grep -q '^SLACK_ALERTS_WEBHOOK_URL=' .env; then
  echo "  NOTE: SLACK_ALERTS_WEBHOOK_URL preserved as-is (rotate separately via vault)"
fi

echo "  OK"

echo "[5/5] Restarting all containers..."
docker compose down
docker compose up -d
echo "  Waiting 15s for services to stabilize..."
sleep 15

echo ""
echo "=== Container Status ==="
docker compose ps --format "table {{.Name}}\t{{.Status}}" 2>/dev/null || docker compose ps

echo ""
echo "=== Health Checks ==="
docker compose exec -T postgres pg_isready -U ops 2>/dev/null && echo "  Postgres: healthy" || echo "  Postgres: UNHEALTHY"
docker compose exec -T redis redis-cli -a "$NEW_REDIS_PASS" ping 2>/dev/null && echo "  Redis: healthy" || echo "  Redis: UNHEALTHY"
REMOTE_SCRIPT

echo ""
echo "========================================="
echo "=== NEW VALUES (copy to .env.secrets) ==="
echo "========================================="
echo ""
echo "HETZNER_POSTGRES_PASSWORD=$NEW_POSTGRES_PASS"
echo "HETZNER_REDIS_PASSWORD=$NEW_REDIS_PASS"
echo "N8N_BASIC_AUTH_PASSWORD=$NEW_N8N_PASSWORD"
echo "N8N_ENCRYPTION_KEY=$NEW_N8N_ENCRYPTION_KEY"
echo "POSTIZ_JWT_SECRET=$NEW_POSTIZ_JWT"
echo ""
echo "========================================="
echo "NEXT STEPS:"
echo "  1. Update .env.secrets with values above"
echo "  2. Run ./scripts/populate-vault.sh"
echo "  3. n8n credentials will be re-entered via API (tell the agent the new values)"
echo "========================================="
