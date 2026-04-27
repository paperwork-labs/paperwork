#!/usr/bin/env bash
# Rebase a single PR's head onto origin/main, with optional regen for
# known conflict files only. Run from a full clone of the repo (e.g. CI).
set -euo pipefail
PR_NUMBER="${1:?PR number required}"

export GH_TOKEN="${GH_TOKEN:-$GITHUB_TOKEN}"
if [[ -z "${GH_TOKEN:-}" ]]; then
  echo "GH_TOKEN / GITHUB_TOKEN required" >&2
  exit 1
fi

is_known() {
  case "$1" in
  apps/studio/src/data/tracker-index.json) return 0 ;;
  docs/_index.yaml) return 0 ;;
  pnpm-lock.yaml) return 0 ;;
  *) return 1 ;;
  esac
}

REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT"

if ! command -v gh &>/dev/null; then
  echo "gh CLI required" >&2
  exit 1
fi
if ! command -v pnpm &>/dev/null; then
  echo "pnpm required for lock regen" >&2
  exit 1
fi

pr_json=$(gh pr view "$PR_NUMBER" --json headRefName,baseRefName,state,isDraft,headRefOid,author,isCrossRepository)
head_ref=$(echo "$pr_json" | jq -r '.headRefName')
base_ref=$(echo "$pr_json" | jq -r '.baseRefName')
state=$(echo "$pr_json" | jq -r '.state')
draft=$(echo "$pr_json" | jq -r '.isDraft')
head_sha=$(echo "$pr_json" | jq -r '.headRefOid')
author=$(echo "$pr_json" | jq -r '.author.login')
is_fork=$(echo "$pr_json" | jq -r '.isCrossRepository')
DEFAULT_BOTS="paperwork-labs[bot],paperwork-labs-bot,github-actions[bot]"
IFS=',' read -ra BOTS <<< "${AGENT_PR_BOT_LOGINS:-$DEFAULT_BOTS}"
allowed=false
for b in "${BOTS[@]}"; do
  b=$(echo "$b" | xargs)
  [[ -z "$b" ]] && continue
  if [[ "$author" == "$b" ]]; then allowed=true; break; fi
done
if [[ "$allowed" != "true" ]]; then
  echo "PR#$PR_NUMBER author $author is not in AGENT_PR_BOT_LOGINS, skip (no force-push to non-bot branches)"
  exit 0
fi
if [[ "$is_fork" == "true" ]]; then
  echo "PR#$PR_NUMBER fork, skip"
  exit 0
fi
REPO_FULL="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY not set}"

if [[ "$state" != "OPEN" ]]; then
  echo "PR#$PR_NUMBER not open, skip"
  exit 0
fi
if [[ "$draft" == "true" ]]; then
  echo "PR#$PR_NUMBER draft, skip"
  exit 0
fi
if [[ "$base_ref" != "main" ]]; then
  echo "PR#$PR_NUMBER base is $base_ref, skip"
  exit 0
fi

# Cooldown: new commits
commit_date=$(gh api "repos/${REPO_FULL}/commits/${head_sha}" --jq .commit.committer.date 2>/dev/null || true)
if [[ -n "$commit_date" ]]; then
  commit_epoch=$(date -d "$commit_date" +%s 2>/dev/null || echo 0)
  now=$(date +%s)
  age=$(( now - commit_epoch ))
  if [[ $commit_epoch -gt 0 && $age -lt 300 ]]; then
    echo "PR#$PR_NUMBER head is ${age}s old (<300s), cooldown skip"
    exit 0
  fi
fi

gh pr checkout "$PR_NUMBER"
git fetch origin main

if git rebase origin/main; then
  git push --force-with-lease origin "HEAD:refs/heads/$head_ref"
  echo "PR#$PR_NUMBER rebased and pushed ($head_ref)"
  exit 0
fi

unmerged=$(git diff --name-only --diff-filter=U || true)
if [[ -z "$unmerged" ]]; then
  git rebase --abort || true
  echo "PR#$PR_NUMBER rebase failed, abort" >&2
  exit 1
fi

only=true
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  is_known "$f" || only=false
done <<< "$unmerged"

if [[ "$only" != "true" ]]; then
  git rebase --abort || true
  echo "PR#$PR_NUMBER nontrivial conflicts, abort" >&2
  exit 1
fi

while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  git checkout --ours -- "$f"
done <<< "$unmerged"

python3 scripts/generate_tracker_index.py
python3 scripts/generate_docs_index.py --write
pnpm install

git add -A
export GIT_EDITOR=true
if ! git rebase --continue; then
  git rebase --abort || true
  echo "PR#$PR_NUMBER rebase --continue failed" >&2
  exit 1
fi
git push --force-with-lease origin "HEAD:refs/heads/$head_ref"
echo "PR#$PR_NUMBER rebased with regen and pushed"
