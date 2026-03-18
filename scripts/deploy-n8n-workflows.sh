#!/usr/bin/env bash
# Deploy n8n workflows to Hetzner and reactivate them.
#
# n8n import:workflow deactivates workflows. This script imports them,
# activates each individually, and restarts n8n so activation takes effect.
#
# Usage:
#   ./scripts/deploy-n8n-workflows.sh
#   ./scripts/deploy-n8n-workflows.sh root@my-server.example.com
#
# Env overrides:
#   N8N_DEPLOY_HOST     SSH target (default: root@204.168.147.100)
#   N8N_CONTAINER       n8n container name (default: paperwork-ops-n8n-1)
#   WORKFLOWS_DIR       Local workflows directory (default: infra/hetzner/workflows)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

HOST="${1:-${N8N_DEPLOY_HOST:-root@204.168.147.100}}"
N8N_CONTAINER="${N8N_CONTAINER:-paperwork-ops-n8n-1}"
WORKFLOWS_DIR="${WORKFLOWS_DIR:-$ROOT_DIR/infra/hetzner/workflows}"
REMOTE_TMP="/tmp/paperwork-workflows"

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

echo "[1/4] Copying workflow files..."
ssh "$HOST" "mkdir -p $REMOTE_TMP"
scp -q "$WORKFLOWS_DIR"/*.json "$HOST:$REMOTE_TMP/"

echo "[2/4] Importing workflows..."
ssh "$HOST" "for f in $REMOTE_TMP/*.json; do
  name=\$(basename \"\$f\")
  docker cp \"\$f\" $N8N_CONTAINER:/tmp/\$name
  docker exec $N8N_CONTAINER n8n import:workflow --input=\"/tmp/\$name\"
done"

echo "[3/4] Activating workflows..."
ssh "$HOST" "IDS=\$(docker exec $N8N_CONTAINER n8n list:workflow --json 2>/dev/null | grep -o '\"id\":\"[^\"]*\"' | cut -d'\"' -f4 || true)
for id in \$IDS; do
  docker exec $N8N_CONTAINER n8n update:workflow --id=\"\$id\" --active=true 2>/dev/null || true
done"

echo "[4/4] Restarting n8n..."
ssh "$HOST" "docker restart $N8N_CONTAINER"

echo ""
echo "Done. Workflows imported, activated, and n8n restarted."
