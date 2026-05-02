---
title: Clerk + Cloudflare DNS incident (2026-04-28)
last_reviewed: 2026-05-02
owner: infra-ops
status: active
doc_kind: runbook
summary: "Post-mortem: Cloudflare zone migration dropped Clerk CNAMEs; Studio sign-in broke; recovery, temporary redirect, and durable guards (reconcile script + pre-deploy + Brain scheduler)."
tags: [clerk, cloudflare, dns, studio, auth, incident]
---

# Clerk + Cloudflare DNS incident (2026-04-28)

> **Category**: incident
> **Owner**: @infra-ops
> **Last verified**: 2026-05-02
> **Status**: active

**TL;DR:** Post-mortem for Studio sign-in breaking after Cloudflare migration, how DNS was repaired, temporary redirect rules, and the guardrails (`reconcile_clerk_dns`, pre-deploy) that prevent repeats.

## Executive summary

On **2026-04-28 ~20:45 UTC**, Studio’s Clerk sign-in flow broke after the **Cloudflare account migration** (personal → work account) for `paperworklabs.com`. Cloudflare’s **auto-import** recreated many DNS rows but **silently omitted** several CNAMEs pointing at Clerk’s `*.clerk.services` targets and two ops records (`brain.paperworklabs.com`, `social.paperworklabs.com`). DNS was repaired via the Cloudflare API, a **temporary** Single Redirect was added for `accounts.paperworklabs.com`, and this repository now ships **automation + runbooks** so the same class of failure is caught before the next deploy.

## Timeline (UTC)

| Time (approx.) | Event |
|---|---|
| Earlier 2026-04-28 | Founder completes Cloudflare **WS-33** migration; production zones land on the work account. |
| ~20:11–20:24 | Sister zones (`filefree.ai`, `launchfree.ai`, `distill.tax`, etc.) activate on the work account; BIND-style import largely preserves records. |
| ~20:45 | **Studio sign-in degraded / broken** — Clerk Frontend API + Account Portal hostnames no longer resolve to Clerk edges as intended. |
| Same session | Operator restores missing rows via one-off Cloudflare API script (`/tmp/fix_clerk_dns.py` pattern — see `scripts/reconcile_clerk_dns.py` in-tree). |
| Discovery | `accounts.paperworklabs.com` **403** with `cf-mitigated=challenge` — Clerk **Cloudflare for SaaS** custom hostname state is **per Cloudflare zone**; zone migration invalidates prior hostname registration until Clerk re-validates. |
| Mitigation | **Temporary** Cloudflare **Single Redirect**: `hostname == accounts.paperworklabs.com` → **302** `https://paperworklabs.com/sign-in` (`preserve_query_string=true`). Ruleset id: `44f435a0b71f4596b6098cb579bef31c`. Studio sign-in works again via the main app URL. |
| Follow-up | Vercel rebuild of Studio with `NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in` was **blocked** by Hobby deploy quota until **2026-04-29 ~21:39 UTC**; Clerk hostname re-validation may complete independently. |

## Root cause

1. **Cloudflare auto-scan / import gaps**  
   Auto-import cannot reliably discover records for names the importer **does not yet own** or that recursive resolvers never see the same way production will. Apex / **CNAME-flattened** SaaS targets (`*.clerk.services`, `*.onrender.com`, etc.) are easy to miss compared to obvious A/AAAA rows.

2. **Clerk custom hostname + zone migration**  
   Clerk’s **Cloudflare for SaaS** hostname registration is tied to the **Cloudflare zone** that served DNS when the hostname was added. Moving the zone to a new account **does not** automatically re-provision identical SaaS edge state; `accounts.paperworklabs.com` briefly pointed at the wrong target (`cname.vercel-dns.com` from the superseded “host Account Portal on Vercel” experiment) and then returned **403** until DNS + Clerk validation realigned.

3. **Product / workstream misunderstanding (WS-15)**  
   The `apps/accounts/` Next.js scaffold assumed we needed to **self-host** the Clerk Account Portal. Clerk **natively** serves the Account Portal at `accounts.clerk.services`; the custom domain is a **CNAME to Clerk**, not a requirement for a dedicated Vercel app. WS-15 is **cancelled**; decommission of the redundant Vercel project is **WS-36**.

## Detection gap

- **Pre-deploy guard** (WS-34) validated **Vercel env vars** and **deploy quota**, not **live DNS** against Clerk’s `cname_targets`.
- There was **no synthetic monitor** for “does `clerk.paperworklabs.com` CNAME resolve to `frontend-api.clerk.services`?”

## Fixes shipped (this change set)

| Item | Description |
|---|---|
| `scripts/reconcile_clerk_dns.py` | Idempotent reconcile: reads Clerk `GET /v1/domains` → `cname_targets` (`required: true`), matches Cloudflare per zone, creates/updates drift; includes **ops** rows for `brain.*` + `social.*` on `paperworklabs.com` unless `--no-ops-dns`. |
| `scripts/check_pre_deploy.py` | For **`studio`**, **`axiomfolio`**, **`filefree`**: runs `reconcile_clerk_dns.py --check-only` unless `--skip-clerk-dns`. Exit **6** on drift. |
| Brain APScheduler | `clerk_dns_reconcile_watch` runs **every 30 minutes**, same check-only path; **Slack** alert to `#engineering` on failure (via `slack_outbound`), loud logs if Slack is not configured. |
| Docker image | `apis/brain/Dockerfile` copies `scripts/reconcile_clerk_dns.py` into `/app/scripts/` so Render can execute the job. |
| Docs | This post-mortem; `cloudflare-ownership.md` checklist; `VERCEL_PROJECTS.md` de-emphasises redundant `accounts` project (**WS-36**). |

## Temporary measures still in place (do not remove silently)

- **Cloudflare Single Redirect** for `accounts.paperworklabs.com` → `https://paperworklabs.com/sign-in` (302, preserve query).  
  **Remove only after** Clerk’s custom hostname for `accounts.paperworklabs.com` is healthy again (see validation below).

## Validation — what “good” looks like

1. **Run reconcile in check-only mode** (CI + laptops with secrets):

   ```bash
   export CLERK_SECRET_KEY=…           # or: ./scripts/vault-get.sh CLERK_SECRET_KEY
   export CLOUDFLARE_API_TOKEN=…      # or CF_TOKEN; or vault-get
   python3 scripts/reconcile_clerk_dns.py --check-only
   ```

   Exit **0** and a table full of **`OK`** rows.

2. **Resolver sanity** (examples):

   ```bash
   dig +short CNAME clerk.paperworklabs.com
   dig +short CNAME accounts.paperworklabs.com
   ```

   Expect Clerk targets from the live Clerk dashboard / API, not `cname.vercel-dns.com` for production Account Portal.

3. **HTTP** — after Clerk re-validates the custom hostname, **remove the temp redirect first in a maintenance window**, then:

   ```bash
   curl -sSI https://accounts.paperworklabs.com/sign-in | head -n 15
   ```

   Success: **200** or a **302** whose **Location** is clearly **Clerk-owned** (not `cf-mitigated: challenge` / **403** from Cloudflare edge without Clerk).

## When to remove the temporary redirect

Remove the Single Redirect **only when**:

- `curl -sSI https://accounts.paperworklabs.com/sign-in` shows **200** or an app **302** from **Clerk** (not Cloudflare challenge), **and**
- Clerk dashboard shows the **custom hostname** for `accounts.paperworklabs.com` as **active/verified** on the **work-account** zone.

Until then, the redirect is **load-bearing** for user sign-in.

## Related workstreams

- **WS-36** — Decommission `apps/accounts` and the redundant Vercel `accounts` project (separate PR after this lands).
- **WS-37** — Clerk DNS auto-reconcile + monitoring (this PR).

## References

- `scripts/reconcile_clerk_dns.py` — automation entry point.
- `docs/runbooks/cloudflare-ownership.md` — post-migration DNS checklist.
- `docs/runbooks/pre-deploy-guard.md` — pre-deploy guard behaviour and exit codes.
- `docs/infra/VERCEL_PROJECTS.md` — Vercel project inventory (accounts row slated for removal).
