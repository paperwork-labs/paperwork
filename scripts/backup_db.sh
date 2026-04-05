#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────
# AxiomFolio — Production Database Backup
#
# Usage:
#   ./scripts/backup_db.sh
#
# Requires:
#   - RENDER_DB_EXTERNAL_URL env var (grab from Render dashboard → axiomfolio-db → External Database URL)
#   - pg_dump installed locally
# ──────────────────────────────────────────────────────────────

BACKUP_DIR="${BACKUP_DIR:-$HOME/axiomfolio-backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/axiomfolio_${TIMESTAMP}.sql.gz"

if [ -z "${RENDER_DB_EXTERNAL_URL:-}" ]; then
    echo "ERROR: Set RENDER_DB_EXTERNAL_URL first."
    echo ""
    echo "  export RENDER_DB_EXTERNAL_URL='postgresql://axiomfolio_db_ip6j_user:<password>@dpg-d725m719fqoc739rc3f0-a.oregon-postgres.render.com/axiomfolio_db_ip6j'"
    echo ""
    echo "  (Copy the External Database URL from Render dashboard → axiomfolio-db → Connections)"
    exit 1
fi

mkdir -p "$BACKUP_DIR"

echo "Starting backup to ${BACKUP_FILE} ..."
echo "Database: dpg-d725m719fqoc739rc3f0-a (axiomfolio-db)"

pg_dump \
    --no-owner \
    --no-privileges \
    --format=plain \
    "${RENDER_DB_EXTERNAL_URL}?sslmode=require" \
    | gzip -9 > "$BACKUP_FILE"

FILESIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "Backup complete: ${BACKUP_FILE} (${FILESIZE})"

# Retain last 5 backups, prune older ones
cd "$BACKUP_DIR"
if compgen -G "axiomfolio_*.sql.gz" > /dev/null; then
    ls -1t axiomfolio_*.sql.gz 2>/dev/null | tail -n +6 | xargs -r rm -f
fi
echo "Retention: kept last 5 backups in ${BACKUP_DIR}"
