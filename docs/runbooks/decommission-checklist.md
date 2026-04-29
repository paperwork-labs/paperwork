# Domain / App Decommission Checklist

**Owner:** ops-engineer  
**Last updated:** 2026-04-28  
**Source of truth for completed decommissions:** `apis/brain/data/decommissions.json`  
**Admin endpoint:** `GET /api/v1/admin/decommissions`

---

## Overview

This runbook covers the safe, auditable removal of a domain, Vercel project, or app from the Paperwork Labs stack. It is generic and applies to any decommission. For app-specific notes see the corresponding script in `scripts/decommission/`.

**Key principle:** we archive — never delete — to preserve deployment history and allow rollbacks.

---

## Pre-flight checklist

These steps must be completed before any infrastructure changes.

### 1. Analytics — last 30 days

- [ ] Open PostHog (or equivalent) and filter to the domain being decommissioned
- [ ] Confirm page views, unique users, and API hits for the last 30 days
- [ ] If **any non-bot traffic** → stop here and document who is using it; escalate to founder before proceeding
- [ ] Record the traffic check date in `decommissions.json` → `last_30d_traffic_check`

### 2. External links / integrations

- [ ] Search the monorepo for the domain string (`grep -r "apps.paperworklabs.com" .`)
- [ ] Search Slack for the domain — any active bookmarks or integrations?
- [ ] Check n8n for any webhooks pointing to the domain (`n8n.paperworklabs.com/workflow/*`)
- [ ] Check Clerk dashboard for any redirect URIs pointing to the domain

### 3. Dependencies

- [ ] Does any other service call this app's API? (check `apis/brain/data/app_registry.json` → `depends_on_services`)
- [ ] Is the domain used in any email templates, marketing links, or public docs?

### 4. Founder sign-off

- [ ] All pre-flight checks pass
- [ ] Founder confirms decommission is safe
- [ ] Update `decommissions.json` → `status: "scheduled"`

---

## Decommission steps

### Step 1: Cloudflare — remove DNS records

```bash
# List DNS records for the zone
curl -s "https://api.cloudflare.com/client/v4/zones/<ZONE_ID>/dns_records?name=<subdomain>" \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" | jq '.result[] | {id, name, type, content}'

# Delete each record
curl -s -X DELETE \
  "https://api.cloudflare.com/client/v4/zones/<ZONE_ID>/dns_records/<RECORD_ID>" \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN"
```

Verify: `dig +short <subdomain>.<domain>` should return empty.

### Step 2: Vercel — archive the project (do NOT delete)

Archiving preserves deployment history, preview URLs, and environment variables for audit.

```bash
# Via Vercel API (preferred — preserves history)
curl -s -X PATCH \
  "https://api.vercel.com/v9/projects/<PROJECT_ID_OR_NAME>?teamId=<TEAM_ID>" \
  -H "Authorization: Bearer $VERCEL_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"live": false}'

# Or via Dashboard: Project → Settings → Advanced → Archive Project
```

**Do NOT use "Delete Project"** — this permanently removes deployment history.

### Step 3: Clerk — revoke dedicated instance (if applicable)

Only if the app had its own dedicated Clerk instance (most apps share the main instance).

- [ ] Log in to [Clerk Dashboard](https://dashboard.clerk.com)
- [ ] Select the instance for the app
- [ ] Settings → Danger Zone → Delete Instance
- [ ] Remove `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` + `CLERK_SECRET_KEY` from vault

If the app used the shared Clerk instance, skip this step.

### Step 4: Update app_registry.json

```bash
# Regenerate from current monorepo state
cd /path/to/monorepo && pwl registry-build
```

Or mark the entry manually if the directory still exists (for archive):
```json
{
  "deploy_target": "decommissioned",
  "owner_persona": "unassigned"
}
```

### Step 5: Record in decommissions.json

```json
{
  "id": "<entry-id>",
  "decommissioned_at": "2026-04-28T00:00:00Z",
  "decommissioned_by": "<github-login>",
  "status": "done"
}
```

### Step 6: (Optional) Archive the source directory

If the app's code lives in `apps/<name>/` and you want to keep the source for reference:

```bash
git mv apps/<name> apps/_archived/<name>
git commit -m "chore: archive apps/<name> (decommissioned)"
```

Alternatively, leave the directory in place and just stop deploying it.

---

## Post-decommission verification

- [ ] `dig +short <subdomain>.<domain>` returns empty
- [ ] `curl -I https://<subdomain>.<domain>` returns 404 or NXDOMAIN (not 200)
- [ ] Vercel project shows "Archived" badge
- [ ] `apis/brain/data/decommissions.json` entry has `status: "done"` and `decommissioned_at` set
- [ ] Brain admin endpoint confirms: `GET /api/v1/admin/decommissions?status=done`

---

## Rollback

If decommission was premature:

1. **DNS**: Re-add the DNS record in Cloudflare
2. **Vercel**: Unarchive the project via Dashboard → Settings → Advanced → Unarchive
3. **Clerk**: Create new instance if needed (re-issue keys)
4. Update `decommissions.json` → `status: "proposed"` with rollback note in `notes`

---

## apps.paperworklabs.com — specific notes

**Current state:** `apps.paperworklabs.com` was a stub Next.js app (`apps/accounts/`) intended
to host a custom Clerk Account Portal (user settings, SSO management). Clerk now provides
this natively via hosted pages at `accounts.<domain>`. The app was never fully built
(248 LoC, conformance score 0.33, no active test suite, zero meaningful traffic).

**Decommission script:** `scripts/decommission/apps-paperworklabs-com.sh`

**Blockers (as of 2026-04-28):**
- Verify zero traffic in PostHog before running the script
- Confirm no redirect URIs in Clerk dashboard point to `apps.paperworklabs.com`

See `apis/brain/data/decommissions.json` entry `apps-paperworklabs-com` for live status.
