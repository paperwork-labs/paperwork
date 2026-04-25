---
owner: infra-ops
last_reviewed: 2026-04-25
doc_kind: runbook
domain: infra
status: active
severity_default: yellow
related_runbooks: []
---
# Runbook: Render Repoint to Monorepo

> Four AxiomFolio Render services still point at the archived
> `paperwork-labs/axiomfolio` repo. With one consolidated `render.yaml`
> at the monorepo root, repointing is now a **single Blueprint Sync**
> instead of four per-service dashboard sessions.

## When this fires

- [RENDER_INVENTORY.md](RENDER_INVENTORY.md) Finding **F-1** is open, or
  a migration plan schedules cutover of `axiomfolio-api`,
  `axiomfolio-worker`, `axiomfolio-worker-heavy`, and
  `axiomfolio-frontend` to the monorepo.
- Deliberate change window — you are switching the **Blueprint** in
  Render, not hot-fixing a crash loop.

| Level | Trigger | Action |
| --- | --- | --- |
| YELLOW | Planned repoint, CI green, no user-visible outage yet | Run this runbook, coordinate in `#deployment`. |
| RED | Repoint caused failed deploys, health red, or customer impact | Rollback first (see [Rollback](#rollback)), then [Escalation](#escalation). |

**Prereqs (blockers if missing):** Read [RENDER_INVENTORY.md](RENDER_INVENTORY.md) (F-1, F-6). Render dashboard: [dashboard.render.com](https://dashboard.render.com). `gh` CLI for archive step.

## Triage (≤5 min)

```bash
# Monorepo main is healthy
gh run list --branch main --limit 5

# Brain reachable (baseline)
curl -sS https://brain-api-zo5t.onrender.com/health
```

If `main` is red → **stop**; fix CI before repointing. If Brain health fails → treat as separate incident, then return here.

## Path A: `brain-api` Docker Build Context Directory fix (F-6)

Symptom: every push to `main` builds with errors of the form

```
#16 ERROR: failed to compute cache key: "/apis/brain/requirements.txt": not found
#15 ERROR: "/apis/brain": not found
#14 ERROR: "/.cursor/rules": not found
```

Cause: Render exposes the build context override as **two separate
fields** in **Settings → Build & Deploy**:

| Render field | What it does | What blueprint maps to |
| --- | --- | --- |
| **Root Directory** | Where commands run (`buildCommand`, `preDeployCommand`, etc.) | `rootDir:` |
| **Docker Build Context Directory** | Path passed as `docker build <context>` | `dockerContext:` |

The blueprint declares `dockerContext: .` (build from monorepo root)
but the **Docker Build Context Directory** field on the live service
was set to `apis/brain`. With that override, `COPY apis/brain/requirements.txt`
in [`apis/brain/Dockerfile`](../../apis/brain/Dockerfile) tries to
resolve `apis/brain/apis/brain/requirements.txt` and fails. **Root
Directory was already empty** — the wrong field was being blamed.

Steps (one click, ~5 min):

1. Open [`brain-api` Settings → Build & Deploy](https://dashboard.render.com/web/srv-d74f3cmuk2gs73a4013g/settings).
2. Find the **Docker Build Context Directory** field. Clear it to empty.
   (Leave **Root Directory** alone if it's already empty.)
3. **Dockerfile Path**: confirm `apis/brain/Dockerfile`. Save.
4. Render auto-triggers a build from the monorepo root.
5. Verify:

   ```bash
   curl -sS https://brain-api-zo5t.onrender.com/health
   gh run list --branch main --limit 3 --workflow brain-tests.yml
   ```

   Both should be green; Render's **Deploys** tab shows the latest
   `main` SHA matching `git rev-parse origin/main`.

Rollback: re-set the field to `apis/brain` and rebuild — but that puts
you back on the broken combo, so only do this if the monorepo build
itself regresses.

## Path B: AxiomFolio repoint via consolidated Blueprint (F-1)

Since 2026-04-25 there is **one** `render.yaml` at the monorepo root
declaring every Paperwork-managed service (FileFree, Brain, AxiomFolio
API + workers + frontend, axiomfolio-redis, axiomfolio-db). The
`apis/axiomfolio/render.yaml` is now a stub pointer.

**Why this works:** Render's "Associate existing services" Blueprint
flow looks up each service in your workspace **by name**. When the
new Blueprint is created against `paperwork-labs/paperwork`, the
existing AxiomFolio services attach to it and Render flips their
underlying repo pointer to the monorepo automatically. Zero per-service
clicks.

> If your Blueprint preview screen shows only `filefree-api` /
> `brain-api` and you don't see the AxiomFolio services, you are
> reading the **old** `render.yaml`. Pull `main`, confirm the file
> declares 6+ services, and try again.

Steps (~10 min, single dashboard session):

1. **Render dashboard** → **Blueprints** → **New Blueprint**.
2. **Repository**: `paperwork-labs/paperwork`.
3. **Branch**: `main`.
4. **Blueprint Path**: leave as `render.yaml` (the default).
5. **Name**: `Paperwork Products` (or any label).
6. Render shows a preview titled "Specified configurations" with one
   row per service. Expected:
   - **Associate** existing service `filefree-api`.
   - **Associate** existing service `brain-api`.
   - **Associate** existing service `axiomfolio-api`.
   - **Associate** existing service `axiomfolio-worker`.
   - **Associate** existing service `axiomfolio-worker-heavy`.
   - **Associate** existing service `axiomfolio-frontend`.
   - **Associate** existing key-value store `axiomfolio-redis`.
   - **Associate** existing database `axiomfolio-db`.
   - Plus a handful of "Update health check path / Dockerfile path"
     adjustments — that's expected, the blueprint is now the source of
     truth.
7. **Choose**: `Associate existing services`. (Do **not** pick "Create
   all as new services" — that would spin up duplicates.)
8. **Create Blueprint**. Render begins a build for any service whose
   config changed (most importantly `axiomfolio-frontend` whose
   `buildCommand` and `staticPublishPath` are repointed at the
   monorepo).
9. After the syncs, repo pointer for every AxiomFolio service is
   `paperwork-labs/paperwork` and `Dockerfile.backend` is replaced by
   `Dockerfile`.

Render's API doesn't expose `repository` reassignment on existing
services; the Blueprint flow does. That's the only documented path.

## Path C: drop the orphaned Blueprint(s)

If you previously created a Blueprint pointing at
`apis/axiomfolio/render.yaml`, delete it once Path B is confirmed
green — otherwise Render will sync from a stub file and overwrite the
working config. **Dashboard → Blueprints → old Blueprint → Settings →
Delete.** This does **not** delete the underlying services.

## Verification

After each service's build finishes (about 2–5 min):

```bash
curl -sS https://axiomfolio-api-02ei.onrender.com/health
curl -sS https://axiomfolio-frontend-ia2b.onrender.com/
```

Workers: no HTTP — confirm recent **Deploys** tab in the dashboard or
ask Brain in Cursor: `@brain render: show me recent deploys for axiomfolio-worker`.

DoD checklist (lives in [RENDER_INVENTORY.md](RENDER_INVENTORY.md)):

- All four AxiomFolio service `repo` fields read `paperwork-labs/paperwork`.
- Latest `main` SHA matches the deploy of every service.
- `/admin/infrastructure` in Studio shows all six services green.

## Rollback

If the monorepo build is wrong, prefer rollback over panic-edits:

1. Render → service → **Manual Deploy** → last known-green commit. This
   preserves the `srv-…` IDs and hostnames.
2. If a Blueprint sync set the wrong build command on
   `axiomfolio-frontend`, revert by re-running the Blueprint Sync from
   a known-good commit (top-right "Sync" on the Blueprint detail page).
3. Do **not** delete a service; recreating breaks hardcoded `srv-…` or
   hostname assumptions.

## Escalation

- **`#deployment`:** post `@paperwork status axiomfolio` if services go
  red; don't "fix" by random env changes mid-flight.
- **Vendor:** [Render support](https://render.com) if dashboard/API
  blocks you — link the ticket in `#deployment`.

## Post-incident

- Tick **F-1** in [RENDER_INVENTORY.md](RENDER_INVENTORY.md) when six
  services are on the consolidated Blueprint and verified.
- After all services are green on the monorepo for **≥ 24 h**, archive
  the old repo (read-only history):

  ```bash
  gh repo archive paperwork-labs/axiomfolio --yes
  ```

- Bump `last_reviewed` on this file when the migration is done.

## Appendix

### Service IDs (current Render)

- `axiomfolio-api`        — `srv-d7lg0o77f7vs73b2k7m0`
- `axiomfolio-worker`     — `srv-d7lg0o77f7vs73b2k7lg`
- `axiomfolio-worker-heavy` — `srv-d7lg0o77f7vs73b2k7kg`
- `axiomfolio-frontend`   — `srv-d7lg0dv7f7vs73b2k1u0`
- `brain-api`             — `srv-d74f3cmuk2gs73a4013g`
- `filefree-api`          — `srv-d70o3jvkijhs73a0ee7g`
- Blueprint source: `/render.yaml` at monorepo root.

### Related

- [RENDER_INVENTORY.md](RENDER_INVENTORY.md) — F-1, F-6 DoD.
- [dashboard.render.com](https://dashboard.render.com)
