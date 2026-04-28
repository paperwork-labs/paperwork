# AxiomFolio Phase 3 — DNS & custom-domain cutover runbook

Phase 3 moves `axiomfolio.com`, `www.axiomfolio.com`, and `api.axiomfolio.com` from the founder’s **personal** Render workspace to **Paperwork Labs (org)** services, and points Cloudflare at the new `*.onrender.com` targets.

**Blocker until done:** Org workspace must be on **Render Pro** (raises custom-domain limit from 2 to 15). Without this, attach returns **402** and the script stops with an explicit billing message.

## Prerequisites

1. **Billing:** Paperwork org upgraded to Pro at [Render billing](https://dashboard.render.com/billing).
2. **Vault:** Local access so `scripts/vault-get.sh RENDER_API_KEY` returns the **org** API key (same secret name as today).
3. **Founder env (export in the shell, never commit):**
   - `RENDER_API_KEY_OLD` — personal Render API key (old team).
   - `CLOUDFLARE_API_TOKEN` — DNS edit on `axiomfolio.com`.
   - `CLOUDFLARE_ZONE_ID` — `3a216b7e555bf74416b05f29a5c38a4c` (see `apis/axiomfolio/scripts/migration/README.md`).
4. **Tools:** `bash`, `curl`, `jq` on `PATH`.

## When to run

- Prefer **after** Render **daily quotas reset** if you recently hit API limits.
- Run from **repo root** on `main` (or a branch that includes these scripts).

## Cutover (forward)

Dry-run (no API mutations):

```bash
export RENDER_API_KEY_OLD='rnd_...'
export CLOUDFLARE_API_TOKEN='...'
export CLOUDFLARE_ZONE_ID='3a216b7e555bf74416b05f29a5c38a4c'
bash scripts/cutover/axiomfolio-finish-phase-3.sh --dry-run
```

Live:

```bash
bash scripts/cutover/axiomfolio-finish-phase-3.sh
```

**Expected flow:** Pre-flight (both Render keys + Cloudflare + new `*.onrender.com` 200s) → detach domains from old personal services → attach to new org services → update three Cloudflare CNAMEs (proxied, TTL 300) → up to **10 minutes** polling `https://api.axiomfolio.com/health` and `https://axiomfolio.com/` → smoke test (`/health` JSON `status` + `version` **2.0.0**, homepage title contains **AxiomFolio**) → short final report.

**If attach fails with 402:** Upgrade org to Pro, then re-run; script is idempotent.

## Rollback (parachute)

If anything is wrong after cutover, **< ~5 minutes** to revert:

```bash
export RENDER_API_KEY_OLD='rnd_...'
export CLOUDFLARE_API_TOKEN='...'
export CLOUDFLARE_ZONE_ID='3a216b7e555bf74416b05f29a5c38a4c'
bash scripts/cutover/axiomfolio-rollback-phase-3.sh
```

**Expected flow:** Detach from **new** org services → attach to **old** personal services → Cloudflare CNAMEs back to old `*.onrender.com` → **resume** old API + frontend services → same SSL wait + smoke test (health `status: healthy`, title **AxiomFolio**; API version may differ from 2.0.0).

Use `--dry-run` on the rollback script the same way as forward.

## After success

- Forward completion line: **Phase 4 (24h soak) starts now** — monitor errors, latency, and auth.
- Keep personal Render key available until soak is done and Phase 3 is accepted.

## Reference

- Service IDs and env template: `apis/axiomfolio/scripts/migration/README.md`
- Earlier helper (manual env names): `apis/axiomfolio/scripts/migration/swap-custom-domains.sh`
