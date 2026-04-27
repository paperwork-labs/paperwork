#!/usr/bin/env bash
# Rebase same-repo open PR branches onto main after a main push. Skips drafts,
# fork PRs, PRs not behind main, and opt-out labels (default: no-auto-rebase).
# Delegates to .github/scripts/rebase_pr_branch.sh.
set -u

: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"
: "${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}"

REPO="${GITHUB_REPOSITORY}"
cd "${GITHUB_WORKSPACE}"

MAIN_REF="${MAIN_REF:-main}"
MAX_PR="${MAX_REBASER_PRS_PER_RUN:-20}"

if ! command -v gh >/dev/null 2>&1; then
  echo "::error::gh is required"
  exit 1
fi

gh auth setup-git
git config --global --add safe.directory "${GITHUB_WORKSPACE}"

git fetch "origin" "${MAIN_REF}"
git checkout "${MAIN_REF}"
git reset --hard "origin/${MAIN_REF}"

mapfile -t pr_nums < <(
  gh pr list -R "$REPO" --state open -L 100 \
    --json number,isDraft,isCrossRepository \
    -q '.[] | select(.isDraft|not) | select((.isCrossRepository // false) | not) | .number' 2>/dev/null \
  | head -n "$MAX_PR"
)

results_ok=0
results_skip=0
results_fail=0
summary_lines=()

if [[ ${#pr_nums[@]} -eq 0 || -z "${pr_nums[0]:-}" ]]; then
  {
    echo "## Auto-rebase on \`${MAIN_REF}\` push"
    echo ""
    echo "No in-repo, non-draft open PRs in this batch (limit ${MAX_PR})."
  } >> "${GITHUB_STEP_SUMMARY:-/dev/stdout}"
  if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    echo "results_ok=0" >> "$GITHUB_OUTPUT"
    echo "results_skip=0" >> "$GITHUB_OUTPUT"
    echo "results_fail=0" >> "$GITHUB_OUTPUT"
  fi
  exit 0
fi

for pr_num in "${pr_nums[@]}"; do
  [[ -z "${pr_num:-}" ]] && continue

  # Opt-out labels (comma-separated in OPT_OUT_LABELS)
  label_block=$(gh pr view "$pr_num" -R "$REPO" --json labels -q '.labels | map(.name) | @json' 2>/dev/null || echo "[]")
  skip_label=0
  if [[ -n "${OPT_OUT_LABELS:-}" ]]; then
    IFS=',' read -r -a _opts <<< "${OPT_OUT_LABELS}"
  else
    _opts=("no-auto-rebase")
  fi
  for raw in "${_opts[@]}"; do
    lab="${raw#"${raw%%[![:space:]]*}"}"; lab="${lab%"${lab##*[![:space:]]}"}"
    [[ -z "$lab" ]] && continue
    if echo "$label_block" | grep -qF "$lab"; then
      skip_label=1
      break
    fi
  done
  if [[ "$skip_label" -eq 1 ]]; then
    echo "::notice::PR #${pr_num} skipped (opt-out label)"
    summary_lines+=("#${pr_num} skip — opt-out label")
    results_skip=$((results_skip + 1))
    continue
  fi

  head_sha=$(gh pr view "$pr_num" -R "$REPO" --json headRefOid -q .headRefOid)
  owner=${REPO%%/*}
  name=${REPO#*/}
  behind_by=$(gh api "repos/${owner}/${name}/compare/${MAIN_REF}...${head_sha}" -q ".behind_by // 0" 2>/dev/null || echo 0)

  if [[ "${behind_by:-0}" -eq 0 ]]; then
    echo "::notice::PR #${pr_num} already on latest ${MAIN_REF}"
    summary_lines+=("#${pr_num} skip — up to date with ${MAIN_REF}")
    results_skip=$((results_skip + 1))
    continue
  fi

  echo "::group::Rebase PR #${pr_num} (behind_by=${behind_by})"
  if ! gh pr checkout "$pr_num" -R "$REPO"; then
    echo "::error::checkout failed for PR #${pr_num}"
    summary_lines+=("#${pr_num} fail — checkout")
    results_fail=$((results_fail + 1))
    echo "::endgroup::"
    git checkout "${MAIN_REF}" && git reset --hard "origin/${MAIN_REF}"
    continue
  fi
  export MAIN_REF
  if bash .github/scripts/rebase_pr_branch.sh; then
    summary_lines+=("#${pr_num} ok")
    results_ok=$((results_ok + 1))
  else
    echo "::error::rebase/push failed for PR #${pr_num}"
    summary_lines+=("#${pr_num} fail — rebase or push")
    results_fail=$((results_fail + 1))
  fi
  echo "::endgroup::"
  git checkout "${MAIN_REF}" && git reset --hard "origin/${MAIN_REF}"
done

{
  echo "## Auto-rebase on \`${MAIN_REF}\` push"
  echo ""
  echo "| Metric | Count |"
  echo "| --- | ---: |"
  echo "| Rebased ok | $results_ok |"
  echo "| Skipped | $results_skip |"
  echo "| Failed | $results_fail |"
  echo ""
  if [[ ${#summary_lines[@]} -eq 0 ]]; then
    echo "_(no per-PR detail)_"
  else
    echo "### Per-PR"
    for line in "${summary_lines[@]}"; do
      echo "- $line"
    done
  fi
} >> "${GITHUB_STEP_SUMMARY:-/dev/stdout}"

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  {
    echo "results_ok=$results_ok"
    echo "results_skip=$results_skip"
    echo "results_fail=$results_fail"
  } >> "$GITHUB_OUTPUT"
fi

if [[ "$results_fail" -gt 0 ]]; then
  exit 1
fi
exit 0
