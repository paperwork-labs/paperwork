#!/usr/bin/env bash
set -euo pipefail

# Close ALL open Dependabot PRs in the current repo.
#
# Requirements:
# - GitHub CLI installed: https://cli.github.com/
# - Authenticated: gh auth login
#
# Usage:
#   ./scripts/close_dependabot_prs.sh "closing to reset dependabot config"
#

REASON="${1:-Closing all Dependabot PRs to reset dependency update policy (grouping/limits).}"

echo "Fetching open Dependabot PRs..."

# List open PRs where the author is dependabot[bot]
PRS="$(gh pr list --state open --author "dependabot[bot]" --json number,title --jq '.[] | "\(.number)\t\(.title)"' || true)"

if [[ -z "${PRS}" ]]; then
  echo "No open Dependabot PRs found."
  exit 0
fi

echo "Will close the following PRs:"
echo "${PRS}"
echo

while IFS=$'\t' read -r num title; do
  [[ -z "${num}" ]] && continue
  echo "Closing #${num} - ${title}"
  gh pr close "${num}" --comment "${REASON}"
done <<< "${PRS}"

echo "Done."


