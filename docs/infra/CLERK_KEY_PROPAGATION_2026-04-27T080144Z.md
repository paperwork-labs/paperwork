# Clerk key propagation audit — 2026-04-27T080144Z

**Agent:** P (composer-2-fast)  
**Outcome:** **Aborted at pre-flight** — no secrets were written to Studio, Vercel, or Render. No keys appear in this document (only masked previews would have been recorded after success).

---

## Pre-flight checks

| # | Check | Result |
|---|--------|--------|
| 1 | `[ -f /tmp/clerk-keys.env ]` readable | **PASS** — file present and readable |
| 2 | `vercel whoami` | **PASS** — account `paperwork-labs` (verify this matches the intended Vercel team; prompt asked for “likely `paperworklabs`”) |
| 3 | `gh auth status` | **PASS** — authenticated as `paperwork-labs` with `workflow` scope |
| 4 | Studio vault `GET $STUDIO_URL/api/secrets` → 200 | **FAIL** — no repo `.env.local` or `apps/studio/.env.local` on this machine; `SECRETS_API_KEY` not in environment. Test request to default `STUDIO_URL` returned **401** `Invalid authorization scheme`. `ADMIN_EMAILS` + `ADMIN_ACCESS_PASSWORD` were not available as fallback |
| 5 | Render | **PARTIAL** — `render` CLI exists at `/opt/homebrew/bin/render` but `render whoami` reports not logged in; `RENDER_API_KEY` not exported. Step 3 would have been skipped or required API key setup |

**Decision:** Per runbook, **abort** when pre-flight fails — do not write keys or “patch around” missing Studio auth.

---

## Step 1 — Studio vault (not executed)

Planned mapping (service=`clerk`, `expires_at` null), all via `scripts/vault-set.sh` or POST `/api/secrets`:

| Vault name | Source key in `/tmp/clerk-keys.env` | Description |
|------------|--------------------------------------|-------------|
| `CLERK_PUBLISHABLE_KEY` | `CLERK_PUBLISHABLE_KEY_PROD` | Production publishable key (browser-safe) |
| `CLERK_SECRET_KEY` | `CLERK_SECRET_KEY_PROD` | Production secret — server only |
| `CLERK_PUBLISHABLE_KEY_TEST` | `CLERK_PUBLISHABLE_KEY_DEV` | Development publishable key |
| `CLERK_SECRET_KEY_TEST` | `CLERK_SECRET_KEY_DEV` | Development secret — server only |
| `CLERK_FRONTEND_API` | `CLERK_FRONTEND_API_URL_PROD` | Production frontend API URL |
| `CLERK_JWKS_URL` | `CLERK_JWKS_URL_PROD` | Production JWKS |
| `CLERK_FRONTEND_API_TEST` | `CLERK_FRONTEND_API_URL_DEV` | Development frontend API URL |
| `CLERK_JWKS_URL_TEST` | `CLERK_JWKS_URL_DEV` | Development JWKS |

**Status:** Not run.

---

## Step 2 — Vercel (not executed)

**Discovered `apps/*/vercel.json`:** `studio`, `filefree`, `launchfree`, `distill`, `axiomfolio-next`, `trinkets`.

**Expected runbook apps vs repo:**

- `paperworklabs` (marketing/admin): **no** `apps/paperworklabs/vercel.json` in this snapshot — would be skipped or path TBD.
- `brain`: **no** `apps/brain/vercel.json` — only `axiomfolio-next` present among “extra” apps; brain may be API-only on Render.
- `axiomfolio` / `axiomfolio-next`: use **`apps/axiomfolio-next`**.

No `apps/*/.vercel/project.json` files were present in the workspace (links may exist only on a developer machine).

**Status:** Not run (aborted before any `vercel env` changes).

---

## Step 3 — Render (not executed)

From `render.yaml`, relevant services for Clerk JWT env: `filefree-api`, `brain-api`, and any `distill-api` / `axiomfolio-api` blocks (confirm in full `render.yaml` when re-running).

**Status:** Not run. Would need `RENDER_API_KEY` or `render login` + service ID discovery via Render API.

---

## Step 4 — Redeploys (not executed)

No deploys triggered (no env updates). Reference workflow: `.github/workflows/vercel-promote-on-merge.yaml`.

---

## Step 5 — Shred `/tmp/clerk-keys.env`

**Skipped intentionally** — propagation did not complete; removing the file would force a new export from Clerk. **Re-run this agent after fixing Studio auth**, then allow shred on success.

Safe command when the run succeeds:

```bash
shred -u /tmp/clerk-keys.env 2>/dev/null || rm -P /tmp/clerk-keys.env 2>/dev/null || rm -f /tmp/clerk-keys.env
```

---

## Errors / skipped items (summary)

1. **Blocking:** Studio vault unreachable with current auth — add `SECRETS_API_KEY` (or `ADMIN_EMAILS` + `ADMIN_ACCESS_PASSWORD`) to `.env.local` or export in the shell, and set `STUDIO_URL` if not the default.
2. **Render:** Set `RENDER_API_KEY` or run `render login` before re-run.
3. **Vercel projects:** Confirm `paperworklabs` app path and link each `apps/<name>` with `.vercel/project.json` where needed.
4. **Team name:** Confirm `paperwork-labs` vs `paperworklabs` in Vercel is the intended scope.

---

## Recommended next steps

1. Place valid Studio credentials in `.env.local` (or export `SECRETS_API_KEY`) and re-run the propagation agent.
2. After a **successful** run, rotate `sk_live_*` and `sk_test_*` in the Clerk Dashboard, then run again with fresh values.
3. On success, allow shred of `/tmp/clerk-keys.env` per runbook.
