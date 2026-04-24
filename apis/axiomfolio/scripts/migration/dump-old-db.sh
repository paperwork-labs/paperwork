#!/usr/bin/env bash
# dump-old-db.sh — pg_dump the OLD axiomfolio-db to a local file.
#
# Requires:
#   - pg_dump v16 (brew install postgresql@16)
#   - AF_OLD_RENDER_KEY, AF_OLD_DB_ID
#   - This machine's IP is whitelisted on old DB's allow-list
#
# Output: /tmp/axiomfolio-render-migration/prod-YYYYMMDD-HHMMSS.dump
#   (custom format, compressed, ~7GB expected)

set -euo pipefail

: "${AF_OLD_RENDER_KEY:?}"
: "${AF_OLD_DB_ID:?}"

PG_DUMP="${PG_DUMP:-/opt/homebrew/opt/postgresql@16/bin/pg_dump}"
[[ -x "$PG_DUMP" ]] || { echo "pg_dump not at $PG_DUMP — run 'brew install postgresql@16'" >&2; exit 2; }

OUT_DIR="${OUT_DIR:-/tmp/axiomfolio-render-migration}"
mkdir -p "$OUT_DIR"
OUT_FILE="$OUT_DIR/prod-$(date -u +%Y%m%d-%H%M%S).dump"

# Fetch connection info
CONN=$(curl -sS -H "Authorization: Bearer $AF_OLD_RENDER_KEY" \
  "https://api.render.com/v1/postgres/$AF_OLD_DB_ID/connection-info")

CONN_STR=$(echo "$CONN" | jq -r '.externalConnectionString')
[[ -n "$CONN_STR" && "$CONN_STR" != "null" ]] || { echo "Failed to fetch conn string" >&2; exit 2; }

echo ">> Dumping old axiomfolio-db (~7.3 GB, expect ~15 min)"
echo "   dest: $OUT_FILE"
START=$(date +%s)

"$PG_DUMP" \
  --format=custom \
  --compress=9 \
  --verbose \
  --no-owner \
  --no-privileges \
  --dbname="$CONN_STR" \
  --file="$OUT_FILE" 2>&1 | tail -30

END=$(date +%s)
SIZE=$(du -h "$OUT_FILE" | awk '{print $1}')
echo ""
echo ">> Done in $((END - START))s — size: $SIZE"
echo "   Next: export AF_DUMP_FILE=$OUT_FILE; ./restore-new-db.sh"
