#!/usr/bin/env bash
# Upsert a secret in the Studio vault by name (POST /api/secrets), idempotent.
# Usage: see --help
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
  cat <<'EOF' >&2
Usage: scripts/vault-set.sh NAME [--value VALUE | --value-from-file PATH | --value-from-stdin]
                             [--service SERVICE] [--location LOCATION] [--description DESCRIPTION]
                             [--expires-at ISO8601] [--dry-run]

       scripts/vault-set.sh --batch FILE [--service SERVICE] [--location LOCATION] [--description DESCRIPTION] [--expires-at ISO8601] [--dry-run]

  Upserts a secret in the Studio Postgres-backed vault. NAME must match: ^[A-Z_][A-Z0-9_]*$
  (uppercase, underscores, digits only). Auth: SECRETS_API_KEY, or first admin email in
  ADMIN_EMAILS with ADMIN_ACCESS_PASSWORD. Env: STUDIO_URL (default https://paperworklabs.com),
  same .env.local loading as scripts/vault-get.sh.

  Value input (single-secret mode, NAME is the secret name; omit it when using --batch only):
  - --value / --value-from-file / --value-from-stdin, or
  - pipe a value on stdin, or
  - interactive: read -s (silent) when stdin is a TTY and no other value source.
  - Default --service: uncategorized (warning printed). Default --location: empty.
EOF
}

if [ "${1:-}" = "" ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
  usage
  exit 1
fi

# --- argument parsing
BATCH_FILE=""
ARG_VALUE=""
ARG_VALUE_FILE=""
ARG_VALUE_FROM_STDIN=false
NAME=""
SERVICE_OPT=""
LOCATION=""
DESCRIPTION=""
EXPIRES_AT=""
DRY_RUN=false

# shellcheck disable=SC2206
POSITIONALS=()

while [ $# -gt 0 ]; do
  case "$1" in
    -h | --help)
      usage
      exit 1
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --batch)
      if [ -z "${2:-}" ]; then
        echo "Error: --batch requires a file path" >&2
        exit 1
      fi
      BATCH_FILE="$2"
      shift 2
      ;;
    --value)
      if [ -z "${2:-}" ]; then
        echo "Error: --value requires an argument" >&2
        exit 1
      fi
      ARG_VALUE="$2"
      shift 2
      ;;
    --value-from-file)
      if [ -z "${2:-}" ]; then
        echo "Error: --value-from-file requires a path" >&2
        exit 1
      fi
      ARG_VALUE_FILE="$2"
      shift 2
      ;;
    --value-from-stdin)
      ARG_VALUE_FROM_STDIN=true
      shift
      ;;
    --service)
      if [ -z "${2:-}" ]; then
        echo "Error: --service requires an argument" >&2
        exit 1
      fi
      SERVICE_OPT="$2"
      shift 2
      ;;
    --location)
      if [ -z "${2:-}" ]; then
        echo "Error: --location requires an argument" >&2
        exit 1
      fi
      LOCATION="$2"
      shift 2
      ;;
    --description)
      if [ -z "${2:-}" ]; then
        echo "Error: --description requires an argument" >&2
        exit 1
      fi
      DESCRIPTION="$2"
      shift 2
      ;;
    --expires-at)
      if [ -z "${2:-}" ]; then
        echo "Error: --expires-at requires an argument" >&2
        exit 1
      fi
      EXPIRES_AT="$2"
      shift 2
      ;;
    --)
      shift
      while [ $# -gt 0 ]; do
        POSITIONALS+=("$1")
        shift
      done
      break
      ;;
    -*)
      echo "Error: unknown option: $1" >&2
      usage
      exit 1
      ;;
    *)
      POSITIONALS+=("$1")
      shift
      ;;
  esac
done

if [ -n "$BATCH_FILE" ]; then
  if [ "${#POSITIONALS[@]}" -gt 0 ]; then
    echo "Error: do not pass NAME with --batch" >&2
    exit 1
  fi
else
  if [ "${#POSITIONALS[@]}" -lt 1 ]; then
    echo "Error: SECRET_NAME is required" >&2
    usage
    exit 1
  fi
  NAME="${POSITIONALS[0]}"
fi

# --- env (match vault-get.sh)
if [ -f "$REPO_ROOT/.env.local" ]; then
  set -a
  # shellcheck source=/dev/null
  . "$REPO_ROOT/.env.local"
  set +a
fi
if [ -f "$REPO_ROOT/apps/studio/.env.local" ]; then
  set -a
  # shellcheck source=/dev/null
  . "$REPO_ROOT/apps/studio/.env.local"
  set +a
fi

STUDIO_URL="${STUDIO_URL:-https://paperworklabs.com}"
SECRETS_API_KEY="$(printf '%s' "${SECRETS_API_KEY:-}" | tr -d '\r\n')"
export SECRETS_API_KEY

ADMIN_EMAIL_FIRST="$(printf '%s' "${ADMIN_EMAILS:-}" | cut -d, -f1 | tr -d ' \"')"
ADMIN_PASS_TRIM="$(printf '%s' "${ADMIN_ACCESS_PASSWORD:-}" | tr -d '\r\n')"

# --- helpers
is_valid_name() {
  n="$1"
  [ -n "$n" ] && printf '%s' "$n" | grep -qE '^[A-Z_][A-Z0-9_]*$'
}

build_json_file() {
  # Writes JSON object to $1 (path); uses --rawfile for value from $2
  out_json="$1"
  valfile="$2"
  sn="$3"
  ss="$4"
  sl="${5:-}"
  sd="${6:-}"
  se="${7:-}"
  # shellcheck disable=SC2016
  jq -n \
    --arg name "$sn" \
    --rawfile value "$valfile" \
    --arg service "$ss" \
    --arg location "$sl" \
    --arg description "$sd" \
    --arg expires_at "$se" \
    '{
      name: $name,
      value: $value,
      service: $service,
      location: $location,
      description: $description,
      expires_at: (if $expires_at == "" then null else $expires_at end)
    }' >"$out_json"
}

# Write string value to temp file (preserves newlines, no command-substitution stripping)
write_value_to_temp() {
  t="$1"
  val="$2"
  printf '%s' "$val" >"$t"
}

post_upsert() {
  payload_file="$1"
  if [ ! -f "$payload_file" ]; then
    echo "Error: internal: missing payload file" >&2
    exit 1
  fi

  tmp_body="$(mktemp "${TMPDIR:-/tmp}/vault-set-body.XXXXXX")"
  url="${STUDIO_URL%/}/api/secrets"
  code="000"

  if [ -n "$SECRETS_API_KEY" ]; then
    if ! code=$(curl -sS -o "$tmp_body" -w "%{http_code}" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $SECRETS_API_KEY" \
      -d @"$payload_file" \
      "$url"); then
      code=000
    fi
  else
    if [ -n "$ADMIN_EMAIL_FIRST" ] && [ -n "$ADMIN_PASS_TRIM" ]; then
      if ! code=$(curl -sS -o "$tmp_body" -w "%{http_code}" \
        -H "Content-Type: application/json" \
        -u "$ADMIN_EMAIL_FIRST:$ADMIN_PASS_TRIM" \
        -d @"$payload_file" \
        "$url"); then
        code=000
      fi
    else
      rm -f "$tmp_body"
      echo "Error: set SECRETS_API_KEY, or ADMIN_EMAILS with ADMIN_ACCESS_PASSWORD" >&2
      exit 1
    fi
  fi

  if [ -n "$SECRETS_API_KEY" ] && [ "$code" = "401" ] && [ -n "$ADMIN_EMAIL_FIRST" ] && [ -n "$ADMIN_PASS_TRIM" ]; then
    if ! code=$(curl -sS -o "$tmp_body" -w "%{http_code}" \
      -H "Content-Type: application/json" \
      -u "$ADMIN_EMAIL_FIRST:$ADMIN_PASS_TRIM" \
      -d @"$payload_file" \
      "$url"); then
      code=000
    fi
  fi

  if [ "$code" = "200" ] || [ "$code" = "201" ]; then
    VAULT_SET_HTTP_CODE="$code"
    rm -f "$tmp_body"
    return 0
  fi

  echo "Error: HTTP $code" >&2
  if [ -f "$tmp_body" ]; then
    cat "$tmp_body" >&2
  fi
  rm -f "$tmp_body"
  exit 1
}

run_upsert_for_name() {
  sec_name="$1"
  # value file
  vfile="$2"
  ssvc="$3"
  sloc="$4"
  sdesc="$5"
  sexp="$6"

  if [ -z "$ssvc" ]; then
    echo "Warning: no --service; defaulting service to uncategorized" >&2
    ssvc="uncategorized"
  fi

  if ! is_valid_name "$sec_name"; then
    echo "Error: name must match ^[A-Z_][A-Z0-9_]*$ (e.g. MY_SECRET): got '$sec_name'" >&2
    exit 1
  fi

  payload="$(mktemp "${TMPDIR:-/tmp}/vault-set-payload.XXXXXX")"
  build_json_file "$payload" "$vfile" "$sec_name" "$ssvc" "$sloc" "$sdesc" "$sexp"

  if $DRY_RUN; then
    echo "DRY-RUN: would POST to ${STUDIO_URL%/}/api/secrets" >&2
    jq -c . "$payload"
    rm -f "$payload"
    return 0
  fi

  post_upsert "$payload"
  code_out="${VAULT_SET_HTTP_CODE:-}"
  rm -f "$payload"
  st="updated"
  if [ "$code_out" = "201" ]; then
    st="created"
  fi
  printf '✓ %s upserted in vault (service=%s, status=%s)\n' "$sec_name" "$ssvc" "$st"
}

# --- resolve single-secret value to temp file
if [ -z "$BATCH_FILE" ]; then
  nsrc=0
  if [ -n "$ARG_VALUE" ]; then
    nsrc=$((nsrc + 1))
  fi
  if [ -n "$ARG_VALUE_FILE" ]; then
    nsrc=$((nsrc + 1))
  fi
  if $ARG_VALUE_FROM_STDIN; then
    nsrc=$((nsrc + 1))
  fi
  if [ "$nsrc" -gt 1 ]; then
    echo "Error: use only one of --value, --value-from-file, or --value-from-stdin" >&2
    exit 1
  fi

  VAL_TEMP="$(mktemp "${TMPDIR:-/tmp}/vault-set-val.XXXXXX")"
  cleanup_v() { rm -f "$VAL_TEMP"; }
  trap 'cleanup_v' EXIT

  if [ -n "$ARG_VALUE" ]; then
    write_value_to_temp "$VAL_TEMP" "$ARG_VALUE"
  elif [ -n "$ARG_VALUE_FILE" ]; then
    if [ ! -f "$ARG_VALUE_FILE" ] || [ ! -r "$ARG_VALUE_FILE" ]; then
      echo "Error: cannot read file: $ARG_VALUE_FILE" >&2
      exit 1
    fi
    cat "$ARG_VALUE_FILE" >"$VAL_TEMP"
  elif $ARG_VALUE_FROM_STDIN; then
    cat >"$VAL_TEMP"
  elif [ ! -t 0 ]; then
    cat >"$VAL_TEMP"
  else
    read -r -s -p "Secret value: " PWDVAL || true
    echo "" >&2
    write_value_to_temp "$VAL_TEMP" "${PWDVAL:-}"
  fi

  run_upsert_for_name "$NAME" "$VAL_TEMP" "$SERVICE_OPT" "$LOCATION" "$DESCRIPTION" "$EXPIRES_AT"
  exit 0
fi

# --- batch: .env-style file
if [ ! -f "$BATCH_FILE" ] || [ ! -r "$BATCH_FILE" ]; then
  echo "Error: cannot read batch file: $BATCH_FILE" >&2
  exit 1
fi

if [ -n "$ARG_VALUE" ] || [ -n "$ARG_VALUE_FILE" ] || $ARG_VALUE_FROM_STDIN; then
  echo "Error: --value / --value-from-file / --value-from-stdin are not used with --batch" >&2
  exit 1
fi

if [ -z "$SERVICE_OPT" ]; then
  echo "Warning: no --service; defaulting service to uncategorized for all keys" >&2
  SERVICE_OPT="uncategorized"
fi

line_n=0
while IFS= read -r line || [ -n "$line" ]; do
  line_n=$((line_n + 1))
  # shellcheck disable=SC2001
  tline="$(printf '%s' "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  [ -z "$tline" ] && continue
  case "$tline" in
    \#*) continue ;;
  esac
  case "$tline" in
    *=*) ;;
    *)
      echo "Warning: line $line_n: no '=', skipping" >&2
      continue
      ;;
  esac
  k="${tline%%=*}"
  v="${tline#*=}"
  k="$(printf '%s' "$k" | tr -d ' ')"
  if [ -z "$k" ]; then
    echo "Warning: line $line_n: empty key, skipping" >&2
    continue
  fi
  if ! is_valid_name "$k"; then
    echo "Error: line $line_n: key '$k' must match ^[A-Z_][A-Z0-9_]*$" >&2
    exit 1
  fi

  ONE_VAL="$(mktemp "${TMPDIR:-/tmp}/vault-set-bval.XXXXXX")"
  printf '%s' "$v" >"$ONE_VAL"
  if ! run_upsert_for_name "$k" "$ONE_VAL" "$SERVICE_OPT" "$LOCATION" "$DESCRIPTION" "$EXPIRES_AT"; then
    rm -f "$ONE_VAL"
    exit 1
  fi
  rm -f "$ONE_VAL"
done <"$BATCH_FILE"

exit 0
