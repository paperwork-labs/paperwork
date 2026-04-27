#!/usr/bin/env bash
set -euo pipefail

# Link every Vercel app under apps/* that appears in scripts/vercel-projects.json.
# Usage:
#   scripts/vercel-link-all.sh              # link missing projects (requires vercel login)
#   scripts/vercel-link-all.sh --check    # read-only: show status + summary
#   scripts/vercel-link-all.sh --check --quiet   # stdout: UNLINKED=N only

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAP_JSON="$REPO_ROOT/scripts/vercel-projects.json"

export REPO_ROOT MAP_JSON
export VERCEL_LINK_CHECK_ONLY=0
export VERCEL_LINK_QUIET=0

for arg in "$@"; do
  case "$arg" in
    --check) export VERCEL_LINK_CHECK_ONLY=1 ;;
    --quiet) export VERCEL_LINK_QUIET=1 ;;
    *)
      echo "usage: $0 [--check] [--quiet]" >&2
      exit 2
      ;;
  esac
done

if [[ ! -f "$MAP_JSON" ]]; then
  echo "error: missing $MAP_JSON" >&2
  exit 1
fi

if [[ "$VERCEL_LINK_CHECK_ONLY" -eq 0 ]]; then
  if ! command -v vercel >/dev/null 2>&1; then
    echo "error: vercel CLI not found. Install: npm i -g vercel" >&2
    exit 1
  fi
  if ! vercel whoami >/dev/null 2>&1; then
    echo "error: not logged in to Vercel. Run: vercel login" >&2
    exit 1
  fi
fi

exec node "$REPO_ROOT/scripts/vercel-link-all.mjs"
