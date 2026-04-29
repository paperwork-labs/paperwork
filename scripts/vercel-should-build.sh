#!/usr/bin/env bash
# Vercel ignoreCommand helper — determines whether a build should proceed.
# Exit 1 = proceed with build, Exit 0 = skip build.
# Called by each app's vercel.json ignoreCommand.
#
# Vercel provides VERCEL_GIT_PREVIOUS_SHA for the comparison base.
# Shallow clones may not have HEAD~1, so we prefer the env var.

set -euo pipefail

APP_PKG="${1:?Usage: vercel-should-build.sh @paperwork-labs/app-name}"

# Skip Dependabot commits entirely
if git log -1 --pretty=%an 2>/dev/null | grep -qi dependabot; then
  echo "Dependabot commit — skipping build"
  exit 0
fi

# Determine the comparison base SHA — prefer Vercel's env var over HEAD~1
# because Vercel uses shallow clones where HEAD~1 may not exist.
BASE_SHA="${VERCEL_GIT_PREVIOUS_SHA:-}"
if [ -z "$BASE_SHA" ]; then
  BASE_SHA=$(git rev-parse HEAD~1 2>/dev/null || echo "")
fi

if [ -n "$BASE_SHA" ]; then
  CHANGED=$(git diff "$BASE_SHA" --name-only 2>/dev/null || echo "")
  if [ -n "$CHANGED" ]; then
    APP_RELEVANT=$(echo "$CHANGED" | grep -vE '^(docs/|apis/|infra/|scripts/|\.github/|\.cursor/)' || true)
    if [ -z "$APP_RELEVANT" ]; then
      echo "Only docs/apis/infra/scripts changed — skipping build for $APP_PKG"
      exit 0
    fi
  fi
fi

# Fall through to turbo-ignore for package-graph-aware detection
exec npx -y turbo-ignore "$APP_PKG" --fallback=HEAD~10
