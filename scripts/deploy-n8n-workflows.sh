#!/usr/bin/env bash
# Deploy n8n workflows to Hetzner: import, publish, restart, verify.
#
# Usage:
#   ./scripts/deploy-n8n-workflows.sh
#   ./scripts/deploy-n8n-workflows.sh root@my-server.example.com
#
# Env overrides:
#   N8N_DEPLOY_HOST          SSH target (default: root@204.168.147.100)
#   N8N_CONTAINER            n8n container name (default: paperwork-ops-n8n-1)
#   N8N_PUBLIC_URL           Public n8n URL for liveness check (default: https://n8n.paperworklabs.com)
#   WORKFLOWS_DIR            Local workflows directory (default: infra/hetzner/workflows)
#   SLACK_ALERTS_WEBHOOK_URL Incoming webhook for deploy notifications (optional)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

HOST="${1:-${N8N_DEPLOY_HOST:-root@204.168.147.100}}"
N8N_CONTAINER="${N8N_CONTAINER:-paperwork-ops-n8n-1}"
N8N_PUBLIC_URL="${N8N_PUBLIC_URL:-https://n8n.paperworklabs.com}"
WORKFLOWS_DIR="${WORKFLOWS_DIR:-$ROOT_DIR/infra/hetzner/workflows}"
REMOTE_TMP="/tmp/paperwork-workflows"

slack_notify() {
  local msg="$1"
  if [[ -n "${SLACK_ALERTS_WEBHOOK_URL:-}" ]]; then
    jq -n --arg text "$msg" '{text: $text}' | \
      curl -sf -X POST "$SLACK_ALERTS_WEBHOOK_URL" -H 'Content-type: application/json' -d @- >/dev/null 2>&1 || true
  fi
}

if [[ ! -d "$WORKFLOWS_DIR" ]]; then
  echo "Error: Workflows directory not found: $WORKFLOWS_DIR" >&2
  exit 1
fi

WORKFLOW_FILES=("$WORKFLOWS_DIR"/*.json)
if [[ ! -e "${WORKFLOW_FILES[0]}" ]]; then
  echo "Error: No JSON files in $WORKFLOWS_DIR" >&2
  exit 1
fi

echo "Deploying n8n workflows to $HOST"
echo "  Workflows: $WORKFLOWS_DIR"
echo "  n8n container: $N8N_CONTAINER"
echo ""

echo "[1/5] Copying workflow files..."
ssh "$HOST" "mkdir -p $REMOTE_TMP"
scp -q "$WORKFLOWS_DIR"/*.json "$HOST:$REMOTE_TMP/"

echo "[2/5] Importing workflows..."
ssh "$HOST" 'for f in '"$REMOTE_TMP"'/*.json; do
  name=$(basename "$f")
  docker cp "$f" '"$N8N_CONTAINER"':/tmp/$name
  docker exec '"$N8N_CONTAINER"' n8n import:workflow --input="/tmp/$name"
  echo "  Imported: $name"
done'

echo "[3/5] Publishing workflows..."
FAILED=0
IDS=$(ssh "$HOST" "docker exec $N8N_CONTAINER n8n list:workflow --onlyId 2>/dev/null" || true)
if [[ -z "$IDS" ]]; then
  echo "WARNING: Could not list workflow IDs"
  FAILED=1
else
  for id in $IDS; do
    if ! ssh "$HOST" "docker exec $N8N_CONTAINER n8n publish:workflow --id=\"$id\"" 2>&1; then
      echo "ERROR: Failed to publish workflow $id"
      FAILED=1
    fi
  done
fi

echo "[4/5] Restarting n8n..."
ssh "$HOST" "docker restart $N8N_CONTAINER"

echo "[5/5] Verifying activation (waiting 15s)..."
sleep 15
TOTAL=$(ssh "$HOST" "docker exec $N8N_CONTAINER n8n list:workflow --onlyId 2>/dev/null | wc -l | tr -d ' '" || echo "0")
ACTIVE=$(ssh "$HOST" "docker exec $N8N_CONTAINER n8n list:workflow --active=true --onlyId 2>/dev/null | wc -l | tr -d ' '" || echo "0")
N8N_STATUS=$(curl -sf -o /dev/null -w '%{http_code}' "$N8N_PUBLIC_URL/" --max-time 10 || echo "000")

echo ""
if [[ "$ACTIVE" -ne "$TOTAL" ]] || [[ "$FAILED" -ne 0 ]]; then
  INACTIVE=$(ssh "$HOST" "docker exec $N8N_CONTAINER n8n list:workflow --active=false 2>/dev/null" | tr '\n' ', ' || echo "unknown")
  echo "DEPLOY FAILED: $ACTIVE/$TOTAL workflows active. n8n: $N8N_STATUS" >&2
  echo "Inactive: $INACTIVE" >&2
  slack_notify ":rotating_light: *n8n deploy FAILED*
$ACTIVE/$TOTAL workflows active.
n8n reachable: $N8N_STATUS"
  exit 1
fi

echo "Deploy complete. $ACTIVE/$TOTAL workflows active. n8n: $N8N_STATUS"
slack_notify ":white_check_mark: *n8n deploy complete*
• $ACTIVE/$TOTAL workflows active
• n8n reachable ($N8N_STATUS)"
