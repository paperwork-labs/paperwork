---
title: Vault token scope matrix (T3.1-pre)
last_reviewed: 2026-05-04
owner: infra-ops
doc_kind: audit
domain: infra
status: draft
related:
  - ../SECRETS.md
  - ../infra/STUDIO_ENV.md
  - ../infra/CLOUDFLARE_TOKEN_INVENTORY.md
  - ../runbooks/credential-access.md
  - ../runbooks/pre-deploy-guard.md
  - ../runbooks/cloudflare-ownership.md
  - ../../.cursor/rules/secrets-ops.mdc
  - ../strategy/STUDIO_UX_AUDIT_2026Q2.md
---

# Vault token scope matrix (T3.1-pre)

> **Purpose:** Recommended **minimum API / credential scopes** per vendor for upcoming IaC and env-drift work (Track 3). This is a **documentation-only** posture guide derived from repo runbooks (`docs/SECRETS.md`, `docs/infra/*`, `docs/runbooks/*`, `secrets-ops.mdc`).  
> **Disclaimer (HARD):** **Not verified against live tokens or dashboards.** Do not treat this matrix as proof that any current credential matches least privilege. Use it as an **operational checklist** when minting or rotating keys.

## Sources (in-repo only)

- `docs/SECRETS.md` — vault architecture, `SECRETS_API_KEY`, environment matrix (Studio, Render, Vercel, Hetzner, Brain).
- `docs/infra/STUDIO_ENV.md` — Studio Vercel envs for infra probes (`HETZNER_API_TOKEN`, `VERCEL_API_TOKEN`, `RENDER_API_KEY`, team IDs).
- `docs/infra/CLOUDFLARE_TOKEN_INVENTORY.md` — Cloudflare token resolution and read/write paths.
- `docs/runbooks/credential-access.md` — credential map by surface (Studio, Brain, product APIs).
- `docs/runbooks/pre-deploy-guard.md` — required scopes for guard script (Vercel list env, Clerk backend key, Cloudflare DNS edit).
- `docs/runbooks/cloudflare-ownership.md` — per-zone `CLOUDFLARE_TOKEN_*` migration vs account-wide token risks.
- `docs/runbooks/hetzner-bootstrap.md` — `GHA_RUNNER_PAT` for self-hosted runner registration.
- `render.yaml` — Brain service declares `RENDER_API_KEY`, `VERCEL_API_TOKEN`, `NEON_API_KEY` (names only).
- `.cursor/rules/secrets-ops.mdc` — Studio inventory (`GITHUB_TOKEN` fine-grained `repo:read`, `VERCEL_API_TOKEN` naming).
- `docs/strategy/STUDIO_UX_AUDIT_2026Q2.md` — GitHub token missing vs empty PR widget (F-002).

---

## Matrix (recommended posture)

Column **Env var names** lists **documentary** names as they appear in docs / vault conventions — not an exhaustive vault inventory.

| Provider | Env var names (documentary) | Recommended least-privilege posture | What excessive scope risks | Founder verification checklist (on rotate) |
| --- | --- | --- | --- | --- |
| **Cloudflare** | `CLOUDFLARE_API_TOKEN` (account-wide fallback; legacy `CF_TOKEN`), `CLOUDFLARE_ACCOUNT_ID`, per-zone `CLOUDFLARE_TOKEN_<ZONE_SLUG>` (e.g. `CLOUDFLARE_TOKEN_PAPERWORKLABS_COM`), optional read-only `CLOUDFLARE_READONLY_TOKEN_*` per `CLOUDFLARE_TOKEN_INVENTORY.md` | Prefer **per-zone API tokens** with **Zone → DNS → Edit** (writes) or narrower read templates for validation-only paths; reserve account-wide token only for bootstrap or minting child tokens, then deprecate per `cloudflare-ownership.md` | Account-wide **DNS:Edit** (or broader) can mutate **every** zone — mass DNS outage, hijack of auth CNAMEs (e.g. Clerk), or SSRF-adjacent cache poisoning if combined with leaked automation | (1) Update vault first, then mirror Render/Vercel/GitHub per runbook. (2) Run `scripts/reconcile_clerk_dns.py --check-only` where Clerk applies (see `pre-deploy-guard.md`). (3) Confirm Brain logs show per-zone resolver path, not perpetual fallback to `CLOUDFLARE_API_TOKEN`. (4) Spot-check one record change in a non-prod zone if available. |
| **Render** | `RENDER_API_KEY` (workspace API key; referenced in `STUDIO_ENV.md`, `credential-access.md`, `render.yaml`) | **Read-only** key if vendor supports scoped keys **only** for status/deploy list; otherwise use the **minimum workspace role** that still allows required automation (env var read for Brain, service metadata). **Never** embed in client apps | Full workspace keys can **read all env vars**, **trigger deploys**, or **delete services** depending on Render’s key type — lateral movement across every API on Render | (1) In Render dashboard, confirm key label and **intended services**. (2) After rotation, hit Studio `/admin/infrastructure` Render card and Brain deploy paths. (3) Re-apply key anywhere `credential-access.md` lists (e.g. Brain on Render). (4) Run `make env-check` after syncing Vercel/Studio mirrors. |
| **Clerk** | `CLERK_SECRET_KEY` (backend API / “secret” key), `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` (publishable; not a bearer for admin APIs) | Use **production instance keys** only on production hosts; use **development** keys only in preview/local; restrict dashboard user access; rotate on incident | Secret key in CI or logs grants **session minting**, **user impersonation**, and **JWT signing** for that Clerk instance — full auth bypass for the product | (1) Rotate in Clerk dashboard; update vault; mirror Vercel/Render per product (`credential-access.md`). (2) Run pre-deploy guard for `studio` / `axiomfolio` / `filefree` when DNS coupling matters. (3) Smoke-test sign-in on each app. (4) Revoke old key only after 24h overlap if traffic-sensitive. |
| **Hetzner** | `HETZNER_API_TOKEN` (Studio infra card; `STUDIO_ENV.md`), SSH host keys / `root@` access (not vault API tokens but **access plane** in `hetzner-bootstrap.md`), `GHA_RUNNER_PAT` (vault; runner registration) | Cloud API token: **Read** for status-only probes; separate **write** token only on provisioning hosts (bootstrap automation), stored narrowly | **Read+Write** Cloud token can **power off**, **snapshot**, or **rebuild** servers — ransomware or accidental fleet loss | (1) Confirm Studio Hetzner card still loads with read token. (2) If bootstrap PAT rotated, re-register runners per `hetzner-bootstrap.md`. (3) SSH smoke test to `paperwork-ops` / builders / workers. (4) `docker compose` health on n8n if ops box touched. |
| **Neon** | `NEON_API_KEY` (Studio optional + Brain `render.yaml`), `NEON_PROJECT_ID` (credential map), `DATABASE_URL` / `DATABASE_URL_UNPOOLED` (connection strings — **not** the same as management API key) | Management API key: **project-scoped** with **read** for health/branches if Neon roles allow; **no org-wide admin** unless required; DB URLs remain **app runtime** secrets with **least DB role** (app user, not superuser) | Broad Neon API keys can **delete branches**, **reset passwords**, or **expose connection endpoints** to other projects if mis-scoped | (1) Rotate management key in Neon console; update vault + Render (`render.yaml` names). (2) Confirm migrations/Brain DB probes still succeed. (3) **Do not** log connection URLs. (4) Invalidate old key after deploy propagation. |
| **Vercel** | `VERCEL_API_TOKEN` (canonical; **not** `VERCEL_TOKEN`), `VERCEL_TEAM_ID` / `VERCEL_ORG_ID`, optional `VERCEL_TEAM_SLUG` | Token scoped to **team** that owns monorepo projects; permissions limited to **read projects/deployments**, **read env** where CI needs manifest checks, **`vercel promote`** only if workflow requires — avoid full **Owner** if Vercel offers scoped tokens | Over-scoped token can **deploy arbitrary code**, **exfiltrate env vars** for all projects, or **burn Hobby deploy quota** via API deploys (`VERCEL_QUOTA_AUDIT_2026Q2.md` narrative) | (1) `vercel env ls production` from `apps/studio` after rotation. (2) Run `scripts/check_pre_deploy.py` for a canary project. (3) Confirm GitHub Actions secret name matches `VERCEL_API_TOKEN` (`VERCEL_AUTO_PROMOTE.md`). (4) Watch first promote or preview job for 403 scope errors. |
| **GitHub** | `GITHUB_TOKEN` (Studio: PR list / CI status per `secrets-ops.mdc`), `GITHUB_PAT` / `GITHUB_PAT_FINEGRAINED` / `GHA_RUNNER_PAT` (Hetzner n8n / runner bootstrap per `hetzner-bootstrap.md`, `secrets-ops.mdc`) | **Fine-grained PAT** for Studio widgets: single org/repo, **read** for PRs and checks (`secrets-ops.mdc`). **Runner registration** (`GHA_RUNNER_PAT`): use the **narrowest** PAT GitHub’s runner registration flow accepts — `hetzner-bootstrap.md` references **`repo` scope** for self-hosted runner registration; do not grant org-wide admin unless a runbook explicitly requires it | Classic broad `repo` PAT can **push code**, **merge PRs**, **delete packages**, and **exfiltrate Actions secrets** if leaked to n8n or logs | (1) Validate token only reaches intended repos (GitHub → PAT settings). (2) Studio Overview: confirm PR widget not empty vs “not configured” (see `docs/strategy/STUDIO_UX_AUDIT_2026Q2.md` F-002). (3) After `GHA_RUNNER_PAT` rotate, verify runners appear online (`hetzner-bootstrap.md`). (4) Revoke old PAT after runners re-authorized. |

---

## Notes for T3.1 IaC drift work

1. **Vault-first** — Always rotate in Studio vault (`POST /api/secrets` or UI), then mirror to Vercel, Render, Hetzner, and GitHub Actions secrets (`docs/SECRETS.md`, `secrets-ops.mdc`).
2. **Name drift** — `VERCEL_API_TOKEN` is canonical; `CF_TOKEN` is legacy alias for Cloudflare in some scripts (`pre-deploy-guard.md`). Prefer documented names in new automation.
3. **Silent health is forbidden** — If a probe omits a token, UI may look “empty but healthy” (`STUDIO_UX_AUDIT_2026Q2.md` F-002 for GitHub). After rotation, confirm **explicit** success states, not blank widgets.
4. **Per-zone Cloudflare** — Target state is per-zone writers + no long-lived account-wide `CLOUDFLARE_API_TOKEN` (`cloudflare-ownership.md`).

---

## Change log

| Date | Change |
| --- | --- |
| 2026-05-04 | Initial T3.1-pre matrix from repo docs only (no live token verification). |
