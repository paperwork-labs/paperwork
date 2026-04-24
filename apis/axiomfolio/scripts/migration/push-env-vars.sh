#!/usr/bin/env bash
# push-env-vars.sh — copy env vars from OLD services to NEW services.
#
# Reads env vars from old services via AF_OLD_RENDER_KEY, filters out the
# blueprint-managed keys (which render.yaml will re-wire), and writes the
# remainder to the new services via AF_NEW_RENDER_KEY.
#
# Idempotent: Render's env-var API upserts by key.

set -euo pipefail

: "${AF_OLD_RENDER_KEY:?}"
: "${AF_NEW_RENDER_KEY:?}"
: "${AF_OLD_API_SERVICE_ID:?}"
: "${AF_NEW_API_SERVICE_ID:?}"
: "${AF_OLD_WORKER_SERVICE_ID:?}"
: "${AF_NEW_WORKER_SERVICE_ID:?}"
: "${AF_OLD_WORKER_HEAVY_SERVICE_ID:?}"
: "${AF_NEW_WORKER_HEAVY_SERVICE_ID:?}"

API="https://api.render.com/v1"

# Keys the new blueprint manages itself — skip during copy.
SKIP_KEYS=(
  DATABASE_URL
  REDIS_URL
  RATE_LIMIT_STORAGE_URL
  CELERY_BROKER_URL
  CELERY_RESULT_BACKEND
  SECRET_KEY
  ENVIRONMENT
  LOG_FORMAT
  AUTO_MIGRATE_ON_STARTUP
  WORKER_ROLE
)

skip_filter() {
  local jq_filter='.[] | .envVar | select(.key as $k | '
  jq_filter+="[$(printf '"%s",' "${SKIP_KEYS[@]}" | sed 's/,$//')]"
  jq_filter+=' | index($k) | not) | {key, value}'
  jq "$jq_filter"
}

copy_service() {
  local label="$1"
  local old_id="$2"
  local new_id="$3"

  echo ">> $label: old=$old_id → new=$new_id"

  local src_json
  src_json=$(curl -sS -H "Authorization: Bearer $AF_OLD_RENDER_KEY" \
    "$API/services/$old_id/env-vars?limit=100" | skip_filter | jq -s '.')

  local count
  count=$(echo "$src_json" | jq 'length')
  echo "   $count env vars to copy"

  # Render env-vars PUT accepts an array replace, but we want upsert. Use the
  # individual POST/PATCH endpoints keyed by var name.
  echo "$src_json" | jq -c '.[]' | while IFS= read -r row; do
    k=$(echo "$row" | jq -r '.key')
    v=$(echo "$row" | jq -r '.value')
    # PUT /services/:id/env-vars/:key upserts
    resp=$(curl -s -w "\n%{http_code}" -X PUT \
      -H "Authorization: Bearer $AF_NEW_RENDER_KEY" \
      -H "Content-Type: application/json" \
      "$API/services/$new_id/env-vars/$k" \
      -d "$(jq -nc --arg v "$v" '{value: $v}')")
    http=$(echo "$resp" | tail -1)
    if [[ "$http" == "200" || "$http" == "201" ]]; then
      echo "   ✓ $k"
    else
      echo "   ✗ $k (HTTP $http): $(echo "$resp" | sed '$d' | head -c 200)"
    fi
  done
}

copy_service "axiomfolio-api"          "$AF_OLD_API_SERVICE_ID"          "$AF_NEW_API_SERVICE_ID"
copy_service "axiomfolio-worker"       "$AF_OLD_WORKER_SERVICE_ID"       "$AF_NEW_WORKER_SERVICE_ID"
copy_service "axiomfolio-worker-heavy" "$AF_OLD_WORKER_HEAVY_SERVICE_ID" "$AF_NEW_WORKER_HEAVY_SERVICE_ID"

echo ""
echo "Done. Trigger deploys on new services to pick up new env vars:"
echo "  curl -X POST -H 'Authorization: Bearer \$AF_NEW_RENDER_KEY' \\"
echo "    $API/services/\$AF_NEW_API_SERVICE_ID/deploys"
