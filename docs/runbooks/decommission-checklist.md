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

---

## Slack + n8n Full Decommission — 2026-04-29 (WS-69 PR J)

**PR:** `feat(WS-69 PR J): n8n + Slack full decommission + Gmail SMTP fallback`
**Branch:** `feat/ws-69-pr-j-decommission`
**Date:** 2026-04-29
**Author:** Brain AI (WS-69 implementation)

### What was removed

| System | Removed artefacts |
|--------|------------------|
| **Slack** | `slack_outbound.py`, `slack_router.py` (routing shim), `slack_routing.py` (schema), `slack_morning_digest.py`, `test_slack_outbound.py`, `test_slack_router.py`, `scripts/slack-persona.sh` |
| **n8n** | `_n8n_slack_format.py`, `infra/hetzner/workflows/` directory, n8n scripts (`deploy-n8n-workflows.sh`, `n8n-activate-workflows.sh`, `snapshot_n8n_graphs.py`, `fix-n8n-env.sh`), `N8N_URL` + `N8N_API_KEY` from `render.yaml` + `config.py` |
| **Studio** | `N8nMirrorStatusClient.tsx`, Slack `#brain-status` quick-link in admin footer |

### What was added

- `apis/brain/app/services/email_outbound.py` — Gmail SMTP fallback for `urgency∈{high,critical}` + `needs_founder_action=True` conversations
- `apis/brain/scripts/conversations-persona.sh` — replacement for `scripts/slack-persona.sh`
- `apis/brain/tests/test_email_outbound.py` — full SMTP mock test coverage

### Scheduler migrations (Slack → Brain Conversations)

All ~14 schedulers that previously called `slack_outbound.post_message(...)` now call
`create_conversation(ConversationCreate(...))` with appropriate `tags`, `urgency`, `persona`,
and `needs_founder_action`.

### Day-0 founder actions required

1. **Create Gmail app password** — Google Account → Security → 2-Step Verification → App passwords
2. **Set Brain env vars on Render:**
   - `GMAIL_USERNAME` — the Gmail address (e.g. `brain@paperworklabs.com`)
   - `GMAIL_APP_PASSWORD` — 16-char app password
   - `FOUNDER_FALLBACK_EMAIL` — delivery address
3. Until vars are set, Brain returns `EmailConfigError` (HTTP 503) on high/critical conversation creates. Conversation is still persisted — only the email notification fails.

### Slack workspace billing

Slack workspace deletion is a **founder-side billing action** and is NOT included in this PR.
Decommission the workspace separately via Slack → Settings & Permissions → Billing once you
confirm zero active integrations.

### Hetzner VPS shutdown

Hetzner instance shutdown is a **separate runbook entry** (infra-level, not in this PR diff).
The n8n service on Hetzner can be stopped independently once the workspace billing step is done.
