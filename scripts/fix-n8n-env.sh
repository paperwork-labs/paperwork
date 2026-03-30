#!/usr/bin/env bash
# Diagnose and fix n8n environment on Hetzner.
# Run: ./scripts/fix-n8n-env.sh
#
# This script checks that N8N_API_KEY is properly set in the Hetzner .env file
# and passed to the n8n container, then restarts the container if needed.

set -euo pipefail

HOST="${1:-${N8N_DEPLOY_HOST:-root@204.168.147.100}}"
ENV_FILE="/opt/paperwork-ops/.env"

echo "=== n8n Environment Diagnostic ==="
echo "Host: $HOST"
echo ""

echo "[1/5] Checking N8N_API_KEY in $ENV_FILE..."
HAS_KEY=$(ssh "$HOST" "grep -q '^N8N_API_KEY=.' $ENV_FILE && echo yes || echo no")
if [[ "$HAS_KEY" == "yes" ]]; then
  echo "  ✓ N8N_API_KEY is set in $ENV_FILE"
else
  echo "  ✗ N8N_API_KEY is NOT set in $ENV_FILE"
  echo ""
  echo "  To fix: Add N8N_API_KEY to $ENV_FILE on Hetzner."
  echo "  You can generate one from n8n UI > Settings > API > Create API Key"
  echo "  Then run: ssh $HOST 'echo \"N8N_API_KEY=your-key-here\" >> $ENV_FILE'"
  exit 1
fi

echo ""
echo "[2/5] Checking n8n container environment..."
CONTAINER_KEY=$(ssh "$HOST" "docker exec n8n printenv N8N_API_KEY 2>/dev/null || echo ''")
if [[ -n "$CONTAINER_KEY" ]]; then
  echo "  ✓ N8N_API_KEY is available inside n8n container"
else
  echo "  ✗ N8N_API_KEY is NOT in container environment"
  echo ""
  echo "  Fix: Restart n8n container to pick up env vars."
  read -p "  Restart n8n now? [y/N] " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "  Restarting n8n container..."
    ssh "$HOST" "cd /opt/paperwork-ops && docker compose up -d --force-recreate n8n"
    sleep 5
    CONTAINER_KEY=$(ssh "$HOST" "docker exec n8n printenv N8N_API_KEY 2>/dev/null || echo ''")
    if [[ -n "$CONTAINER_KEY" ]]; then
      echo "  ✓ N8N_API_KEY now available after restart"
    else
      echo "  ✗ Still not available - check compose.yaml"
      exit 1
    fi
  else
    echo "  Skipping restart."
    exit 1
  fi
fi

echo ""
echo "[3/5] Testing n8n API with key..."
API_STATUS=$(ssh "$HOST" "
N8N_KEY=\$(grep '^N8N_API_KEY=' $ENV_FILE | cut -d= -f2-)
curl -s -o /dev/null -w '%{http_code}' 'http://localhost:5678/api/v1/workflows?limit=1' -H \"X-N8N-API-KEY: \$N8N_KEY\"
")
if [[ "$API_STATUS" == "200" ]]; then
  echo "  ✓ n8n API responds with 200"
else
  echo "  ✗ n8n API returned HTTP $API_STATUS"
  exit 1
fi

echo ""
echo "[4/5] Checking workflow count..."
WF_COUNT=$(ssh "$HOST" "
N8N_KEY=\$(grep '^N8N_API_KEY=' $ENV_FILE | cut -d= -f2-)
curl -s 'http://localhost:5678/api/v1/workflows?limit=250' -H \"X-N8N-API-KEY: \$N8N_KEY\" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(len(d.get(\"data\",[])))'
" || echo "0")
ACTIVE_COUNT=$(ssh "$HOST" "
N8N_KEY=\$(grep '^N8N_API_KEY=' $ENV_FILE | cut -d= -f2-)
curl -s 'http://localhost:5678/api/v1/workflows?active=true&limit=250' -H \"X-N8N-API-KEY: \$N8N_KEY\" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(len(d.get(\"data\",[])))'
" || echo "0")
echo "  Workflows: $ACTIVE_COUNT/$WF_COUNT active"

echo ""
echo "[5/5] Testing in-container API access (simulating health check workflow)..."
INSIDE_STATUS=$(ssh "$HOST" "
docker exec n8n sh -c 'curl -s -o /dev/null -w \"%{http_code}\" \"http://localhost:5678/api/v1/workflows?limit=1\" -H \"X-N8N-API-KEY: \$N8N_API_KEY\"'
")
if [[ "$INSIDE_STATUS" == "200" ]]; then
  echo "  ✓ In-container API access works (HTTP $INSIDE_STATUS)"
else
  echo "  ✗ In-container API access failed (HTTP $INSIDE_STATUS)"
  echo ""
  echo "  The N8N_API_KEY env var may not be correct inside the container."
  echo "  Try: ssh $HOST 'cd /opt/paperwork-ops && docker compose up -d --force-recreate n8n'"
  exit 1
fi

echo ""
echo "=== All checks passed ==="
echo "n8n infra health check should now report correct workflow counts."
