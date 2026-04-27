#!/usr/bin/env bash
#
# Canonical Vercel install command for the Paperwork Labs monorepo.
#
# Usage from apps/<app>/vercel.json:
#   "installCommand": "bash ../../scripts/vercel-install.sh @paperwork-labs/<app>"
#
# Reads the pnpm version from root package.json `packageManager` so there is one
# source of truth across every project.
#
# The `rm -rf node_modules/.pnpm` step is deliberate: Vercel caches the pnpm
# virtual store across builds, and stale entries (e.g. from when apps/_archive
# was uploaded) can poison peer-dep resolution. Until apps/_archive is fully
# removed AND the cache demonstrably clean, this stays.

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <pnpm-filter-target>" >&2
  echo "Example: $0 @paperwork-labs/studio" >&2
  exit 2
fi

FILTER="$1"

# Move to repo root regardless of how Vercel invokes us.
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${ROOT}" ]]; then
  # Vercel build runner is not a git checkout; fall back to walking up for package.json with workspaces.
  CUR="$(pwd)"
  while [[ "${CUR}" != "/" ]]; do
    if [[ -f "${CUR}/pnpm-workspace.yaml" ]]; then
      ROOT="${CUR}"
      break
    fi
    CUR="$(dirname "${CUR}")"
  done
fi
if [[ -z "${ROOT}" ]]; then
  echo "vercel-install: could not locate monorepo root (no pnpm-workspace.yaml found)" >&2
  exit 1
fi
cd "${ROOT}"

PNPM_VERSION="$(node -p "require('./package.json').packageManager.split('@')[1]")"
if [[ -z "${PNPM_VERSION}" ]]; then
  echo "vercel-install: failed to read packageManager from root package.json" >&2
  exit 1
fi

echo "vercel-install: root=${ROOT} pnpm=${PNPM_VERSION} filter=${FILTER}"

corepack enable
corepack prepare "pnpm@${PNPM_VERSION}" --activate

rm -rf node_modules/.pnpm

pnpm install --frozen-lockfile --filter="${FILTER}..."
