---
owner: brain
last_reviewed: 2026-04-30
doc_kind: runbook
domain: ops
status: living
---

# Credential Access Runbook

Brain and agents have programmatic access to all infrastructure credentials. **Never ask the founder to manually set env vars or DNS** — use the APIs documented here.

## Credential Locations

| Credential | Location | How to Access |
|------------|----------|---------------|
| `RENDER_API_KEY` | Vercel Studio production env | `vercel env pull .env.production.local --environment production` then grep |
| `CLOUDFLARE_API_TOKEN` | Brain's Render env vars | Render API: `GET /v1/services/{brain-api-id}/env-vars` |
| `CLOUDFLARE_ACCOUNT_ID` | Brain's Render env vars | Same as above |
| `VERCEL_API_TOKEN` | Vercel Studio production env | `vercel env pull` (note: CLI auth is separate and already works) |
| Vercel CLI | Already authenticated | Just run `vercel` commands directly |

## Quick Reference: Service IDs

```bash
# Brain API on Render
BRAIN_SERVICE_ID="srv-d74f3cmuk2gs73a4013g"

# Cloudflare Zone IDs
AXIOMFOLIO_ZONE="e06277688d45265fb6e1240ca17e796e"
# Add other zones as needed
```

## Common Operations

### 1. Get Render API Key

```bash
cd /Users/paperworklabs/development/paperwork
vercel link --yes --project studio  # if not already linked
vercel env pull .env.production.local --environment production --yes
RENDER_API_KEY=$(grep "^RENDER_API_KEY" .env.production.local | cut -d'=' -f2 | tr -d '"')
```

### 2. Get Cloudflare Credentials (from Brain's Render env)

```bash
# First get RENDER_API_KEY as above, then:
curl -s -H "Authorization: Bearer $RENDER_API_KEY" \
  "https://api.render.com/v1/services/srv-d74f3cmuk2gs73a4013g/env-vars" | \
  jq -r '.[] | select(.envVar.key | test("CLOUDFLARE")) | "\(.envVar.key)=\(.envVar.value)"'
```

### 3. Fix DNS Records (Cloudflare)

```bash
# Get zone ID
curl -s -H "Authorization: Bearer $CF_TOKEN" \
  "https://api.cloudflare.com/client/v4/zones?name=example.com" | jq '.result[0].id'

# List DNS records
curl -s -H "Authorization: Bearer $CF_TOKEN" \
  "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" | \
  jq '.result[] | {id, type, name, content, proxied}'

# Delete a record
curl -s -X DELETE -H "Authorization: Bearer $CF_TOKEN" \
  "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$RECORD_ID"

# Create A record (DNS only, for Vercel)
curl -s -X POST -H "Authorization: Bearer $CF_TOKEN" -H "Content-Type: application/json" \
  "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
  -d '{"type":"A","name":"example.com","content":"76.76.21.21","proxied":false,"ttl":1}'

# Create/Update CNAME (DNS only, for Vercel)
curl -s -X POST -H "Authorization: Bearer $CF_TOKEN" -H "Content-Type: application/json" \
  "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
  -d '{"type":"CNAME","name":"www","content":"cname.vercel-dns.com","proxied":false,"ttl":1}'
```

### 4. Add Env Vars to Vercel Project

```bash
# Link to project first
cd /path/to/monorepo
vercel link --yes --project PROJECT_NAME

# Add env var
echo "VALUE" | vercel env add VAR_NAME production

# List env vars
vercel env ls

# Pull all env vars locally
vercel env pull .env.local --yes
```

### 5. Add Env Vars to Render Service

```bash
# Add or update env var
curl -s -X PUT -H "Authorization: Bearer $RENDER_API_KEY" \
  -H "Content-Type: application/json" \
  "https://api.render.com/v1/services/$SERVICE_ID/env-vars/VAR_NAME" \
  -d '{"value": "VAR_VALUE"}'

# List all env vars
curl -s -H "Authorization: Bearer $RENDER_API_KEY" \
  "https://api.render.com/v1/services/$SERVICE_ID/env-vars" | jq '.[].envVar.key'
```

### 6. Trigger Vercel Deployment

```bash
# Option A: Push a change to the app directory (preferred for monorepo)
echo "" >> apps/PROJECT/next.config.mjs
git add -A && git commit -m "chore: trigger redeploy" && git push

# Option B: Use Vercel CLI (requires proper linking)
vercel --prod
```

### 7. List Render Services

```bash
curl -s -H "Authorization: Bearer $RENDER_API_KEY" \
  "https://api.render.com/v1/services?limit=50" | \
  jq '.[] | .service | "\(.id) \(.name) \(.type)"'
```

## Vercel Projects Reference

| Project | Slug | Domain |
|---------|------|--------|
| Studio | studio | paperworklabs.com |
| AxiomFolio | axiomfolio | axiomfolio.com |
| FileFree | filefree | filefree.ai |
| LaunchFree | launchfree | launchfree.ai |
| Distill | distill | distill.tax |
| Trinkets | trinkets | trinkets.paperworklabs.com |

## Vercel Standard IPs

For pointing domains to Vercel:
- **A record**: `76.76.21.21`
- **CNAME**: `cname.vercel-dns.com`
- **Proxy**: Always set to **DNS only** (gray cloud in Cloudflare) — Vercel handles SSL

## Important Notes

1. **Never ask founder for dashboard clicks** — use APIs
2. **Vercel CLI is already authenticated** — just run commands
3. **Render API key lives in Studio's Vercel env** — pull it first
4. **Cloudflare creds live in Brain's Render env** — fetch via Render API
5. **Monorepo builds use ignoreCommand** — touch a file in the app dir to trigger builds
6. **DNS changes propagate in ~2 min** — use `dig domain.com +short` to verify

## Troubleshooting

### "Error 1000" on Cloudflare domain
DNS is pointing to Cloudflare proxy IPs instead of Vercel. Fix by:
1. Delete existing A records
2. Create new A record with `76.76.21.21`, proxied=false

### Vercel deployment not triggering
The monorepo's `ignoreCommand` detected no changes. Touch a file in the app directory.

### "Domain already assigned to another project"
```bash
vercel domains rm DOMAIN --yes
vercel link --yes --project TARGET_PROJECT
vercel domains add DOMAIN
```
