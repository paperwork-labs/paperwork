#!/usr/bin/env bash
# Dry-run: for each app in scripts/vercel-projects.json with a real project id,
# call Vercel GET /v6/deployments?projectId=...&state=READY&limit=1.
#
# Optional: pass a merge commit SHA as the first argument (or set MERGE_SHA)
# to assert the newest READY preview matches meta.githubCommitSha (full or prefix).
#
# Requires: VERCEL_API_TOKEN or VERCEL_TOKEN in the environment.
# On HTTP 429, logs a warning and skips remaining API calls (rate-limit safe).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
JSON="$ROOT/scripts/vercel-projects.json"
TEAM_ID="$(jq -r '.teamId' "$JSON")"
TOKEN="${VERCEL_API_TOKEN:-${VERCEL_TOKEN:-}}"

MERGE_SHA="${1:-${MERGE_SHA:-}}"
if [ -n "$MERGE_SHA" ]; then
  MERGE_SHA="$(printf '%s' "$MERGE_SHA" | tr '[:upper:]' '[:lower:]')"
fi

if [ -z "$TOKEN" ]; then
  echo "WARN: VERCEL_API_TOKEN / VERCEL_TOKEN not set — skipping Vercel API validation."
  exit 0
fi

rate_limited=0
checked=0
skipped_placeholder=0

while IFS= read -r row; do
  slug="$(echo "$row" | jq -r '.slug')"
  pid="$(echo "$row" | jq -r '.projectId')"
  if [ -z "$pid" ] || [ "$pid" = "null" ] || [ "$pid" = "TBD_CREATE_BEFORE_MERGE" ]; then
    echo "SKIP (placeholder): $slug"
    skipped_placeholder=$((skipped_placeholder + 1))
    continue
  fi

  if [ "$rate_limited" -eq 1 ]; then
    echo "WARN: rate limited earlier — skipping API for $slug"
    continue
  fi

  url="https://api.vercel.com/v6/deployments?projectId=${pid}&teamId=${TEAM_ID}&state=READY&limit=1"
  code=$(curl -sS -o /tmp/vchk.json -w "%{http_code}" -H "Authorization: Bearer ${TOKEN}" "$url" || true)
  if [ "$code" = "429" ]; then
    echo "::warning::Vercel API rate limited (429) while checking $slug — skipping further calls."
    rate_limited=1
    continue
  fi
  if [ -z "$code" ] || [ "$code" -lt 200 ] || [ "$code" -ge 400 ]; then
    echo "ERROR: deployments fetch failed for $slug (HTTP ${code})"
    head -c 2000 /tmp/vchk.json || true
    echo
    exit 1
  fi

  dep_sha="$(jq -r '.deployments[0].meta.githubCommitSha // empty' /tmp/vchk.json)"
  uid="$(jq -r '.deployments[0].uid // empty' /tmp/vchk.json)"
  if [ -z "$uid" ]; then
    echo "WARN: no READY deployment for $slug (projectId=$pid)"
  else
    echo "OK: $slug READY deployment=$uid commit=${dep_sha:-unknown}"
    if [ -n "$MERGE_SHA" ] && [ -n "$dep_sha" ]; then
      ds="$(printf '%s' "$dep_sha" | tr '[:upper:]' '[:lower:]')"
      if [ "$ds" != "$MERGE_SHA" ] && [ "${ds:0:7}" != "${MERGE_SHA:0:7}" ]; then
        echo "WARN: newest READY SHA for $slug ($dep_sha) does not match requested MERGE_SHA ($MERGE_SHA)"
      fi
    fi
  fi
  checked=$((checked + 1))
done < <(jq -c '.apps[]' "$JSON")

echo "Done: checked=${checked} placeholder_skips=${skipped_placeholder} rate_limited=${rate_limited}"
