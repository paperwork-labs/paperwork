#!/usr/bin/env bash
# Drain the current Dependabot PR backlog using the same classification
# rules as .github/workflows/dependabot-auto-approve.yaml.
#
# Safe bumps → gh pr review --approve + gh pr merge --auto --squash.
# Major bumps → gh pr edit --add-label deps:major (then the triage
#               workflow will pick them up).
#
# Usage:
#   .github/scripts/drain-dependabot-backlog.sh            # apply
#   .github/scripts/drain-dependabot-backlog.sh --dry-run  # preview only
#
# Requires: gh CLI authenticated as a user with approve+merge rights.
# Dependabot metadata comes from the PR branch name + title, since the
# fetch-metadata action only runs inside GitHub Actions.
set -euo pipefail

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
fi

classify() {
  local ref="$1" title="$2"

  if [[ "$ref" == *"minor-and-patch"* ]]; then
    echo "safe|grouped minor-and-patch"
    return
  fi
  if [[ "$ref" == dependabot/github_actions/* ]]; then
    echo "safe|github-actions bump"
    return
  fi

  # Extract "from X.Y.Z to A.B.C" from the title — or "from >=X.Y.Z to >=A.B.C".
  local from_v to_v
  if [[ "$title" =~ from[[:space:]]+([^[:space:]]+)[[:space:]]+to[[:space:]]+([^[:space:]]+) ]]; then
    from_v="${BASH_REMATCH[1]}"
    to_v="${BASH_REMATCH[2]}"
    # Strip any leading comparators (>=, ^, ~, v, =, >).
    from_v="${from_v#>=}"; from_v="${from_v#<=}"; from_v="${from_v#>}"; from_v="${from_v#<}"
    from_v="${from_v#^}"; from_v="${from_v#~}"; from_v="${from_v#=}"; from_v="${from_v#v}"
    to_v="${to_v#>=}"; to_v="${to_v#<=}"; to_v="${to_v#>}"; to_v="${to_v#<}"
    to_v="${to_v#^}"; to_v="${to_v#~}"; to_v="${to_v#=}"; to_v="${to_v#v}"
    local from_major="${from_v%%.*}"
    local to_major="${to_v%%.*}"
    if [[ "$from_major" =~ ^[0-9]+$ ]] && [[ "$to_major" =~ ^[0-9]+$ ]]; then
      if (( to_major > from_major )); then
        echo "major|semver ${from_v} -> ${to_v}"
        return
      fi
      echo "safe|semver ${from_v} -> ${to_v}"
      return
    fi
  fi

  echo "unknown|could not parse bump from title: ${title}"
}

total=0
safe=0
major=0
unknown=0

gh pr list --author "app/dependabot" --state open --limit 200 \
  --json number,title,headRefName > /tmp/drain-prs.json

jq -c '.[]' /tmp/drain-prs.json | while IFS= read -r pr; do
  total=$((total + 1))
  number=$(jq -r '.number' <<<"$pr")
  title=$(jq -r '.title' <<<"$pr")
  ref=$(jq -r '.headRefName' <<<"$pr")
  result=$(classify "$ref" "$title")
  kind="${result%%|*}"
  reason="${result#*|}"

  case "$kind" in
    safe)
      safe=$((safe + 1))
      echo "[safe]    #${number}  ${title}"
      echo "          reason: ${reason}"
      if ! $DRY_RUN; then
        gh pr review "$number" --approve \
          --body "auto-approved by drain-dependabot-backlog — ${reason}" \
          2>&1 | sed 's/^/          /' || true
        gh pr merge "$number" --auto --squash \
          2>&1 | sed 's/^/          /' || true
      fi
      ;;
    major)
      major=$((major + 1))
      echo "[major]   #${number}  ${title}"
      echo "          reason: ${reason}"
      if ! $DRY_RUN; then
        gh pr edit "$number" --add-label "deps:major" \
          2>&1 | sed 's/^/          /' || true
      fi
      ;;
    *)
      unknown=$((unknown + 1))
      echo "[unknown] #${number}  ${title}"
      echo "          reason: ${reason}"
      ;;
  esac
done

echo
if $DRY_RUN; then
  echo "DRY-RUN summary (nothing was changed):"
else
  echo "Done."
fi
