#!/usr/bin/env bash
# restore-new-db.sh — pg_restore a dump file into the NEW axiomfolio-db.
#
# Requires:
#   - pg_restore v16 (brew install postgresql@16)
#   - AF_NEW_RENDER_KEY, AF_NEW_DB_ID
#   - AF_DUMP_FILE (path to .dump produced by dump-old-db.sh)
#   - This machine's IP is whitelisted on NEW DB's allow-list
#     (add via dashboard or API before running)

set -euo pipefail

: "${AF_NEW_RENDER_KEY:?}"
: "${AF_NEW_DB_ID:?}"
: "${AF_DUMP_FILE:?path to dump file}"

PG_RESTORE="${PG_RESTORE:-/opt/homebrew/opt/postgresql@16/bin/pg_restore}"
PSQL="${PSQL:-/opt/homebrew/opt/postgresql@16/bin/psql}"
[[ -x "$PG_RESTORE" ]] || { echo "pg_restore not at $PG_RESTORE" >&2; exit 2; }
[[ -f "$AF_DUMP_FILE" ]] || { echo "Dump file not found: $AF_DUMP_FILE" >&2; exit 2; }

CONN=$(curl -sS -H "Authorization: Bearer $AF_NEW_RENDER_KEY" \
  "https://api.render.com/v1/postgres/$AF_NEW_DB_ID/connection-info")

CONN_STR=$(echo "$CONN" | jq -r '.externalConnectionString')
[[ -n "$CONN_STR" && "$CONN_STR" != "null" ]] || { echo "Failed to fetch new conn string" >&2; exit 2; }

echo ">> Pre-flight: confirm new DB is empty"
TABLE_COUNT=$("$PSQL" "$CONN_STR" -Atc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';")
if [[ "$TABLE_COUNT" -gt 0 ]]; then
  echo "   !! New DB has $TABLE_COUNT tables already. Restore would conflict." >&2
  echo "   !! Either drop the schema or use a fresh DB." >&2
  read -r -p "   Continue anyway? [type YES] " ok
  [[ "$ok" == "YES" ]] || exit 1
fi

echo ">> Restoring into new axiomfolio-db (expect ~20 min)"
START=$(date +%s)

"$PG_RESTORE" \
  --dbname="$CONN_STR" \
  --jobs=4 \
  --no-owner \
  --no-privileges \
  --verbose \
  --exit-on-error \
  "$AF_DUMP_FILE" 2>&1 | tail -30

END=$(date +%s)
echo ""
echo ">> Restore done in $((END - START))s"

echo ""
echo ">> Row-count spot checks (top 10 tables by relation size)"
"$PSQL" "$CONN_STR" <<'SQL'
SELECT relname AS table, n_live_tup AS approx_rows,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size
FROM pg_stat_user_tables s
JOIN pg_class c ON c.relname = s.relname
ORDER BY pg_total_relation_size(c.oid) DESC
LIMIT 10;
SQL
