#!/usr/bin/env bash
# swap-custom-domains.sh — remove custom domains from OLD services,
# add them to NEW services, and update Cloudflare CNAMEs.
#
# Requires:
#   - AF_OLD_RENDER_KEY + old service IDs
#   - AF_NEW_RENDER_KEY + new service IDs
#   - CLOUDFLARE_API_TOKEN, CLOUDFLARE_ZONE_ID
#
# Domains moved:
#   - api.axiomfolio.com      → new axiomfolio-api
#   - axiomfolio.com + www    → new axiomfolio-frontend

set -euo pipefail

: "${AF_OLD_RENDER_KEY:?}" "${AF_NEW_RENDER_KEY:?}"
: "${AF_OLD_API_SERVICE_ID:?}" "${AF_NEW_API_SERVICE_ID:?}"
: "${AF_OLD_FRONTEND_SERVICE_ID:?}" "${AF_NEW_FRONTEND_SERVICE_ID:?}"
: "${CLOUDFLARE_API_TOKEN:?}" "${CLOUDFLARE_ZONE_ID:?}"

API="https://api.render.com/v1"
CF="https://api.cloudflare.com/client/v4"

get_new_hostname() {
  # <svc-id>.onrender.com (web services) or <svc-id>.onrender.com (static)
  local id="$1"
  curl -sS -H "Authorization: Bearer $AF_NEW_RENDER_KEY" "$API/services/$id" \
    | jq -r '.serviceDetails.url // .slug' \
    | sed 's|^https\?://||'
}

remove_custom_domain() {
  local key="$1" svc_id="$2" domain="$3"
  local cds
  cds=$(curl -sS -H "Authorization: Bearer $key" \
    "$API/services/$svc_id/custom-domains?limit=50")
  local cd_id
  cd_id=$(echo "$cds" | jq -r --arg d "$domain" '.[] | .customDomain | select(.name == $d) | .id' | head -1)
  if [[ -n "$cd_id" && "$cd_id" != "null" ]]; then
    echo "   removing $domain ($cd_id) from $svc_id"
    curl -sS -X DELETE -H "Authorization: Bearer $key" \
      "$API/services/$svc_id/custom-domains/$cd_id" >/dev/null
  else
    echo "   $domain not attached to $svc_id (already removed)"
  fi
}

add_custom_domain() {
  local key="$1" svc_id="$2" domain="$3"
  echo "   adding $domain to $svc_id"
  curl -sS -X POST -H "Authorization: Bearer $key" -H "Content-Type: application/json" \
    "$API/services/$svc_id/custom-domains" \
    -d "$(jq -nc --arg n "$domain" '{name: $n}')" | jq -r '.customDomain.name // .message'
}

update_cname() {
  local host="$1" target="$2"
  local rec
  rec=$(curl -sS -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
    "$CF/zones/$CLOUDFLARE_ZONE_ID/dns_records?name=$host&type=CNAME")
  local rec_id
  rec_id=$(echo "$rec" | jq -r '.result[0].id // empty')
  local payload
  payload=$(jq -nc --arg n "$host" --arg c "$target" \
    '{type:"CNAME", name:$n, content:$c, ttl:300, proxied:true}')
  if [[ -n "$rec_id" ]]; then
    echo "   updating CF CNAME $host → $target"
    curl -sS -X PUT -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" -H "Content-Type: application/json" \
      "$CF/zones/$CLOUDFLARE_ZONE_ID/dns_records/$rec_id" -d "$payload" \
      | jq -r '.success'
  else
    echo "   creating CF CNAME $host → $target"
    curl -sS -X POST -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" -H "Content-Type: application/json" \
      "$CF/zones/$CLOUDFLARE_ZONE_ID/dns_records" -d "$payload" \
      | jq -r '.success'
  fi
}

new_api_host=$(get_new_hostname "$AF_NEW_API_SERVICE_ID")
new_fe_host=$(get_new_hostname "$AF_NEW_FRONTEND_SERVICE_ID")
echo "new API  onrender host: $new_api_host"
echo "new FE   onrender host: $new_fe_host"

echo ">> Removing custom domains from OLD services"
remove_custom_domain "$AF_OLD_RENDER_KEY" "$AF_OLD_API_SERVICE_ID" "api.axiomfolio.com"
remove_custom_domain "$AF_OLD_RENDER_KEY" "$AF_OLD_FRONTEND_SERVICE_ID" "axiomfolio.com"
remove_custom_domain "$AF_OLD_RENDER_KEY" "$AF_OLD_FRONTEND_SERVICE_ID" "www.axiomfolio.com"

echo ">> Adding custom domains to NEW services"
add_custom_domain "$AF_NEW_RENDER_KEY" "$AF_NEW_API_SERVICE_ID" "api.axiomfolio.com"
add_custom_domain "$AF_NEW_RENDER_KEY" "$AF_NEW_FRONTEND_SERVICE_ID" "axiomfolio.com"
add_custom_domain "$AF_NEW_RENDER_KEY" "$AF_NEW_FRONTEND_SERVICE_ID" "www.axiomfolio.com"

echo ">> Updating Cloudflare CNAMEs"
update_cname "api.axiomfolio.com" "$new_api_host"
update_cname "axiomfolio.com"     "$new_fe_host"
update_cname "www.axiomfolio.com" "$new_fe_host"

echo ""
echo ">> Wait ~5 min for DNS propagation + Render SSL cert issuance. Verify with:"
echo "   ./verify.sh https://api.axiomfolio.com"
echo "   curl -sI https://axiomfolio.com | head"
