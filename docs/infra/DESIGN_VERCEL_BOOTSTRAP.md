# design.paperworklabs.com — Vercel bootstrap

The design canvas lives in `apps/design` (Storybook static export → `storybook-static/`). Until a Vercel project exists and DNS points at Vercel, **https://design.paperworklabs.com** will not resolve.

## One-time setup (~10 min)

1. **Vercel** → **Add New** → **Project** → Import `paperwork-labs/paperwork`.
2. **Root Directory:** `apps/design` (critical — not repo root).
3. **Build & Output:** Leave as inferred from `apps/design/vercel.json` (`installCommand` / `buildCommand` / `outputDirectory: storybook-static`).
4. **Production branch:** `main`.
5. After first deploy succeeds, open the project → **Settings** → copy **Project ID** (`prj_…`).
6. Paste that ID into `.github/workflows/vercel-promote-on-merge.yaml` for the `design` matrix row (replace `TBD_CREATE_BEFORE_MERGE`).
7. **Domains** → add `design.paperworklabs.com`.
8. At your DNS host (Cloudflare / Spaceship), add the **CNAME** Vercel shows (usually `cname.vercel-dns.com` or similar). Prefer **DNS only** (no proxy) until TLS has issued.
9. Wait for **SSL: Issued**, then verify: `curl -sI https://design.paperworklabs.com | head -5` → `200` or `304`.

## Free-tier deploy cap

If GitHub/Vercel shows “100 deployments per day”, production may lag until the daily window resets. The **auto-promote** workflow does not burn a new build; it only promotes an existing READY preview.

## Related

- Canonical checklist: `docs/infra/FOUNDER_ACTIONS.md` § design canvas.
- Promote matrix: `docs/infra/VERCEL_AUTO_PROMOTE.md` (update when `design` `prj_*` is known).
