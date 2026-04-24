#!/usr/bin/env bash
# discover-new-ids.sh — list all resources in the Paperwork Render team
# matching AxiomFolio names, so you can populate AF_NEW_*_ID env vars.
#
# Run AFTER Phase 1 (blueprint launch). Prints `export` lines ready to
# source.

set -euo pipefail

: "${AF_NEW_RENDER_KEY:?Set AF_NEW_RENDER_KEY}"
: "${AF_NEW_OWNER_ID:?Set AF_NEW_OWNER_ID}"

API="https://api.render.com/v1"
H=(-H "Authorization: Bearer $AF_NEW_RENDER_KEY" -H "Accept: application/json")

echo "# Discovered AxiomFolio resources under team $AF_NEW_OWNER_ID" >&2
echo "# Source this to populate AF_NEW_*_ID" >&2

# Services
curl -s "${H[@]}" "$API/services?limit=50&ownerId=$AF_NEW_OWNER_ID" \
  | jq -r '.[] | .service | select(.name | startswith("axiomfolio-")) | "\(.name)\t\(.id)\t\(.type)"' \
  | while IFS=$'\t' read -r name id type; do
      case "$name" in
        axiomfolio-api)          echo "export AF_NEW_API_SERVICE_ID=$id" ;;
        axiomfolio-frontend)     echo "export AF_NEW_FRONTEND_SERVICE_ID=$id" ;;
        axiomfolio-worker)       echo "export AF_NEW_WORKER_SERVICE_ID=$id" ;;
        axiomfolio-worker-heavy) echo "export AF_NEW_WORKER_HEAVY_SERVICE_ID=$id" ;;
        *)                       echo "# unmatched service: $name ($id, $type)" >&2 ;;
      esac
    done

# Postgres
curl -s "${H[@]}" "$API/postgres?limit=20&ownerId=$AF_NEW_OWNER_ID" \
  | jq -r '.[] | .postgres | select(.name == "axiomfolio-db") | "export AF_NEW_DB_ID=\(.id)"'

# Key-value
curl -s "${H[@]}" "$API/key-value?limit=20&ownerId=$AF_NEW_OWNER_ID" \
  | jq -r '.[] | .keyValue | select(.name == "axiomfolio-redis") | "export AF_NEW_REDIS_ID=\(.id)"'
