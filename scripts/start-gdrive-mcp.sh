#!/usr/bin/env bash
# Start google-drive-mcp server (folder_create, file_upload, etc.)
# Run this before using GDrive MCP in Cursor. Keep terminal open.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEYS_FILE="$SCRIPT_DIR/../infra/gcp/gcp-oauth.keys.json"

if [[ ! -f "$KEYS_FILE" ]]; then
  echo "Missing $KEYS_FILE. Download OAuth credentials from GCP Console."
  exit 1
fi

KEYS_FILE_ABS="$(cd "$(dirname "$KEYS_FILE")" && pwd)/$(basename "$KEYS_FILE")"

CREDS=$(node -e "
  const j = require('$KEYS_FILE_ABS');
  const c = j.installed || j.web;
  process.stdout.write(c.client_id + '::' + c.client_secret);
")

export GOOGLE_CLIENT_ID="${CREDS%%::*}"
export GOOGLE_CLIENT_SECRET="${CREDS##*::}"
export MCP_TRANSPORT=http
export PORT=${GDRIVE_MCP_PORT:-3100}

echo "Starting google-drive-mcp on http://localhost:$PORT/mcp"
echo "Add http://localhost:$PORT/callback to your GCP OAuth client if not done."
npx -y google-drive-mcp
