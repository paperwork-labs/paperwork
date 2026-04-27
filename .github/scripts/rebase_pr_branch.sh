#!/usr/bin/env bash
# Rebase current branch onto origin/main; resolve known generated-file conflicts.
set -euo pipefail

git fetch origin main

if git rebase origin/main; then
  git push --force-with-lease origin "HEAD"
  exit 0
fi

echo "::notice::Rebase stopped for conflicts — applying heuristics for generated files"
for f in apps/studio/src/data/tracker-index.json docs/_index.yaml pnpm-lock.yaml; do
  if git diff --name-only --diff-filter=U 2>/dev/null | grep -qx "$f"; then
    # During rebase, "ours" is the commit being rebased onto (main).
    git checkout --ours -- "$f" || true
  fi
done

python3 scripts/generate_tracker_index.py 2>/dev/null || make tracker-index 2>/dev/null || true
python3 scripts/generate_docs_index.py --write 2>/dev/null || true
corepack enable 2>/dev/null || true
pnpm install --no-frozen-lockfile 2>/dev/null || true
git add -A

if ! GIT_EDITOR=true git rebase --continue; then
  git rebase --abort
  echo "::error::Rebase could not be completed automatically; resolve conflicts locally"
  exit 1
fi

git push --force-with-lease origin "HEAD"
