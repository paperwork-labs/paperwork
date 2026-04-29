#!/usr/bin/env bash
# Decommission script: apps.paperworklabs.com
#
# WS-48 (Phase C Wallet) — removes the stub `apps/accounts/` Vercel project
# and DNS record for apps.paperworklabs.com.
#
# SAFE TO RUN: all steps are reversible (DNS can be re-added, Vercel project
# is archived not deleted). See docs/runbooks/decommission-checklist.md.
#
# Pre-requisites:
#   export CLOUDFLARE_API_TOKEN=<account-wide or paperworklabs.com zone token>
#   export CLOUDFLARE_ZONE_ID=<paperworklabs.com zone id>
#   export VERCEL_API_TOKEN=<vercel token>
#   export VERCEL_TEAM_ID=<team id>  # leave empty if personal account
#   export VERCEL_PROJECT_NAME=accounts  # Vercel project name for apps.paperworklabs.com
#
# Run with: bash scripts/decommission/apps-paperworklabs-com.sh
# Run dry-run: DRY_RUN=1 bash scripts/decommission/apps-paperworklabs-com.sh

set -euo pipefail

DOMAIN="apps.paperworklabs.com"
CF_ZONE_ID="${CLOUDFLARE_ZONE_ID:-}"
CF_TOKEN="${CLOUDFLARE_API_TOKEN:-}"
VERCEL_TOKEN="${VERCEL_API_TOKEN:-}"
VERCEL_TEAM="${VERCEL_TEAM_ID:-}"
VERCEL_PROJECT="${VERCEL_PROJECT_NAME:-accounts}"
DRY_RUN="${DRY_RUN:-0}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
dry()   { echo -e "${YELLOW}[DRY-RUN]${NC} Would execute: $*"; }

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

info "=== apps.paperworklabs.com decommission ==="
info "Domain: $DOMAIN"
info "Dry-run: $DRY_RUN"

if [[ -z "$CF_ZONE_ID" ]]; then
  error "CLOUDFLARE_ZONE_ID is not set"
  exit 1
fi
if [[ -z "$CF_TOKEN" ]]; then
  error "CLOUDFLARE_API_TOKEN is not set"
  exit 1
fi
if [[ -z "$VERCEL_TOKEN" ]]; then
  error "VERCEL_API_TOKEN is not set"
  exit 1
fi

# ---------------------------------------------------------------------------
# Step 1: Check analytics (reminder — must be done manually before running)
# ---------------------------------------------------------------------------

info "Step 1: Checking DNS resolution for $DOMAIN..."
RESOLVED=$(dig +short "$DOMAIN" 2>/dev/null || true)
if [[ -n "$RESOLVED" ]]; then
  info "  DNS resolves to: $RESOLVED"
else
  warn "  DNS does not resolve (may already be removed or propagating)"
fi

cat <<'MSG'

=== MANUAL PRE-FLIGHT REQUIRED ===
Before proceeding, confirm you have checked:
  1. PostHog analytics: last-30-day traffic for apps.paperworklabs.com
  2. Clerk dashboard: no redirect URIs pointing to this domain
  3. n8n: no webhook triggers for this domain
  4. Founder sign-off received

Press Ctrl+C to abort, or Enter to continue.
MSG
read -r

# ---------------------------------------------------------------------------
# Step 2: Remove Cloudflare DNS record
# ---------------------------------------------------------------------------

info "Step 2: Finding DNS records for $DOMAIN in Cloudflare zone $CF_ZONE_ID..."

RECORDS=$(curl -s \
  "https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID}/dns_records?name=${DOMAIN}" \
  -H "Authorization: Bearer ${CF_TOKEN}" \
  -H "Content-Type: application/json")

RECORD_IDS=$(echo "$RECORDS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for r in data.get('result', []):
    print(r['id'] + '|' + r['type'] + '|' + r['content'])
" 2>/dev/null || true)

if [[ -z "$RECORD_IDS" ]]; then
  warn "  No DNS records found for $DOMAIN — may already be removed"
else
  while IFS='|' read -r record_id record_type record_content; do
    info "  Found: $record_type $DOMAIN → $record_content (id: $record_id)"
    if [[ "$DRY_RUN" == "1" ]]; then
      dry "DELETE https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID}/dns_records/${record_id}"
    else
      DEL_RESP=$(curl -s -X DELETE \
        "https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID}/dns_records/${record_id}" \
        -H "Authorization: Bearer ${CF_TOKEN}" \
        -H "Content-Type: application/json")
      SUCCESS=$(echo "$DEL_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success', False))" 2>/dev/null || echo "false")
      if [[ "$SUCCESS" == "True" ]] || [[ "$SUCCESS" == "true" ]]; then
        info "  Deleted DNS record $record_id ✓"
      else
        error "  Failed to delete DNS record $record_id: $DEL_RESP"
        exit 1
      fi
    fi
  done <<< "$RECORD_IDS"
fi

# ---------------------------------------------------------------------------
# Step 3: Archive Vercel project (NOT delete — preserves history)
# ---------------------------------------------------------------------------

info "Step 3: Archiving Vercel project '$VERCEL_PROJECT'..."

TEAM_PARAM=""
if [[ -n "$VERCEL_TEAM" ]]; then
  TEAM_PARAM="?teamId=${VERCEL_TEAM}"
fi

if [[ "$DRY_RUN" == "1" ]]; then
  dry "PATCH https://api.vercel.com/v9/projects/${VERCEL_PROJECT}${TEAM_PARAM} {live: false}"
else
  ARCHIVE_RESP=$(curl -s -X PATCH \
    "https://api.vercel.com/v9/projects/${VERCEL_PROJECT}${TEAM_PARAM}" \
    -H "Authorization: Bearer ${VERCEL_TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{"live": false}')
  # Vercel returns the project object on success; check for error field
  HAS_ERROR=$(echo "$ARCHIVE_RESP" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('yes' if 'error' in d else 'no')
" 2>/dev/null || echo "unknown")

  if [[ "$HAS_ERROR" == "yes" ]]; then
    error "  Vercel archive failed: $ARCHIVE_RESP"
    warn "  If project is already archived or name is wrong, this may be safe to ignore."
    warn "  Verify manually at https://vercel.com/dashboard"
  else
    info "  Vercel project '$VERCEL_PROJECT' archived ✓"
  fi
fi

# ---------------------------------------------------------------------------
# Step 4: Update decommissions.json
# ---------------------------------------------------------------------------

info "Step 4: Updating decommissions.json..."

DECOMMISSIONS_FILE="$(dirname "$0")/../../apis/brain/data/decommissions.json"
if [[ ! -f "$DECOMMISSIONS_FILE" ]]; then
  warn "  decommissions.json not found at $DECOMMISSIONS_FILE — update manually"
else
  NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  ACTOR="${GITHUB_ACTOR:-$(git config user.name 2>/dev/null || echo "unknown")}"
  if [[ "$DRY_RUN" == "1" ]]; then
    dry "Update decommissions.json: status=done, decommissioned_at=$NOW, decommissioned_by=$ACTOR"
  else
    python3 - "$DECOMMISSIONS_FILE" "$NOW" "$ACTOR" <<'PYEOF'
import sys, json
path, now, actor = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path) as f:
    data = json.load(f)
for entry in data["entries"]:
    if entry["id"] == "apps-paperworklabs-com":
        entry["status"] = "done"
        entry["decommissioned_at"] = now
        entry["decommissioned_by"] = actor
with open(path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
print(f"Updated: {path}")
PYEOF
    info "  decommissions.json updated ✓"
  fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
info "=== Decommission complete ==="
if [[ "$DRY_RUN" == "1" ]]; then
  warn "DRY-RUN mode — no changes were made. Re-run without DRY_RUN=1 to apply."
else
  info "Post-decommission verification:"
  info "  dig +short $DOMAIN  (should be empty)"
  info "  curl -I https://$DOMAIN  (should return 404 or connection error)"
  info "  GET /api/v1/admin/decommissions?status=done  (should include apps-paperworklabs-com)"
  info ""
  info "Rollback instructions: docs/runbooks/decommission-checklist.md → Rollback section"
fi
