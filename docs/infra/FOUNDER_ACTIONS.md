---
owner: infra-ops
last_reviewed: 2026-04-27
doc_kind: runbook
domain: infra
status: active
summary: "Single-source list of one-time blockers that require founder credentials (Vercel, Render, GitHub, Clerk, DNS, Chromatic). Move completed items to Resolved with date and PR."
tags: [infra, founder, operations]
---

# Founder-Only Actions

Single-source list of one-time blockers that require founder credentials. Once an item lands, move it to the **Resolved** section at the bottom with a date and PR link.

**Rules:** no secrets in this file — point to 1Password, Vercel/Render/GitHub/Clerk dashboards, or the secrets vault. If live state is unknown, the item is marked **`[VERIFY]`** with a concrete check.

## 2026-04-28 — AxiomFolio Vercel cutover (in-place; mostly done)

The canonical `axiomfolio` Vercel project (`prj_7L9N3FpOFRsc12tMfKKWa8q2lDLE`) — which already owns `axiomfolio.com` + `www.axiomfolio.com` (verified) — was originally framework=vite. We flipped it in-place to Next.js rather than migrate domains to a separate project. Step A (PATCH framework + root + install + output) ran successfully on 2026-04-28 via `scripts/vercel-cutover-axiomfolio.mjs --apply`.

The earlier stop-gap `axiomfolio-next` project was never used and was deleted via the Vercel API on 2026-04-28. There is now exactly one canonical AxiomFolio Vercel project: `axiomfolio`.

**Remaining founder action (one click, after Vercel hobby quota reset ≈ 2026-04-28T21:13Z):**

- Re-run the cutover deploy: GitHub Actions → **"Vercel cutover — axiomfolio"** → Run workflow. This deploys `main` HEAD against the canonical project. Step A is idempotent (skips PATCH if framework already nextjs).
- Or via CLI: `gh workflow run vercel-cutover-axiomfolio.yml`.

After the deploy lands READY, `axiomfolio.com` + `www.axiomfolio.com` start serving the Next.js app from `main`. Confirm at the Vercel dashboard → `axiomfolio` → Domains (the "Invalid Configuration" warning resolves once a successful production deployment exists).

**DNS at Cloudflare** (the domain registrar is Spaceship, but DNS is on Cloudflare): keep the existing records pointing to Vercel — apex `A` to `76.76.21.21`, `www` `CNAME` to `cname.vercel-dns.com`, both proxy=DNS only (gray cloud). No nameserver change at Spaceship is required.

Tracked in: `chore/axiomfolio-vercel-cutover` ([#306](https://github.com/paperwork-labs/paperwork/pull/306)) and the cutover workflow PR.

## Pending — Critical (blocks production)

### 1. F-1 — AxiomFolio Render services repoint to monorepo
- **Why this matters:** `axiomfolio-api`, workers, and static frontend still deploy from `paperwork-labs/axiomfolio`; `apis/axiomfolio/` changes on `main` do not ship to production.
- **Where:** [Render Blueprints + dashboard](https://dashboard.render.com) — Path B in runbook.
- **Steps:**
  1. Confirm `main` is green: `gh run list --branch main --limit 3`.
  2. Follow **Path B** in `docs/infra/RENDER_REPOINT.md` (New Blueprint → `paperwork-labs/paperwork` → associate existing `axiomfolio-*` services).
  3. Wait for deploys; run health checks from the runbook **Verification** section.
  4. Tick F-1 in `docs/infra/RENDER_INVENTORY.md` when all `repo` fields show the monorepo.
  5. After 24h green, archive the old repo per runbook (optional but recommended).
- **Verification:** `curl` health URLs in `RENDER_REPOINT.md`; Studio → **Admin → Infrastructure** shows services healthy; Render UI shows `paperwork-labs/paperwork` for all four services.
- **Source:** [RENDER_REPOINT Path B](docs/infra/RENDER_REPOINT.md), [RENDER_INVENTORY F-1](docs/infra/RENDER_INVENTORY.md); PRs touching medallion / port batch
- **ETA:** ~30–45 min

### 2. `design.paperworklabs.com` — Vercel project + domain + auto-promote matrix
- **Why this matters:** The design Storybook canvas does not have a first-class production host until the Vercel project exists, the GitHub promote workflow has a real project id, and DNS points at Vercel.
- **Where:** [Vercel — Paperwork Labs team](https://vercel.com/paperwork-labs), Cloudflare DNS for `paperworklabs.com` zone, `.github/workflows/vercel-promote-on-merge.yaml`.
- **Steps:**
  1. Vercel → New Project → import `paperwork-labs/paperwork`, root `apps/design`, production branch `main` (add `vercel.json` in the app root after the project is created, if not generated automatically).
  2. Copy Project ID (`prj_…`) and replace the `TBD_CREATE_BEFORE_MERGE` placeholder for the `design` row in `vercel-promote-on-merge.yaml` and the tracked table in `docs/infra/VERCEL_AUTO_PROMOTE.md`.
  3. Vercel project → Domains → add `design.paperworklabs.com`.
  4. In Cloudflare, add the CNAME Vercel shows; **disable proxy** (DNS only) for clean TLS issuance.
- **Verification:** `https://design.paperworklabs.com` serves Storybook static build; merge to `main` updates production (or PR comment on promote workflow shows success).
- **Source:** PR #256
- **ETA:** ~25 min

## Pending — Operational (blocks automation)

### 1. GitHub `CHROMATIC_PROJECT_TOKEN` + Chromatic project wiring
- **Why this matters:** Visual regression CI for `apps/design` / shared packages is a no-op until the token exists and `chromatic.config.json` has a real `projectId`.
- **Where:** [Chromatic](https://www.chromatic.com) (GitHub sign-in) → [GitHub repo → Settings → Secrets → Actions](https://github.com/paperwork-labs/paperwork/settings/secrets/actions)
- **Steps:**
  1. Create Chromatic project for this repo’s Storybook; copy project token and id.
  2. Add repo secret `CHROMATIC_PROJECT_TOKEN`.
  3. Set `projectId` in `apps/design/chromatic.config.json` to match Chromatic.
  4. Push a change under `apps/design/**` or `packages/**/src/**` (or run Chromatic locally) to baseline.
- **Verification:** Chromatic check passes on a PR; dashboard shows a build/baseline.
- **Source:** PR #255 (in-repo Chromatic VRT runbook under `docs/infra/` when that runbook ships; path not fixed yet)
- **ETA:** ~20 min

### 2. `GITHUB_WEBHOOK_SECRET` on `brain-api` (Render) + GitHub repo webhook
- **Why this matters:** Brain’s `POST` webhook handler HMAC-verifies with `GITHUB_WEBHOOK_SECRET`. An unset or mismatched value breaks Dependabot/PR automation from GitHub. The repo must deliver webhooks to Brain’s URL with the same secret.
- **Where:** [Render `brain-api` environment](https://dashboard.render.com), [GitHub repo → Settings → Webhooks](https://github.com/paperwork-labs/paperwork/settings/hooks) (or org-level; follow internal convention).
- **Steps:**
  1. **Generate** a strong shared secret; store in 1Password / vault.
  2. Set `GITHUB_WEBHOOK_SECRET` on Render `brain-api` (declared in `render.yaml` with `sync: false` — value must be pasted in dashboard). **`[VERIFY]`** whether production already has a value; compare with GitHub hook configuration.
  3. Ensure GitHub sends `pull_request` (and other required events per `docs/DEPENDABOT.md`) to `https://brain.paperworklabs.com/api/v1/webhooks/github` (path prefix may differ — confirm in `apis/brain/app/routers/webhooks.py`).
  4. Redeliver a test event from GitHub and confirm Brain logs 2xx.
- **Verification:** GitHub “Recent Deliveries” green; `POST` does not 401/403; Brain automation processes a test Dependabot or PR event.
- **Source:** [DEPENDABOT.md](docs/DEPENDABOT.md) (webhook flow), [RENDER_INVENTORY F-5](docs/infra/RENDER_INVENTORY.md)
- **ETA:** ~15 min

### 3. Render `brain-api`: use `VERCEL_API_TOKEN` only (drop legacy `VERCEL_TOKEN` row if present)
- **Why this matters:** Brain and automation read only `VERCEL_API_TOKEN`. A second env row under the old name invites confusion and rotation mistakes.
- **Where:** Render `brain-api` → Environment; see F-3 in `docs/infra/RENDER_INVENTORY.md`.
- **Steps:**
  1. Confirm only `VERCEL_API_TOKEN` is required in code and workflows (`VERCEL_AUTO_PROMOTE.md`).
  2. **`[VERIFY]`** If the dashboard still has `VERCEL_TOKEN`, rename that row to `VERCEL_API_TOKEN` (same value) or remove the duplicate after confirming nothing else references the old name.
- **Verification:** Brain infra tools / Studio infra probes still work; no env errors in logs.
- **Source:** Track I2, F-3 in `docs/infra/RENDER_INVENTORY.md`
- **ETA:** ~5 min (after verify)

### 4. n8n shadow workflows — disable originals after Brain cutover
- **Why this matters:** Retired n8n JSONs were moved to `infra/hetzner/workflows/retired/`; if the live n8n instance still runs them, you get duplicate Slack posts and duplicate triggers versus Brain.
- **Where:** [n8n editor](https://n8n.paperworklabs.com) — Hetzner-hosted workflows.
- **Steps:**
  1. For each row in `infra/hetzner/workflows/retired/RETIRED.md`, confirm the corresponding workflow is **inactive** in n8n.
  2. For `brain-pr-summary`, consider removing a GitHub → n8n webhook if it only supported that flow (see PR #216 body).
- **Verification:** No duplicate posts in target Slack channels; n8n execution history clean for those flows.
- **Source:** PR #216, `docs/infra/BRAIN_SCHEDULER.md`
- **ETA:** ~20 min

### 5. Render (`brain-api`) env hygiene after n8n → Brain cron cutover
- **Why this matters:** Ex-n8n crons run on Brain when `BRAIN_SCHEDULER_ENABLED=true`. Remove stale `BRAIN_OWNS_DAILY_BRIEFING`-style env vars from Render so operators are not misled (they are ignored by code).
- **Where:** Render `brain-api` environment variables; full matrix in `docs/infra/BRAIN_SCHEDULER.md`.
- **Steps:**
  1. Ex-n8n crons are **always on** when `BRAIN_SCHEDULER_ENABLED=true` (cutover flags retired). Optional gates remain for sprint auto-logger / sprint planner / agent sprint scheduler / PR triage — see [BRAIN_SCHEDULER.md](BRAIN_SCHEDULER.md).
  2. Watch `#engineering` / `#engineering-cron-shadow` and Brain logs; confirm no duplicate user-facing posts.
  3. Remove obsolete `BRAIN_OWNS_DAILY_BRIEFING` (and siblings) from Render env if still present — they are ignored.
  4. **Optional (operational):** `BRAIN_OWNS_SPRINT_AUTO_LOGGER=true` only after GitHub bot-PR path is accepted.
- **Verification:** `GET /internal/schedulers` or `SELECT id FROM apscheduler_jobs`; optional `GET /api/v1/admin/scheduler/n8n-mirror/status` returns `retired: true`.
- **Source:** PR #245, `docs/infra/BRAIN_SCHEDULER.md`
- **ETA:** ~60+ min (spread across days; not one sitting)

### 6. Vercel auto-promote matrix placeholders + stale production recovery — `[VERIFY]`
- **Why this matters:** `.github/workflows/vercel-promote-on-merge.yaml` includes rows with `project_id: TBD_CREATE_BEFORE_MERGE` (`design`, `accounts`). Those jobs intentionally skip until real `prj_…` ids exist. Separately, if **no** READY deployment exists for the merge commit on a real project, **promote cannot fix production** (alias-only); CI must fail loudly — see `docs/infra/VERCEL_AUTO_PROMOTE.md`.
- **Where:** [Vercel — Paperwork Labs](https://vercel.com/paperwork-labs); workflow matrix; optional `gh secret list` for `VERCEL_API_TOKEN`.
- **Steps:**
  1. For each placeholder row: create or locate the Vercel project, copy **Project ID** from Settings → General, replace `TBD_CREATE_BEFORE_MERGE` in the workflow (do not invent ids).
  2. If production is stale and `vercel deploy` / redeploy returns **402** `api-deployments-free-per-day`, the team hit the **Hobby daily deployment cap** — wait for reset, upgrade, or use the dashboard to **promote** an existing READY deployment that already matches `main` (no new build).
  3. If CLI reports a doubled root path (e.g. `apps/studio/apps/studio`), fix **Root Directory** under the Vercel project’s General settings (often one `apps/<name>` segment, not nested twice).
- **Verification:** Merge a PR that touches shared paths; promote workflow comments or promotes; `vercel api`/dashboard shows production `githubCommitSha` matching `git rev-parse origin/main` for studio, launchfree, filefree, distill.
- **Source:** PR #267, `docs/infra/VERCEL_AUTO_PROMOTE.md`
- **ETA:** ~15–30 min per project + any plan/cap wait

## Pending — Branding / Polish (cosmetic)

### 1. Clerk “Powered by Clerk” / Pro branding on dev — `[VERIFY]`
- **Why this matters:** On Hobby, some Clerk surfaces show vendor branding; product Standard is to minimize Clerk chrome for customer-facing UIs. PR #234 shipped shared `@paperwork-labs/auth-clerk` appearance defaults; long-term, Clerk Pro or Dashboard settings may be required for full control.
- **Where:** [Clerk Dashboard](https://dashboard.clerk.com) for each app instance; per-app Vercel env for appearance-related overrides if any.
- **Steps:** **`[VERIFY]`** current state across dev/staging after PR #234; align with #234 and `packages/auth` docs before changing plans or CSS workarounds.
- **Verification:** Sign-in on each public app: branding matches brand guidelines; no unexpected Clerk footer.
- **Source:** PR #234, [CLERK_STUDIO.md](docs/infra/CLERK_STUDIO.md) (sibling `docs/infra/CLERK_*.md` runbooks)
- **ETA:** ~30 min (research) + any Clerk plan upgrade (business decision)

### 2. DNS + Dashboard for Clerk production (`paperworklabs.com` / `accounts.paperworklabs.com`) — `[VERIFY]`
- **Why this matters:** Clerk production for **`paperworklabs.com`** needs the **five CNAMEs** (Frontend API, Account portal, mail, DKIM) verified in the Dashboard before hosted auth flows are fully trusted. Satellite domains (other brands) still follow `CLERK_SATELLITE_TOPOLOGY.md` when you enable them. Embedded-only auth in individual apps (PR #210) **reduced** reliance on `accounts.*` for basic login in some surfaces; **Track H4** for the root zone is **DNS + verification** — see **[`CLERK_DNS_SPACESHIP.md`](docs/infra/CLERK_DNS_SPACESHIP.md)** (Clerk auto-hosts the Account Portal at `accounts.paperworklabs.com`; no custom `apps/accounts/` deploy required for that portal). ~~Former Track H4 (`apps/accounts` micro-app)~~ — **superseded** by Clerk-hosted Account Portal per [`docs/KNOWLEDGE.md`](../KNOWLEDGE.md) §D91.
- **Where:** **Spaceship** DNS for `paperworklabs.com` (not Cloudflare/Vercel DNS for this zone); [Clerk Dashboard](https://dashboard.clerk.com) → **Configure** → **Developers** → **Domains**.
- **Steps:** Open **[`CLERK_DNS_SPACESHIP.md`](docs/infra/CLERK_DNS_SPACESHIP.md)** — paste the five CNAMEs, wait ~5 min, then **Verify configuration** in Clerk. For satellite rollouts across **other** apex domains, follow [`CLERK_SATELLITE_TOPOLOGY.md`](docs/infra/CLERK_SATELLITE_TOPOLOGY.md) (Clerk shows live record values per domain — do not copy stale placeholders).
- **Verification:** `dig` one-liner in `CLERK_DNS_SPACESHIP.md`; all five **Verified** in Dashboard; optional end-to-end sign-in across a pilot satellite when satellites are enabled.
- **Source:** [`CLERK_DNS_SPACESHIP.md`](docs/infra/CLERK_DNS_SPACESHIP.md), [`CLERK_SATELLITE_TOPOLOGY.md`](docs/infra/CLERK_SATELLITE_TOPOLOGY.md), PR #219, PR #210
- **ETA:** ~15 min (DNS paste) + propagation; satellite program add 1–2 h when executed

## Future / strategy — AxiomFolio Vite on Render vs Vercel (Next) — `[VERIFY]`

- **Note:** F-1 addresses **today’s** monorepo deploy gap on Render. A separate initiative (`docs/axiomfolio/plans/NEXTJS_MIGRATION_2026Q3.md`) describes moving the public AxiomFolio app toward Vercel/Next and decommissioning the Render static site **later**. Do not conflate with F-1; track founder actions there when the plan is active.

## Resolved

- 2026-04-25: F-6 — `brain-api` Docker build context directory cleared; monorepo images build and deploy. Source: [RENDER_INVENTORY F-6](docs/infra/RENDER_INVENTORY.md), PR #142 area / `RENDER_REPOINT` Path A.
- 2026-04-25: F-2 — `launchfree-api` decision documented (commented in `render.yaml`). Source: `docs/infra/RENDER_INVENTORY.md` F-2.
- 2026-04-25: F-4 — Single `render.yaml` at repo root. Source: `docs/infra/RENDER_INVENTORY.md` F-4.
- 2026-04-27: Track I2 — Brain reads only `VERCEL_API_TOKEN` (pydantic `VERCEL_TOKEN` alias removed). Founder: align Render env key name with blueprint (`VERCEL_API_TOKEN`). Source: F-3 in `docs/infra/RENDER_INVENTORY.md`.
- 2026-04-26: Code and docs use canonical `VERCEL_API_TOKEN` with legacy env alias in Brain for cutover. Source: PR #213, F-3 partial (superseded by 2026-04-27 Track I2).

*Renamed from `VERCEL_TOKEN` to canonical `VERCEL_API_TOKEN` per Track I2 (2026-04-27).*
