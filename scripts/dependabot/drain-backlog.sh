#!/usr/bin/env bash
# Drain the existing Dependabot backlog after dependabot-auto-approve.yaml is live.
#
# For each open Dependabot PR:
#   - safe bumps (patch/minor/group) → approve + enable automerge --squash
#   - major bumps (title contains "major", or like "-> N.0.0", or "vN.0" where N>=2)
#     → label `deps:major,dependencies` — this triggers dependabot-major-triage.yaml
#       which runs Haiku + applies risk:low|medium|high.
#
# Usage:
#   ./scripts/dependabot/drain-backlog.sh [--dry-run]
#
# Requires: gh CLI authenticated against paperwork-labs/paperwork.

set -euo pipefail

DRY="${1:-}"

REPO="paperwork-labs/paperwork"

echo "==> Fetching open Dependabot PRs…"
PRS_JSON=$(gh pr list --repo "$REPO" --author "app/dependabot" --state open --limit 200 \
  --json number,title,labels)

safe=()
major=()

while IFS= read -r row; do
  num=$(echo "$row" | jq -r '.number')
  title=$(echo "$row" | jq -r '.title')

  # Classify as major if:
  #   - "major" literal, or
  #   - "-> X.0.0" at the tail, or
  #   - semver bump where first number differs ("from 11.18.2 to 12.38.0"), or
  #   - action-style bump with no dots where first number differs ("from 7 to 9").
  if python3 - "$title" <<'PYEOF'
import re, sys
t = sys.argv[1]
# explicit markers
if re.search(r'(\bmajor\b|-> ?\d+\.0\.0)', t):
    sys.exit(0)
# extract first number after "from" and first number after "to" (skipping
# comparison prefixes like >=, ^, ~, ==, etc.). Treat them as major positions.
m = re.search(r'from\s+[^\d]*?(\d+)\S*\s+to\s+[^\d]*?(\d+)', t)
if m and m.group(1) != m.group(2):
    sys.exit(0)
sys.exit(1)
PYEOF
  then
    major+=("$num|$title")
    continue
  fi

  safe+=("$num|$title")
done < <(echo "$PRS_JSON" | jq -c '.[]')

echo
echo "==> Safe bumps: ${#safe[@]}"
for item in "${safe[@]}"; do echo "  #${item}"; done

echo
echo "==> Major bumps (route to Haiku triage): ${#major[@]}"
for item in "${major[@]}"; do echo "  #${item}"; done

if [[ "$DRY" == "--dry-run" ]]; then
  echo
  echo "Dry run — not making changes."
  exit 0
fi

echo
echo "==> Approving + enabling automerge on safe bumps…"
for item in "${safe[@]}"; do
  num="${item%%|*}"
  title="${item#*|}"
  echo "  #$num — $title"
  gh pr review "$num" --repo "$REPO" --approve \
    --body "Drain-backlog approval (patch/minor/group bump per dependabot-auto-approve.yaml rules)." \
    || echo "    (already approved or blocked — continuing)"
  gh pr merge "$num" --repo "$REPO" --auto --squash \
    || echo "    (automerge already enabled or blocked — continuing)"
done

echo
echo "==> Labeling majors for Haiku triage…"
for item in "${major[@]}"; do
  num="${item%%|*}"
  title="${item#*|}"
  echo "  #$num — $title"
  gh pr edit "$num" --repo "$REPO" --add-label "deps:major,dependencies" \
    || echo "    (label already present — continuing)"
done

echo
echo "==> Done. Watch the PR queue — safe bumps should start merging as CI turns green."
