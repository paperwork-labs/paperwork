#!/usr/bin/env bash
# Deploy n8n workflows to Hetzner and reactivate them.
#
# n8n import:workflow deactivates workflows. This script imports, publishes,
# activates all workflows, and restarts n8n so activation takes effect (per
# n8n docs: CLI activation requires restart).
#
# Usage:
#   ./scripts/deploy-n8n-workflows.sh
#   ./scripts/deploy-n8n-workflows.sh root@my-server.example.com
#
# Env overrides:
#   N8N_DEPLOY_HOST     SSH target (default: root@204.168.147.100)
#   N8N_CONTAINER       n8n container name (default: paperwork-ops-n8n-1)
#   POSTGRES_CONTAINER   Postgres container name (default: paperwork-ops-postgres-1)
#   POSTGRES_USER       Postgres user for n8n DB (default: filefree_ops)
#   WORKFLOWS_DIR       Local workflows directory (default: infra/hetzner/workflows)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

HOST="${1:-${N8N_DEPLOY_HOST:-root@204.168.147.100}}"
N8N_CONTAINER="${N8N_CONTAINER:-paperwork-ops-n8n-1}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-paperwork-ops-postgres-1}"
POSTGRES_USER="${POSTGRES_USER:-filefree_ops}"
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

echo "[1/5] Copying workflow files..."
ssh "$HOST" "mkdir -p $REMOTE_TMP"
scp -q "$WORKFLOWS_DIR"/*.json "$HOST:$REMOTE_TMP/"

echo "[2/5] Importing workflows (deactivates them)..."
ssh "$HOST" "for f in $REMOTE_TMP/*.json; do
  name=\$(basename \"\$f\")
  docker cp \"\$f\" $N8N_CONTAINER:/tmp/\$name
  docker exec $N8N_CONTAINER n8n import:workflow --input=\"/tmp/\$name\"
done"

echo "[3/5] Publishing workflows..."
ssh "$HOST" "ids=\$(docker exec $POSTGRES_CONTAINER psql -U $POSTGRES_USER -d n8n -At -c 'SELECT id FROM workflow_entity;'); for id in \$ids; do docker exec $N8N_CONTAINER n8n publish:workflow --id=\$id 2>/dev/null || true; done"

echo "[4/5] Activating all workflows..."
ssh "$HOST" "docker exec -u node $N8N_CONTAINER n8n update:workflow --all --active=true"

echo "[5/5] Restarting n8n (activation takes effect after restart)..."
ssh "$HOST" "docker restart $N8N_CONTAINER"

echo ""
echo "Done. Workflows are imported, published, active, and n8n has been restarted."
