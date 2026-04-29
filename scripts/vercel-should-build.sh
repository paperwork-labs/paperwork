#!/usr/bin/env bash
# Vercel ignoreCommand helper — determines whether a build should proceed.
# Exit 1 = proceed with build, Exit 0 = skip build.
# Called by each app's vercel.json ignoreCommand.

set -euo pipefail

APP_PKG="${1:?Usage: vercel-should-build.sh @paperwork-labs/app-name}"

# Skip Dependabot commits entirely
if git log -1 --pretty=%an 2>/dev/null | grep -qi dependabot; then
  echo "Dependabot commit — skipping build"
  exit 0
fi

# If we can determine changed files and they are ALL in non-app directories,
# skip the build. This prevents 6 preview deploys on docs/data-only PRs.
if CHANGED=$(git diff HEAD~1 --name-only 2>/dev/null); then
  if [ -n "$CHANGED" ]; then
    # Check if ANY changed file is outside the "safe to skip" directories
    APP_RELEVANT=$(echo "$CHANGED" | grep -vE '^(docs/|apis/|infra/|scripts/|\.github/|\.cursor/)' || true)
    if [ -z "$APP_RELEVANT" ]; then
      echo "Only docs/apis/infra/scripts changed — skipping build"
      exit 0
    fi
  fi
fi

# Fall through to turbo-ignore for package-graph-aware detection
exec npx -y turbo-ignore "$APP_PKG" --fallback=HEAD~10
