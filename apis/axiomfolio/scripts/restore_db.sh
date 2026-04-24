#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────
# AxiomFolio — Restore Production Database to Local Dev
#
# Usage:
#   ./scripts/restore_db.sh <backup_file>
#   ./scripts/restore_db.sh ~/axiomfolio-backups/axiomfolio_20260406_120000.sql.gz
#
# Requires:
#   - Docker dev stack running (make up)
#   - A backup file from ./scripts/backup_db.sh
#
# Credentials after restore:
#   Host:     localhost:5432
#   Database: axiomfolio
#   User:     axiomfolio
#   Password: password  (from infra/env.dev)
# ──────────────────────────────────────────────────────────────

BACKUP_FILE="${1:-}"
ENV_FILE="${ENV_FILE:-infra/env.dev}"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: ./scripts/restore_db.sh <backup_file.sql.gz>"
    echo ""
    echo "Available backups:"
    ls -1t ~/axiomfolio-backups/axiomfolio_*.sql.gz 2>/dev/null || echo "  (none found in ~/axiomfolio-backups/)"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: File not found: $BACKUP_FILE"
    exit 1
fi

# Load dev env for DB credentials
if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    set -a; source "$ENV_FILE"; set +a
fi

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_HOST_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-axiomfolio}"
DB_USER="${POSTGRES_USER:-axiomfolio}"
DB_PASS="${POSTGRES_PASSWORD:-password}"

export PGPASSWORD="$DB_PASS"

echo "=== AxiomFolio DB Restore ==="
echo "Source:   $BACKUP_FILE"
echo "Target:   $DB_USER@$DB_HOST:$DB_PORT/$DB_NAME"
echo ""

read -rp "This will DROP and recreate the local database. Continue? [y/N] " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "Step 1/3: Dropping existing database..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "
  SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();
" 2>/dev/null || true
dropdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" --if-exists "$DB_NAME"
createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME"

echo "Step 2/3: Restoring from backup..."
if [[ "$BACKUP_FILE" == *.gz ]]; then
    gunzip -c "$BACKUP_FILE" | psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" --quiet --single-transaction 2>&1 | tail -5
else
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" --quiet --single-transaction < "$BACKUP_FILE" 2>&1 | tail -5
fi

echo "Step 3/3: Running Alembic migrations (catch up if backup is older)..."
cd "$(dirname "$0")/.."
if command -v alembic &>/dev/null; then
    alembic -c app/alembic.ini upgrade head 2>&1 | tail -3
else
    echo "  (alembic not found locally; migrations will run on next 'make up')"
fi

echo ""
echo "=== Restore complete ==="
echo ""
echo "Connect with:"
echo "  psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME"
echo "  Password: $DB_PASS"
echo ""
echo "Or from your app: DATABASE_URL=postgresql://$DB_USER:$DB_PASS@$DB_HOST:$DB_PORT/$DB_NAME"
