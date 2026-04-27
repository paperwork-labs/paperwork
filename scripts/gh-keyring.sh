#!/usr/bin/env bash
# Run GitHub CLI with GITHUB_TOKEN unset so `gh` uses the keyring / OAuth login
# (full `repo` scope). Many setups — including Cursor — export a read-only or
# narrow PAT as GITHUB_TOKEN; `gh` prefers that over keyring and then
# `gh pr create` / `gh pr merge` fail with:
#   Resource not accessible by personal access token
#
# Repo scripts that need a PAT (e.g. pr-pipeline) should keep using GITHUB_TOKEN
# explicitly; use this wrapper only for interactive CLI.
set -euo pipefail
exec env -u GITHUB_TOKEN gh "$@"
