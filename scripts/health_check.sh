#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-infra/env.dev}"
if [[ -f "$ENV_FILE" ]]; then
  set -o allexport
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +o allexport
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "❌ curl is required for health checks."
  exit 1
fi

BACKEND_HOST_PORT="${BACKEND_HOST_PORT:-8000}"
WEB_HOST_PORT="${WEB_HOST_PORT:-3000}"
FLOWER_HOST_PORT="${FLOWER_HOST_PORT:-5555}"
LADLE_HOST_PORT="${LADLE_HOST_PORT:-61000}"

MAX_WAIT="${HEALTHCHECK_MAX_WAIT:-90}"
INTERVAL="${HEALTHCHECK_INTERVAL:-3}"

checks=(
  "backend|http://localhost:${BACKEND_HOST_PORT}/health"
  "frontend|http://localhost:${WEB_HOST_PORT}"
  "ladle|http://localhost:${LADLE_HOST_PORT}"
  "flower|http://localhost:${FLOWER_HOST_PORT}"
)

echo "🔎 Running health checks (timeout: ${MAX_WAIT}s)..."

failures=()
for check in "${checks[@]}"; do
  name="${check%%|*}"
  url="${check#*|}"
  elapsed=0

  printf " - %s: " "$name"
  until curl -fsS --max-time 2 "$url" >/dev/null 2>&1; do
    sleep "$INTERVAL"
    elapsed=$((elapsed + INTERVAL))
    if (( elapsed >= MAX_WAIT )); then
      echo "FAILED (${url})"
      failures+=("$name")
      break
    fi
  done

  if (( elapsed < MAX_WAIT )); then
    echo "OK"
  fi
done

if (( ${#failures[@]} > 0 )); then
  echo "❌ Health checks failed: ${failures[*]}"
  exit 1
fi

echo "✅ All health checks passed."
