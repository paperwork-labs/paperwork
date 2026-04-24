#!/usr/bin/env bash
set -euo pipefail

# Create a conventional commit PR for the current working tree.
#
# Requirements:
# - gh CLI installed and authenticated OR GH_TOKEN set with:
#   - contents:write
#   - pull_requests:write
#
# Usage:
#   scripts/open_pr.sh fix "prevent dev DB usage in tests"
#   scripts/open_pr.sh feat "add github actions CI"
#   scripts/open_pr.sh chore "infra cleanup"

TYPE="${1:-}"
TITLE="${2:-}"

if [[ -z "${TYPE}" || -z "${TITLE}" ]]; then
  echo "Usage: $0 <type: feat|fix|chore|docs|refactor|test> \"short title\""
  exit 2
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not found. Install GitHub CLI or use a GitHub App/token flow."
  exit 2
fi

# Guardrail: do not start a new agent PR from an existing agent branch unless that branch is already merged.
# This avoids "branch-on-branch" confusion and keeps our workflow deterministic:
# - If current branch is agent/** and its PR is merged -> switch to main, fast-forward, proceed.
# - If current branch is agent/** and its PR is open/unmerged -> stop and ask operator to finish/merge first.
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$CURRENT_BRANCH" == agent/* ]]; then
  # If there are local changes, don't attempt to switch branches automatically.
  if [[ -n "$(git status --porcelain)" ]]; then
    echo "You are on $CURRENT_BRANCH with uncommitted changes."
    echo "Finish this branch (commit/push) or stash changes before starting a new PR."
    exit 2
  fi

  # If no PR exists, treat as unmerged (operator should decide what to do).
  if gh pr view "$CURRENT_BRANCH" --json number,state,isMerged >/dev/null 2>&1; then
    PR_STATE="$(gh pr view "$CURRENT_BRANCH" --json state,isMerged --jq '.state + \"|\" + (if .isMerged then \"true\" else \"false\" end)')"
    if [[ "$PR_STATE" != *"|true" ]]; then
      echo "Refusing to start a new PR while current agent branch PR is not merged: $CURRENT_BRANCH"
      echo "Merge/close the PR (or switch to main) and re-run this script."
      exit 2
    fi
  else
    echo "Refusing to start a new PR from $CURRENT_BRANCH because no PR is associated (treating as unmerged)."
    echo "Switch to main (or open/merge the PR for this branch) and re-run."
    exit 2
  fi

  # Current agent PR is merged; reset workflow baseline to main.
  git switch main
  git pull --ff-only origin main
fi

BRANCH="agent/${TYPE}/$(echo "${TITLE}" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//;s/-$//')-$(date +%Y%m%d)"

git status --porcelain >/dev/null

if [[ -n "$(git status --porcelain)" ]]; then
  git checkout -b "${BRANCH}"
  git add -A
  git commit -m "${TYPE}: ${TITLE}"
else
  echo "No changes to commit."
  exit 0
fi

git push -u origin "${BRANCH}"

BODY_TEMPLATE=".github/pull_request_template.md"
TMP_BODY="$(mktemp)"
{
  echo "Auto-created PR for branch \`${BRANCH}\`."
  echo
  if [[ -f "${BODY_TEMPLATE}" ]]; then
    cat "${BODY_TEMPLATE}"
  else
    echo "Summary"
    echo
    echo "What does this change do?"
    echo
    echo "Checklist"
    echo "- [ ] Tests pass locally"
    echo "- [ ] No test can touch the dev DB (uses postgres_test only)"
    echo "- [ ] Any migrations included (if schema changes)"
    echo "- [ ] Docs updated (README / docs/)"
    echo "- [ ] No hardcoded secrets or account identifiers"
    echo
    echo "Risk / Rollback"
    echo "What could break? How do we roll back?"
    echo
  fi
} > "${TMP_BODY}"

gh pr create \
  --title "${TYPE}: ${TITLE}" \
  --draft \
  --body-file "${TMP_BODY}" \
  --head "${BRANCH}" \
  --base "main"

rm -f "${TMP_BODY}"


