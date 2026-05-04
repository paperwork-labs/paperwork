#!/usr/bin/env bash
# verify_provider_token_scopes.sh — preflight for T3.1 IaC drift detector.
# Reads tokens from Studio Vault via ./scripts/vault-get.sh, hits each provider's
# verification / minimal read endpoint, prints PASS/FAIL per provider.
#
# Prerequisites: jq, curl; repo-root .env.local with SECRETS_API_KEY (or admin
# auth per scripts/vault-get.sh). No secrets are embedded in this file.
#
# Usage: from repo root — ./scripts/audits/verify_provider_token_scopes.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VAULT_GET="$REPO_ROOT/scripts/vault-get.sh"
TMPDIR="$(mktemp -d "${TMPDIR:-/tmp}/verify_provider_scopes.XXXXXX")"
cleanup() { rm -rf "$TMPDIR"; }
trap cleanup EXIT

if [[ ! -x "$VAULT_GET" ]]; then
  echo "FAIL: $VAULT_GET not found or not executable" >&2
  exit 1
fi

vault_plain() {
  local name="$1"
  local out
  if ! out="$("$VAULT_GET" "$name" 2>/dev/null)"; then
    return 1
  fi
  printf '%s' "$out" | tr -d '\r'
}

# Try vault names in order; stdout = token or empty.
first_vault() {
  local n v
  for n in "$@"; do
    v="$(vault_plain "$n" || true)"
    if [[ -n "$v" ]]; then
      printf '%s' "$v"
      return 0
    fi
  done
  return 1
}

any_failed=0

fail_provider() {
  echo "FAIL: $1 — $2" >&2
  any_failed=1
}

pass_provider() {
  echo "PASS: $1 — $2"
}

# --- Cloudflare
echo "=== Cloudflare ==="
if ! CF_TOKEN="$(first_vault CLOUDFLARE_API_TOKEN CF_API_TOKEN CF_TOKEN)"; then
  fail_provider "Cloudflare" "no vault secret CLOUDFLARE_API_TOKEN (or CF_API_TOKEN / CF_TOKEN)"
else
  cf_json="$(curl -sS -H "Authorization: Bearer ${CF_TOKEN}" \
    "https://api.cloudflare.com/client/v4/user/tokens/verify")"
  if echo "$cf_json" | jq -e '.success == true' >/dev/null 2>&1; then
    pass_provider "Cloudflare" "GET /user/tokens/verify returned success (inspect .result.policies for zone scope)"
  else
    fail_provider "Cloudflare" "token verify unsuccessful ($(echo "$cf_json" | jq -c '.errors // .'))"
  fi
fi

# --- Render (owners + services + env-vars probe)
echo "=== Render ==="
if ! RENDER_KEY="$(first_vault RENDER_API_KEY)"; then
  fail_provider "Render" "no vault secret RENDER_API_KEY"
else
  ro="${TMPDIR}/render_owners.json"
  rs="${TMPDIR}/render_svc.json"
  re="${TMPDIR}/render_env.json"
  rh="$(curl -sS -o "$ro" -w '%{http_code}' \
    -H "Authorization: Bearer ${RENDER_KEY}" \
    "https://api.render.com/v1/owners?limit=1")"
  if [[ "$rh" != "200" ]]; then
    fail_provider "Render" "GET /v1/owners HTTP $rh"
  else
    sh="$(curl -sS -o "$rs" -w '%{http_code}' \
      -H "Authorization: Bearer ${RENDER_KEY}" \
      "https://api.render.com/v1/services?limit=1")"
    if [[ "$sh" != "200" ]]; then
      fail_provider "Render" "GET /v1/services HTTP $sh"
    else
      sid="$(jq -r '
        (if type == "array" then . else (.services // []) end)
        | .[0]
        | if . == null then empty else (.service.id // .id) end
      ' "$rs" 2>/dev/null || true)"
      if [[ -z "$sid" || "$sid" == "null" ]]; then
        fail_provider "Render" "could not parse service id from /v1/services response (check jq path vs API shape)"
      else
        eh="$(curl -sS -o "$re" -w '%{http_code}' \
          -H "Authorization: Bearer ${RENDER_KEY}" \
          "https://api.render.com/v1/services/${sid}/env-vars?limit=1")"
        if [[ "$eh" != "200" ]]; then
          fail_provider "Render" "GET /v1/services/{id}/env-vars HTTP $eh (needs EnvVar:Read)"
        else
          pass_provider "Render" "owners + services + env-vars readable (serviceId=$sid)"
        fi
      fi
    fi
  fi
fi

# --- Clerk (instance + domains)
echo "=== Clerk ==="
if ! CLERK_SECRET="$(first_vault CLERK_SECRET_KEY)"; then
  fail_provider "Clerk" "no vault secret CLERK_SECRET_KEY"
else
  CLERK_API_BASE="${CLERK_API_URL:-https://api.clerk.com}"
  CLERK_API_BASE="${CLERK_API_BASE%/}"
  ci="${TMPDIR}/clerk_inst.json"
  cd="${TMPDIR}/clerk_dom.json"
  ih="$(curl -sS -o "$ci" -w '%{http_code}' \
    -H "Authorization: Bearer ${CLERK_SECRET}" \
    "${CLERK_API_BASE}/v1/instance")"
  dh="$(curl -sS -o "$cd" -w '%{http_code}' \
    -H "Authorization: Bearer ${CLERK_SECRET}" \
    "${CLERK_API_BASE}/v1/domains?limit=1")"
  if [[ "$ih" != "200" ]]; then
    fail_provider "Clerk" "GET /v1/instance HTTP $ih"
  elif [[ "$dh" != "200" ]]; then
    fail_provider "Clerk" "GET /v1/domains HTTP $dh"
  else
    pass_provider "Clerk" "instance + domains endpoints OK"
  fi
fi

# --- Hetzner Cloud
echo "=== Hetzner ==="
if ! HZ_TOKEN="$(first_vault HETZNER_API_TOKEN)"; then
  fail_provider "Hetzner" "no vault secret HETZNER_API_TOKEN"
else
  hz="${TMPDIR}/hz_srv.json"
  hh="$(curl -sS -o "$hz" -w '%{http_code}' \
    -H "Authorization: Bearer ${HZ_TOKEN}" \
    "https://api.hetzner.cloud/v1/servers")"
  if [[ "$hh" != "200" ]]; then
    fail_provider "Hetzner" "GET /v1/servers HTTP $hh"
  else
    pass_provider "Hetzner" "GET /v1/servers OK"
  fi
fi

# --- Neon (projects + first project's branches)
echo "=== Neon ==="
if ! NEON_KEY="$(first_vault NEON_API_KEY)"; then
  fail_provider "Neon" "no vault secret NEON_API_KEY"
else
  np="${TMPDIR}/neon_proj.json"
  nb="${TMPDIR}/neon_br.json"
  ph="$(curl -sS -o "$np" -w '%{http_code}' \
    -H "Authorization: Bearer ${NEON_KEY}" \
    -H "Accept: application/json" \
    "https://console.neon.tech/api/v2/projects?limit=5")"
  if [[ "$ph" != "200" ]]; then
    fail_provider "Neon" "GET /api/v2/projects HTTP $ph"
  else
    pid="$(jq -r '.projects[0].id // empty' "$np")"
    if [[ -z "$pid" || "$pid" == "null" ]]; then
      fail_provider "Neon" "no projects returned (cannot test branch read)"
    else
      bh="$(curl -sS -o "$nb" -w '%{http_code}' \
        -H "Authorization: Bearer ${NEON_KEY}" \
        -H "Accept: application/json" \
        "https://console.neon.tech/api/v2/projects/${pid}/branches?limit=1")"
      if [[ "$bh" != "200" ]]; then
        fail_provider "Neon" "GET .../branches HTTP $bh (needs Branch:Read)"
      else
        pass_provider "Neon" "projects + branches OK (sample project_id=$pid)"
      fi
    fi
  fi
fi

echo "=== Summary ==="
if [[ "$any_failed" -ne 0 ]]; then
  echo "One or more providers FAILED — fix vault tokens or scopes, then re-run."
  exit 1
fi
echo "All listed providers PASS."
exit 0
