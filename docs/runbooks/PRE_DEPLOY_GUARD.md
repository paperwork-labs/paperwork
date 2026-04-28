---
title: Pre-deploy guard (Vercel quota + env vars + Clerk DNS)
last_reviewed: 2026-04-28
owner: infra-ops
status: active
domain: infra
doc_kind: runbook
summary: "Run scripts/check_pre_deploy.py before any production Vercel deploy so hobby quota, missing Clerk/API env vars, and Clerk↔Cloudflare DNS drift cannot take production offline."
tags: [vercel, brain, ci, deploy, quota, secrets, clerk, cloudflare, dns]
---

# Pre-deploy guard (Vercel quota + env vars + Clerk DNS)

Quota monitors in Brain **record** live usage (WS-29…31: [`apis/brain/app/schedulers/quota_monitors/vercel.py`](../../apis/brain/app/schedulers/quota_monitors/vercel.py) persists snapshots; [`GET /api/v1/admin/vercel-quota`](../../apis/brain/app/routers/admin.py) exposes the latest batch). This guard **enforces** a minimum deploy budget and required environment variables **before** you trigger a deploy (WS-34 / PR #365 hardens the “don’t deploy into a wall” class of failure).

## When to run it

Any time you are about to consume Vercel production deploy quota:

- GitHub Actions workflows that PATCH projects or call the deploy API (for example [.github/workflows/vercel-cutover-axiomfolio.yml](../../.github/workflows/vercel-cutover-axiomfolio.yml)).
- Local or agent-driven deploys (`vercel deploy --prod`, promote hooks, cutover scripts).
- Manual dashboard deploys — run the check first if you are unsure quota or env vars are healthy.

Typical failure modes this prevents:

- **Hobby deploy cap** — 100 production deploys per UTC day; exhausting it mid-session blocks all apps on the team until reset.
- **Missing Clerk (or API) env vars** — deploying without required keys yields HTTP 500 and `MIDDLEWARE_INVOCATION_FAILED` on edge/middleware.
- **Clerk ↔ Cloudflare DNS drift** — Cloudflare zone migrations or bad imports can drop `*.clerk.services` CNAMEs while Vercel env vars still look fine (2026-04-28 incident — [CLERK_DNS_INCIDENT_2026-04-28.md](CLERK_DNS_INCIDENT_2026-04-28.md)).

Recovery patterns for Brain-on-Render boot issues remain in [Brain deploy recovery](BRAIN_DEPLOY_RECOVERY.md); this runbook is the **runtime Vercel** sibling.

## Requirements

| Variable | Purpose |
| --- | --- |
| `BRAIN_ADMIN_TOKEN` | Same secret as Brain `BRAIN_API_SECRET` (sent as header `X-Brain-Secret` to `/api/v1/admin/*`). |
| `VERCEL_API_TOKEN` | Vercel token with access to list project env vars. |
| `CLERK_SECRET_KEY` | Required when `--project` is `studio`, `axiomfolio`, or `filefree` (unless `--skip-clerk-dns`). Same secret Clerk exposes as the Backend API key. |
| `CLOUDFLARE_API_TOKEN` | Required for those projects (DNS:Edit on the work account). Legacy alias: `CF_TOKEN`. |
| `BRAIN_BASE_URL` | Optional. Defaults to `https://brain-api.onrender.com`. |

Install PyYAML once (`pip install pyyaml`); the script loads [`apis/brain/data/required_env_vars.yaml`](../../apis/brain/data/required_env_vars.yaml). The Clerk DNS step shells out to [`scripts/reconcile_clerk_dns.py`](../../scripts/reconcile_clerk_dns.py) (`stdlib` only).

## Command

From the repo root:

```bash
python scripts/check_pre_deploy.py --project <vercel-slug> --target production \
  [--brain-base-url "$BRAIN_BASE_URL"] [--quota-threshold 5] \
  [--skip-quota] [--skip-env-vars] [--skip-clerk-dns] [--require-all-checks]
```

Project slugs match [`scripts/vercel-projects.json`](../../scripts/vercel-projects.json). Resolve `prj_…` overrides via `VERCEL_PROJECT_ID_<SLUG>` (hyphens to underscores, uppercase) when a slug is still `TBD_CREATE_BEFORE_MERGE` in JSON.

## Adding a project to the manifest

1. Edit [`apis/brain/data/required_env_vars.yaml`](../../apis/brain/data/required_env_vars.yaml) (top-of-file comment reminds you).
2. List required env var **names** per deployment target (`production`, `preview`, …) — values are **not** stored in git.
3. Ensure `scripts/vercel-projects.json` has a real `projectId` or set `VERCEL_PROJECT_ID_<SLUG>` in CI.

## Emergency bypass

Use only when you intentionally accept risk (incident hotfix, quota logic bug, Brain outage):

```bash
python scripts/check_pre_deploy.py --project axiomfolio --target production \
  --skip-quota --skip-env-vars --skip-clerk-dns
```

The script prints **`WARNING: PRE_DEPLOY_GUARD_BYPASS_USED`** and a **`::warning::`** line for Actions summaries.

- **`--require-all-checks`** — CI or automation should pass this when you want bypass attempts to **fail** (exit code 5) instead of succeeding. Accidental `--skip-*` in a guarded job becomes loud.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Success |
| 1 | Unexpected error (HTTP/JSON) |
| 2 | Quota below threshold |
| 3 | Required env var missing for target |
| 4 | Missing `BRAIN_ADMIN_TOKEN` / `VERCEL_API_TOKEN` / `CLERK_SECRET_KEY`+`CLOUDFLARE_API_TOKEN` when a step needs them, unresolved project id, or PyYAML missing |
| 5 | Bypass flags used together with `--require-all-checks` |
| 6 | Clerk DNS drift — `scripts/reconcile_clerk_dns.py --check-only` exited 2 |

## GitHub Actions

Workflows that deploy should set `BRAIN_ADMIN_TOKEN` from repository secrets and run the script **before** cutover or deploy steps. For **`studio`**, **`axiomfolio`**, and **`filefree`**, also configure **`CLERK_SECRET_KEY`** and **`CLOUDFLARE_API_TOKEN`** (see [.github/workflows/vercel-cutover-axiomfolio.yml](../../.github/workflows/vercel-cutover-axiomfolio.yml)). If a secret is missing, add it (same `BRAIN_ADMIN_TOKEN` value as production `BRAIN_API_SECRET` on Render).

## See also

- [Brain deploy recovery](BRAIN_DEPLOY_RECOVERY.md) — merge-time and Render boot guards.
- [`scripts/check_pre_deploy.py`](../../scripts/check_pre_deploy.py) — implementation.
- [`scripts/reconcile_clerk_dns.py`](../../scripts/reconcile_clerk_dns.py) — Clerk + Cloudflare DNS reconcile / check-only.
- [Clerk DNS incident (2026-04-28)](CLERK_DNS_INCIDENT_2026-04-28.md) — post-mortem and temp redirect removal criteria.
