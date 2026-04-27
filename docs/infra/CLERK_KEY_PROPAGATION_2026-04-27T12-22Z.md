# Clerk key propagation — audit report (v2)

**Run:** 2026-04-27 (Agent P-v2)  
**Temp input:** `/tmp/clerk-keys.env` — **left intact** for founder re-runs and rotation. Shred is deferred until the rotation flow completes.

## Auth status (confirmed)

| Mechanism | Status |
|-----------|--------|
| Studio Vault — HTTP Basic (`ADMIN_EMAILS` first email + `ADMIN_ACCESS_PASSWORD`) | Working — `GET /api/secrets` returned **200** |
| Vercel CLI (`vercel whoami`) | **paperwork-labs** (per founder verification) |
| GitHub `gh` CLI | Authenticated as **paperwork-labs** (per founder verification) |
| Render API | **Skipped** — see [Render](#render-skip) |

## Input validation (schema)

All eight values from `/tmp/clerk-keys.env` were validated before writes:

- `CLERK_PUBLISHABLE_KEY_PROD` → prefix `pk_live_` ✓  
- `CLERK_SECRET_KEY_PROD` → prefix `sk_live_` ✓  
- `CLERK_PUBLISHABLE_KEY_DEV` → prefix `pk_test_` ✓  
- `CLERK_SECRET_KEY_DEV` → prefix `sk_test_` ✓  
- All four Clerk URLs → `https://` ✓  

(Full values were not logged or committed.)

## Vault writes (`POST $STUDIO_URL/api/secrets`, `service=clerk`)

| Vault name | HTTP | Masked value (first 8 chars + `...`) |
|------------|------|----------------------------------------|
| `CLERK_PUBLISHABLE_KEY` | 201 | `pk_live_...` |
| `CLERK_SECRET_KEY` | 200 | `sk_live_...` |
| `CLERK_PUBLISHABLE_KEY_TEST` | 201 | `pk_test_...` |
| `CLERK_SECRET_KEY_TEST` | 201 | `sk_test_...` |
| `CLERK_FRONTEND_API` | 201 | `https://...` |
| `CLERK_JWKS_URL` | 201 | `https://...` |
| `CLERK_FRONTEND_API_TEST` | 201 | `https://...` |
| `CLERK_JWKS_URL_TEST` | 201 | `https://...` |

`200` on an existing secret indicates upsert/conflict handling; `201` indicates create. All requests succeeded.

## Vercel environment variables

### Studio (`paperwork-labs/studio`) — **critical path**

**Linked locally:** `apps/studio/.vercel/project.json` ✓  

**Variables:** `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `NEXT_PUBLIC_CLERK_FRONTEND_API` for **production**, **preview**, and **development**.

**Notes:**

- Initial `vercel env rm …` emitted `env_not_found` for some combinations; safe to ignore.
- **Production** adds used `vercel env add … production` with stdin / `--value --yes` as applicable.
- **Preview** (CLI **50.33.1**): non-interactive `preview` targets returned `git_branch_required` unless a third argument was passed. **Workaround:** `vercel env add <NAME> preview '' --value "<val>" --yes --non-interactive` (empty string = all Preview branches).
- **Development** adds used `--value` + `--yes --non-interactive`. The CLI sometimes did not exit after success; adds were confirmed via `vercel env ls` and short-lived background + `kill` where needed.

**Deploy:**

- `vercel deploy --prod --yes` **from `apps/studio` failed** with: project Root Directory + CWD produced a non-existent path `…/apps/studio/apps/studio`.
- **Successful deploy:** from monorepo root with `VERCEL_ORG_ID` + `VERCEL_PROJECT_ID` from `apps/studio/.vercel/project.json`:

  - **Production deployment URL:** `https://studio-8vhb5lq5a-paperwork-labs.vercel.app`  
  - **Inspect:** `https://vercel.com/paperwork-labs/studio/4zQdH6JcgAa6qqwRfT7QSGWR6SzV`  
  - **Production alias:** `https://paperworklabs.com` (reported by CLI on completion)

### Other apps — skipped (not Vercel-linked locally)

No `apps/<name>/.vercel/project.json` was present for:

| App | Reason |
|-----|--------|
| `axiomfolio` | Not linked locally |
| `axiomfolio-next` | Not linked locally |
| `distill` | Not linked locally |
| `filefree` | Not linked locally |
| `launchfree` | Not linked locally |
| `trinkets` | Not linked locally |

**Founder action:** `cd apps/<name> && vercel link` (team **paperwork-labs**, correct project), then re-run the env remove/add + `vercel deploy --prod --yes` pattern for that app.

**`paperworklabs`:** There is no `apps/paperworklabs` in this repository; if that name maps to another directory or project, link it the same way once the path is known.

No additional production redeploys were triggered for these apps in this run.

## Render skip

**Would have been written (not executed):**

- **Services:** `brain-api`, `filefree-api` (Render)  
- **Variables:** `CLERK_SECRET_KEY` (prod `sk_live_*`) and `CLERK_JWKS_URL` (production JWKS URL)

**Why skipped:**

- Studio production `RENDER_API_KEY` in Vault returns **401** when used against the Render API; `render` CLI was not logged in.

**Founder action:**

1. Regenerate a Render API key: [Render dashboard — API keys](https://dashboard.render.com/u/settings#api-keys).  
2. Update the existing Vault secret **`RENDER_API_KEY`** in Studio (rotate value only).  
3. Re-run Render env propagation (or use Render dashboard) for `brain-api` and `filefree-api`.

## Recommended key rotation (after login works)

After the founder confirms login at `https://paperworklabs.com/admin`:

1. Rotate `sk_live_*` and `sk_test_*` in the Clerk Dashboard.  
2. Refresh `/tmp/clerk-keys.env` (or equivalent) and re-run this propagation so Vault + Vercel + (later) Render stay aligned.

## Next step for founder

1. Wait for the Studio production deployment to finish propagating (CLI reported ~2 minutes; allow ~3 minutes if CDN is warm).  
2. Confirm Clerk shows a healthy/custom-domain status in the Clerk Dashboard (SSL / DNS can take **~5–15 minutes** from verification).  
3. Test admin login at **`https://paperworklabs.com/admin`** (and Clerk sign-in if applicable).  
4. Link remaining Vercel apps locally and re-run env deploys for those projects; rotate Render API key and apply backend Clerk envs when ready.
