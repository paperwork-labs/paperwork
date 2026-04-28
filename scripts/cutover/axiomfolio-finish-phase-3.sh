#!/usr/bin/env bash
# axiomfolio-finish-phase-3.sh — Phase 3 DNS + Render custom-domain cutover (org Pro tier).
#
# Does NOT run destructive DB operations. Idempotent: safe to re-run.
#
# Prerequisites (founder):
#   - Org Render workspace upgraded to Pro (15 custom domains).
#   - export RENDER_API_KEY_OLD=...   (personal Render API key)
#   - export CLOUDFLARE_API_TOKEN=...
#   - export CLOUDFLARE_ZONE_ID=...   (axiomfolio.com zone)
# Org key: fetched via scripts/vault-get.sh RENDER_API_KEY (needs vault auth).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VAULT_GET="$REPO_ROOT/scripts/vault-get.sh"

API="https://api.render.com/v1"
CF="https://api.cloudflare.com/client/v4"

# NEW (Paperwork org)
readonly NEW_API_SERVICE_ID="srv-d7lg0o77f7vs73b2k7m0"
readonly NEW_FE_SERVICE_ID="srv-d7lg0dv7f7vs73b2k1u0"

# OLD (personal account) — detach only
readonly OLD_API_SERVICE_ID="srv-d64mkqi4d50c73eite20"
readonly OLD_FE_SERVICE_ID="srv-d64mkhi4d50c73eit7ng"

DRY_RUN=0

usage() {
  sed -n '1,22p' "$0" | tail -n +2
  echo ""
  echo "Usage: $0 [--dry-run] [--help]"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

: "${RENDER_API_KEY_OLD:?Founder: paste your personal Render API key here (export RENDER_API_KEY_OLD=...)}"
: "${CLOUDFLARE_API_TOKEN:?Set CLOUDFLARE_API_TOKEN (Cloudflare API token with DNS edit for the zone)}"
: "${CLOUDFLARE_ZONE_ID:?Set CLOUDFLARE_ZONE_ID (axiomfolio.com zone, see apis/axiomfolio/scripts/migration/README.md)}"

if [[ ! -f "$VAULT_GET" ]]; then
  echo "ABORT: missing $VAULT_GET" >&2
  exit 1
fi

RENDER_API_KEY_NEW="$("$VAULT_GET" RENDER_API_KEY | tr -d '\r\n')"
if [[ -z "$RENDER_API_KEY_NEW" ]]; then
  echo "ABORT: vault-get RENDER_API_KEY returned empty (check SECRETS_API_KEY / admin auth)" >&2
  exit 1
fi

http_json_get() {
  local url="$1" key="$2"
  curl -sS -H "Authorization: Bearer $key" -w '\n%{http_code}' "$url"
}

verify_render_key() {
  local label="$1" key="$2"
  local resp code body
  resp=$(http_json_get "$API/owners" "$key")
  code="${resp##*$'\n'}"
  body="${resp%$'\n'*}"
  if [[ "$code" != "200" ]]; then
    echo "ABORT: Render API key check failed for $label (HTTP $code): $body" >&2
    exit 1
  fi
}

verify_cf_zone() {
  local resp code body
  resp=$(curl -sS -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
    -w '\n%{http_code}' "$CF/zones/$CLOUDFLARE_ZONE_ID")
  code="${resp##*$'\n'}"
  body="${resp%$'\n'*}"
  if [[ "$code" != "200" ]] || ! echo "$body" | jq -e '.success == true' >/dev/null 2>&1; then
    echo "ABORT: Cloudflare zone check failed (HTTP $code): $body" >&2
    exit 1
  fi
}

get_onrender_host() {
  local key="$1" svc_id="$2"
  curl -sS -H "Authorization: Bearer $key" "$API/services/$svc_id" \
    | jq -r '.serviceDetails.url // .slug // empty' \
    | sed 's|^https\?://||; s|/$||'
}

remove_custom_domain() {
  local key="$1" svc_id="$2" domain="$3"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] Would remove custom domain $domain from service $svc_id (if attached)"
    return 0
  fi
  local cds cd_id
  cds=$(curl -sS -H "Authorization: Bearer $key" \
    "$API/services/$svc_id/custom-domains?limit=50")
  cd_id=$(echo "$cds" | jq -r --arg d "$domain" '.[] | .customDomain | select(.name == $d) | .id' | head -1)
  if [[ -n "$cd_id" && "$cd_id" != "null" ]]; then
    echo "   removing $domain ($cd_id) from $svc_id"
    local code
    code=$(curl -sS -o /dev/null -w '%{http_code}' -X DELETE -H "Authorization: Bearer $key" \
      "$API/services/$svc_id/custom-domains/$cd_id")
    if [[ "$code" != "200" && "$code" != "202" && "$code" != "204" ]]; then
      echo "ABORT: DELETE custom-domain $domain failed (HTTP $code)" >&2
      exit 1
    fi
  else
    echo "   $domain not attached to $svc_id (already removed)"
  fi
}

render_quota_abort() {
  echo "ABORT: Render workspace is on Hobby tier (2-domain cap reached). Upgrade to Pro at https://dashboard.render.com/billing before re-running." >&2
  exit 1
}

add_custom_domain() {
  local key="$1" svc_id="$2" domain="$3"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] Would POST custom domain $domain → service $svc_id"
    return 0
  fi
  echo "   adding $domain to $svc_id"
  local tmp code body
  tmp="$(mktemp)"
  code=$(curl -sS -o "$tmp" -w '%{http_code}' -X POST \
    -H "Authorization: Bearer $key" -H "Content-Type: application/json" \
    "$API/services/$svc_id/custom-domains" \
    -d "$(jq -nc --arg n "$domain" '{name: $n}')")
  body="$(cat "$tmp")"
  rm -f "$tmp"
  if [[ "$code" == "402" ]]; then
    render_quota_abort
  fi
  if [[ "$code" != "200" && "$code" != "201" && "$code" != "202" ]]; then
    echo "ABORT: POST custom-domain $domain failed (HTTP $code): $body" >&2
    exit 1
  fi
  echo "$body" | jq -r '.customDomain.name // .message // .' 2>/dev/null || true
}

update_cname() {
  local host="$1" target="$2"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] Would set Cloudflare CNAME $host → $target (proxied, ttl 300)"
    return 0
  fi
  local rec rec_id payload code body
  rec=$(curl -sS -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
    "$CF/zones/$CLOUDFLARE_ZONE_ID/dns_records?name=$host&type=CNAME")
  rec_id=$(echo "$rec" | jq -r '.result[0].id // empty')
  payload=$(jq -nc --arg n "$host" --arg c "$target" \
    '{type:"CNAME", name:$n, content:$c, ttl:300, proxied:true}')
  if [[ -n "$rec_id" ]]; then
    echo "   updating CF CNAME $host → $target"
    body=$(curl -sS -X PUT -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
      -H "Content-Type: application/json" \
      "$CF/zones/$CLOUDFLARE_ZONE_ID/dns_records/$rec_id" -d "$payload")
  else
    echo "   creating CF CNAME $host → $target"
    body=$(curl -sS -X POST -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
      -H "Content-Type: application/json" \
      "$CF/zones/$CLOUDFLARE_ZONE_ID/dns_records" -d "$payload")
  fi
  if ! echo "$body" | jq -e '.success == true' >/dev/null 2>&1; then
    echo "ABORT: Cloudflare DNS update failed for $host: $body" >&2
    exit 1
  fi
}

echo ">> Pre-flight"
verify_render_key "org (vault RENDER_API_KEY)" "$RENDER_API_KEY_NEW"
verify_render_key "personal (RENDER_API_KEY_OLD)" "$RENDER_API_KEY_OLD"
verify_cf_zone

new_api_host=$(get_onrender_host "$RENDER_API_KEY_NEW" "$NEW_API_SERVICE_ID")
new_fe_host=$(get_onrender_host "$RENDER_API_KEY_NEW" "$NEW_FE_SERVICE_ID")
if [[ -z "$new_api_host" || -z "$new_fe_host" ]]; then
  echo "ABORT: could not resolve onrender hostnames for new services (check service IDs / API)" >&2
  exit 1
fi
echo "   new API onrender host: $new_api_host"
echo "   new FE  onrender host: $new_fe_host"

if ! curl -sS -o /dev/null -f "https://$new_api_host/health"; then
  echo "ABORT: new API not healthy at https://$new_api_host/health (expected HTTP 200)" >&2
  exit 1
fi
if ! curl -sS -o /dev/null -f "https://$new_fe_host/"; then
  echo "ABORT: new frontend root not OK at https://$new_fe_host/ (expected HTTP 200)" >&2
  exit 1
fi
echo "   pre-flight: new .onrender.com endpoints return 200"

echo ""
echo ">> Detach custom domains from OLD (personal) services"
remove_custom_domain "$RENDER_API_KEY_OLD" "$OLD_API_SERVICE_ID" "api.axiomfolio.com"
remove_custom_domain "$RENDER_API_KEY_OLD" "$OLD_FE_SERVICE_ID" "axiomfolio.com"
remove_custom_domain "$RENDER_API_KEY_OLD" "$OLD_FE_SERVICE_ID" "www.axiomfolio.com"

echo ""
echo ">> Attach custom domains to NEW (org) services"
add_custom_domain "$RENDER_API_KEY_NEW" "$NEW_API_SERVICE_ID" "api.axiomfolio.com"
add_custom_domain "$RENDER_API_KEY_NEW" "$NEW_FE_SERVICE_ID" "axiomfolio.com"
add_custom_domain "$RENDER_API_KEY_NEW" "$NEW_FE_SERVICE_ID" "www.axiomfolio.com"

echo ""
echo ">> Update Cloudflare CNAMEs → new onrender hosts"
update_cname "api.axiomfolio.com" "$new_api_host"
update_cname "axiomfolio.com" "$new_fe_host"
update_cname "www.axiomfolio.com" "$new_fe_host"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo ""
  echo "[dry-run] Skipping SSL wait and smoke tests."
  exit 0
fi

echo ""
echo ">> Waiting for SSL / DNS (poll every 30s, max 10 min)"
deadline=$((SECONDS + 600))
while (( SECONDS < deadline )); do
  api_ok=0 fe_ok=0
  curl -sS -o /dev/null -f "https://api.axiomfolio.com/health" && api_ok=1 || true
  curl -sS -o /dev/null -f "https://axiomfolio.com/" && fe_ok=1 || true
  if [[ "$api_ok" -eq 1 && "$fe_ok" -eq 1 ]]; then
    echo "   both https://api.axiomfolio.com/health and https://axiomfolio.com/ return 200"
    break
  fi
  echo "   ($(date +%H:%M:%S)) still waiting (api=$api_ok fe=$fe_ok) ..."
  sleep 30
done

if [[ "$api_ok" -ne 1 || "$fe_ok" -ne 1 ]]; then
  echo "ABORT: timeout after 10m — custom domains or SSL not ready. Check Render dashboard + CF." >&2
  exit 1
fi

echo ""
echo ">> Smoke tests"
api_body=$(curl -sS "https://api.axiomfolio.com/health") || true
if ! echo "$api_body" | jq -e '.status == "healthy" and .version == "2.0.0"' >/dev/null 2>&1; then
  echo "ABORT: /health body does not match expected JSON (status=healthy, version=2.0.0)" >&2
  echo "Full response: $api_body" >&2
  exit 1
fi

fe_html=$(curl -sS "https://axiomfolio.com/") || true
if ! printf '%s' "$fe_html" | tr '\n' ' ' | grep -qiE '<title>[^<]*AxiomFolio'; then
  echo "ABORT: frontend root <title> does not contain AxiomFolio" >&2
  echo "Full response (first 2k): $(echo "$fe_html" | head -c 2000)" >&2
  exit 1
fi

echo ""
echo "================ FINAL REPORT ================"
echo "Domains now on NEW org services:"
echo "  api.axiomfolio.com  → $NEW_API_SERVICE_ID ($new_api_host)"
echo "  axiomfolio.com      → $NEW_FE_SERVICE_ID ($new_fe_host)"
echo "  www.axiomfolio.com  → $NEW_FE_SERVICE_ID ($new_fe_host)"
echo ""
echo "TLS issuer (api):"
curl -sSIv "https://api.axiomfolio.com/health" 2>&1 | grep -i 'issuer:' || echo "  (issuer line not found in curl -v output)"
echo "TLS issuer (frontend):"
curl -sSIv "https://axiomfolio.com/" 2>&1 | grep -i 'issuer:' || echo "  (issuer line not found in curl -v output)"
echo ""
echo "Phase 3 complete. Phase 4 (24h soak) starts now."
echo "============================================="
