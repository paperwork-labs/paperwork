#!/usr/bin/env bash
# Deploy n8n workflows to Hetzner via REST API: upsert, activate, verify.
#
# Usage:
#   ./scripts/deploy-n8n-workflows.sh
#   ./scripts/deploy-n8n-workflows.sh root@my-server.example.com
#
# Env overrides:
#   N8N_DEPLOY_HOST          SSH target (default: root@204.168.147.100)
#   N8N_PUBLIC_URL           Public n8n URL (default: https://n8n.paperworklabs.com)
#   WORKFLOWS_DIR            Local workflows directory (default: infra/hetzner/workflows)
#   SLACK_ALERTS_WEBHOOK_URL Incoming webhook for deploy notifications (optional)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

HOST="${1:-${N8N_DEPLOY_HOST:-root@204.168.147.100}}"
N8N_PUBLIC_URL="${N8N_PUBLIC_URL:-https://n8n.paperworklabs.com}"
WORKFLOWS_DIR="${WORKFLOWS_DIR:-$ROOT_DIR/infra/hetzner/workflows}"

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

echo "Deploying n8n workflows via REST API to $HOST"
echo "  Workflows: $WORKFLOWS_DIR (${#WORKFLOW_FILES[@]} files)"
echo ""

echo "[1/4] Uploading workflow files..."
ssh "$HOST" "mkdir -p /tmp/paperwork-workflows"
scp -q "$WORKFLOWS_DIR"/*.json "$HOST:/tmp/paperwork-workflows/"

echo "[2/4] Upserting workflows via REST API..."
ssh "$HOST" 'set -e
N8N_KEY=$(grep "^N8N_API_KEY=" /opt/paperwork-ops/.env | cut -d= -f2-)
API="http://localhost:5678/api/v1"

existing=$(curl -sfS "$API/workflows?limit=250" -H "X-N8N-API-KEY: $N8N_KEY") || {
  echo "Error: Failed to list existing workflows from n8n API" >&2
  exit 1
}

for f in /tmp/paperwork-workflows/*.json; do
  name=$(python3 -c "import json; print(json.load(open(\"$f\"))[\"name\"])" 2>/dev/null || echo "")
  if [ -z "$name" ]; then
    echo "SKIP: $f (no name field)"
    continue
  fi

  cleaned=$(python3 -c "
import json, sys
with open(\"$f\") as fh:
    wf = json.load(fh)
for key in [\"tags\", \"meta\", \"pinData\"]:
    wf.pop(key, None)
json.dump(wf, sys.stdout)
")

  wf_id=$(echo "$existing" | NAME="$name" python3 -c "
import json, os, sys
data = json.load(sys.stdin).get(\"data\", [])
target = os.environ.get(\"NAME\", \"\")
matches = [w[\"id\"] for w in data if w.get(\"name\") == target]
print(matches[0] if matches else \"\")
" 2>/dev/null || echo "")

  if [ -n "$wf_id" ]; then
    resp=$(echo "$cleaned" | python3 -c "
import json, sys
wf = json.load(sys.stdin)
keep = {\"name\": wf[\"name\"], \"nodes\": wf[\"nodes\"], \"connections\": wf[\"connections\"], \"settings\": wf.get(\"settings\", {})}
json.dump(keep, sys.stdout)
" | curl -s -w "\n%{http_code}" -X PUT "$API/workflows/$wf_id" \
      -H "X-N8N-API-KEY: $N8N_KEY" \
      -H "Content-Type: application/json" \
      -d @-)
    code=$(echo "$resp" | tail -1)
    if [ "$code" = "200" ]; then
      echo "  UPDATE: $name (id=$wf_id)"
    else
      echo "  FAIL UPDATE: $name (HTTP $code)" >&2
    fi
  else
    resp=$(echo "$cleaned" | curl -s -w "\n%{http_code}" -X POST "$API/workflows" \
      -H "X-N8N-API-KEY: $N8N_KEY" \
      -H "Content-Type: application/json" \
      -d @-)
    code=$(echo "$resp" | tail -1)
    if [ "$code" = "200" ] || [ "$code" = "201" ]; then
      wf_id=$(echo "$resp" | sed "\$d" | python3 -c "import json,sys; print(json.load(sys.stdin).get(\"id\",\"\"))" 2>/dev/null || echo "")
      echo "  CREATE: $name (id=$wf_id)"
    else
      echo "  FAIL CREATE: $name (HTTP $code)" >&2
    fi
  fi

  if [ -n "$wf_id" ]; then
    act_resp=$(curl -s -w "\n%{http_code}" -X POST "$API/workflows/$wf_id/activate" \
      -H "X-N8N-API-KEY: $N8N_KEY")
    act_code=$(echo "$act_resp" | tail -1)
    if [ "$act_code" = "200" ]; then
      echo "    -> activated"
    else
      echo "    -> activation failed (HTTP $act_code)" >&2
    fi
  fi
done
rm -rf /tmp/paperwork-workflows
'

echo "[3/4] Verifying workflows..."
sleep 3
TOTAL=$(ssh "$HOST" 'N8N_KEY=$(grep "^N8N_API_KEY=" /opt/paperwork-ops/.env | cut -d= -f2-); curl -s "http://localhost:5678/api/v1/workflows?limit=250" -H "X-N8N-API-KEY: $N8N_KEY" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get(\"data\",[])))"' || echo "0")
ACTIVE=$(ssh "$HOST" 'N8N_KEY=$(grep "^N8N_API_KEY=" /opt/paperwork-ops/.env | cut -d= -f2-); curl -s "http://localhost:5678/api/v1/workflows?active=true&limit=250" -H "X-N8N-API-KEY: $N8N_KEY" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get(\"data\",[])))"' || echo "0")
N8N_STATUS=$(curl -sf -o /dev/null -w '%{http_code}' "$N8N_PUBLIC_URL/" --max-time 10 || echo "000")

echo "[4/4] Summary"
echo ""
if [[ "$ACTIVE" -lt "$TOTAL" ]]; then
  INACTIVE_LIST=$(ssh "$HOST" 'N8N_KEY=$(grep "^N8N_API_KEY=" /opt/paperwork-ops/.env | cut -d= -f2-); curl -s "http://localhost:5678/api/v1/workflows?active=false&limit=250" -H "X-N8N-API-KEY: $N8N_KEY" | python3 -c "import json,sys; [print(w[\"name\"]) for w in json.load(sys.stdin).get(\"data\",[])]"' || echo "unknown")
  echo "WARNING: $ACTIVE/$TOTAL workflows active. Inactive: $INACTIVE_LIST" >&2
  slack_notify ":warning: *n8n deploy*: $ACTIVE/$TOTAL active. Inactive: $INACTIVE_LIST. n8n: $N8N_STATUS"
  if [[ "${CI:-}" == "true" || -n "${GITHUB_ACTIONS:-}" ]]; then
    exit 1
  fi
else
  echo "Deploy complete. $ACTIVE/$TOTAL workflows active. n8n: $N8N_STATUS"
  slack_notify ":white_check_mark: *n8n deploy complete*
• $ACTIVE/$TOTAL workflows active
• n8n reachable ($N8N_STATUS)"
fi
