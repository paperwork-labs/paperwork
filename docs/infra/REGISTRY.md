---
owner: infra-ops
last_reviewed: 2026-05-04
doc_kind: reference
domain: infra
status: active
summary: "One row per production surface — verified from repo paths only; unknowns explicit."
---

# Production surface registry (Q2 Wave 1 — T3.2)

Canonical **names and wiring** for operators. **Do not treat this file as proof that a surface is healthy** — use dashboards and health endpoints. Where this checkout cannot confirm a value, the row says `unknown — needs founder` (no guessing).

**Column contract**

| Column | Meaning |
| --- | --- |
| `surface` | What we operate |
| `provider` | SaaS / cloud vendor |
| `name_id` | Stable id **from this repo** (project slug, service `name` in `render.yaml`, zone apex, env var *name*) or `unknown — needs founder` |
| `owner` | From nearest sibling doc front-matter when present; else `engineering` |
| `runbook` | Path under `docs/runbooks/` only if the file exists; else `none — flagged for T3.3` |
| `drift_detector_status` | `live` = Brain `iac_drift_detector` can reconcile this surface today; `planned (T3.1)` = code path stubbed or not default-enabled; `n/a` = not an IaC drift surface |
| `kill_switch_path` | Repo path or env flag documented to stop automation; `none` if absent |
| `on_call_escalation` | Default per company ops doctrine |

Default **`on_call_escalation`**: `founder (Conversation tag alert)` — use Brain Conversations with tag `alert` for infra incidents unless a runbook names a different path.

---

## 1. DNS zones (Cloudflare + registrar context)

**Sources:** `scripts/cloudflare_decommission_zones.py` (`TARGET_ZONES`), `docs/infra/FOUNDER_ACTIONS.md` (Spaceship + Cloudflare for `paperworklabs.com` / AxiomFolio), `docs/infra/CLERK_SATELLITE_TOPOLOGY.md`. **`infra/cloudflare/zones.yaml` is not present in this repo.**

| surface | provider | name_id | owner | runbook | drift_detector_status | kill_switch_path | on_call_escalation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dns_zone | Cloudflare (target account for migration cleanup) | `paperworklabs.com` | infra-ops | [../runbooks/cloudflare-ownership.md](../runbooks/cloudflare-ownership.md) | planned (T3.1) (`CloudflareDNSSurface` is `NotImplementedError` unless `BRAIN_IAC_DRIFT_SURFACES` includes `cloudflare`; no `infra/state/cloudflare.yaml` in tree) | none | founder (Conversation tag `alert`) |
| dns_zone | Cloudflare (target account for migration cleanup) | `axiomfolio.com` | infra-ops | [../runbooks/cloudflare-ownership.md](../runbooks/cloudflare-ownership.md) | planned (T3.1) | none | founder (Conversation tag `alert`) |
| dns_zone | Cloudflare (target account for migration cleanup) | `filefree.ai` | infra-ops | [../runbooks/cloudflare-ownership.md](../runbooks/cloudflare-ownership.md) | planned (T3.1) | none | founder (Conversation tag `alert`) |
| dns_zone | Cloudflare (target account for migration cleanup) | `launchfree.ai` | infra-ops | [../runbooks/cloudflare-ownership.md](../runbooks/cloudflare-ownership.md) | planned (T3.1) | none | founder (Conversation tag `alert`) |
| dns_zone | Cloudflare (target account for migration cleanup) | `distill.tax` | infra-ops | [../runbooks/cloudflare-ownership.md](../runbooks/cloudflare-ownership.md) | planned (T3.1) | none | founder (Conversation tag `alert`) |
| dns_registrar | Spaceship | `paperworklabs.com` zone registration (DNS delegated to Cloudflare; see also [CLERK_DNS_SPACESHIP.md](./CLERK_DNS_SPACESHIP.md)) | infra-ops | none — flagged for T3.3 | n/a | none | founder (Conversation tag `alert`) |

---

## 2. Vercel projects (one row per linked app)

**Sources:** `scripts/vercel-projects.json`, `apps/*/vercel.json`, `docs/infra/VERCEL_LINKING.md`. Local `.vercel/project.json` is gitignored — **not** used here.

| surface | provider | name_id | owner | runbook | drift_detector_status | kill_switch_path | on_call_escalation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| vercel_project | Vercel | `studio` → `prj_FZvJJnDdQqawjBpJAwC0SuwyMzFT` | infra-ops | [../runbooks/pre-deploy-guard.md](../runbooks/pre-deploy-guard.md) | live (`infra/state/vercel.yaml` + `VercelEnvSurface`; job `iac_drift_detector` every 30m; canonical `projects` list may be empty until seeded) | none (disable deploys in Vercel dashboard) | founder (Conversation tag `alert`) |
| vercel_project | Vercel | `filefree` → `prj_DNPGX5GrYcwer9oANv90NKqIT67I` | infra-ops | [../runbooks/pre-deploy-guard.md](../runbooks/pre-deploy-guard.md) | live | none | founder (Conversation tag `alert`) |
| vercel_project | Vercel | `distill` → `prj_1TKlkMmY3vLVNfAfRxUY57z43m11` | infra-ops | [../runbooks/pre-deploy-guard.md](../runbooks/pre-deploy-guard.md) | live | none | founder (Conversation tag `alert`) |
| vercel_project | Vercel | `launchfree` → `prj_hXQNtz5g7IAwx8lvCkODWxOyHcP7` | infra-ops | [../runbooks/pre-deploy-guard.md](../runbooks/pre-deploy-guard.md) | live | none | founder (Conversation tag `alert`) |
| vercel_project | Vercel | `axiomfolio` → `prj_7L9N3FpOFRsc12tMfKKWa8q2lDLE` | infra-ops | [../runbooks/pre-deploy-guard.md](../runbooks/pre-deploy-guard.md) | live | none | founder (Conversation tag `alert`) |
| vercel_project | Vercel | `trinkets` → `prj_MFUxaJCbQuSdJZWWVgaEtRllKjzB` | infra-ops | [../runbooks/pre-deploy-guard.md](../runbooks/pre-deploy-guard.md) | live | none | founder (Conversation tag `alert`) |
| vercel_project | Vercel | `design` → `TBD_CREATE_BEFORE_MERGE` (placeholder in `scripts/vercel-projects.json`) | infra-ops | none — flagged for T3.3 | live (still listed for drift when file exists; project may not exist) | none | founder (Conversation tag `alert`) |
| vercel_project | Vercel | `accounts` → `TBD_CREATE_BEFORE_MERGE` (placeholder; Clerk-hosted primary per `CLERK_SATELLITE_TOPOLOGY.md`) | infra-ops | none — flagged for T3.3 | live | none | founder (Conversation tag `alert`) |

**Note:** `apps/accounts/` exists with `vercel.json`, but `scripts/vercel-projects.json` still sets `repoRoot: null` for `accounts` — treat deployment wiring as **unknown — needs founder** until the JSON and dashboard match.

---

## 3. Render services and attached data stores

**Sources:** `render.yaml` (repo root), `apis/axiomfolio/render.yaml` (stub pointer only), `docs/infra/RENDER_INVENTORY.md`.

| surface | provider | name_id | owner | runbook | drift_detector_status | kill_switch_path | on_call_escalation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| render_web | Render | `filefree-api` | infra-ops | none — flagged for T3.3 | planned (T3.1) (`RenderEnvSurface` stub; not in default `BRAIN_IAC_DRIFT_SURFACES`) | none | founder (Conversation tag `alert`) |
| render_web | Render | `brain-api` | infra-ops | [../runbooks/brain-deploy-recovery.md](../runbooks/brain-deploy-recovery.md) | planned (T3.1) | `apis/brain/data/brain_paused.flag` (see `scripts/brain_pause.py`); env `BRAIN_SCHEDULER_ENABLED=false` on `brain-api` (see `docs/infra/BRAIN_SCHEDULER.md`) | founder (Conversation tag `alert`) |
| render_web | Render | `axiomfolio-api` | infra-ops | none — flagged for T3.3 | planned (T3.1) | none | founder (Conversation tag `alert`) |
| render_worker | Render | `axiomfolio-worker` | infra-ops | none — flagged for T3.3 | planned (T3.1) | none | founder (Conversation tag `alert`) |
| render_worker | Render | `axiomfolio-worker-heavy` | infra-ops | none — flagged for T3.3 | planned (T3.1) | none | founder (Conversation tag `alert`) |
| render_keyvalue | Render | `axiomfolio-redis` | infra-ops | none — flagged for T3.3 | n/a | none | founder (Conversation tag `alert`) |
| render_postgres | Render | `axiomfolio-db` | infra-ops | none — flagged for T3.3 | n/a | none | founder (Conversation tag `alert`) |
| render_web | Render | `launchfree-api` | infra-ops | [../runbooks/launchfree-api-health.md](../runbooks/launchfree-api-health.md) | n/a (service block commented out in `render.yaml`; not provisioned per `RENDER_INVENTORY.md`) | none | founder (Conversation tag `alert`) |

---

## 4. Clerk (identity)

**Sources:** `docs/infra/CLERK_SATELLITE_TOPOLOGY.md`, `packages/auth-clerk/README.md`, `apps/filefree/.env.example` (`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` placeholder only).

| surface | provider | name_id | owner | runbook | drift_detector_status | kill_switch_path | on_call_escalation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| clerk_instance | Clerk | `unknown — needs founder` (production instance / application id not in repo; topology: single production instance with `accounts.paperworklabs.com` primary + satellites per `CLERK_SATELLITE_TOPOLOGY.md`) | infra-ops | [../runbooks/filefree-preview-clerk-envs.md](../runbooks/filefree-preview-clerk-envs.md) | planned (T3.1) (`ClerkConfigSurface` stub) | Clerk Dashboard (disable application) | founder (Conversation tag `alert`) |

---

## 5. Hetzner VMs

**Sources:** `infra/hetzner/README.md`, `infra/hetzner-build/`, `infra/hetzner-workers/`, `docs/infra/FOUNDER_ACTIONS.md`. **`docs/infra/HETZNER_RUNNERS.md` is not in this repo** (path requested in prompt does not exist; runners are documented under `infra/hetzner/README.md`).

| surface | provider | name_id | owner | runbook | drift_detector_status | kill_switch_path | on_call_escalation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hetzner_vm | Hetzner Cloud | `paperwork-ops` — `204.168.147.100` (CX33; Postiz, Postgres, Redis, Temporal per `infra/hetzner/README.md`) | infra-ops | [../runbooks/hetzner-bootstrap.md](../runbooks/hetzner-bootstrap.md) | n/a | `docker compose down` on host (see `infra/hetzner/compose.yaml`) | founder (Conversation tag `alert`) |
| hetzner_vm | Hetzner Cloud | `paperwork-builders` — `89.167.34.68` (CX43; GHA self-hosted runners) | infra-ops | [../runbooks/hetzner-bootstrap.md](../runbooks/hetzner-bootstrap.md) | n/a | stop runner service / compose on host | founder (Conversation tag `alert`) |
| hetzner_vm | Hetzner Cloud | `paperwork-workers` — `204.168.165.156` (CX43; Brain background placeholder per README) | infra-ops | [../runbooks/hetzner-bootstrap.md](../runbooks/hetzner-bootstrap.md) | n/a | stop compose on host (`infra/hetzner-workers/`) | founder (Conversation tag `alert`) |

---

## 6. n8n (Hetzner) — workflows that survived Brain APScheduler cutover

**Sources:** `docs/infra/BRAIN_SCHEDULER.md` (replacement mapping), `docs/strategy/N8N_DECOMMISSION_INVENTORY.md` §1a (names three **active** workflows), `apps/studio/.env.example` (`N8N_API_URL`), `docs/infra/FOUNDER_ACTIONS.md` (live instance URL). **This checkout has no `infra/hetzner/workflows/` directory** (no JSON on disk to hash); inventory is documentation-only until that tree exists or is restored.

| surface | provider | name_id | owner | runbook | drift_detector_status | kill_switch_path | on_call_escalation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| n8n_instance | self-hosted (Hetzner) | `https://n8n.paperworklabs.com` (from `apps/studio/.env.example`) | infra-ops | [../runbooks/n8n-deprecated-cleanup.md](../runbooks/n8n-deprecated-cleanup.md) | n/a | disable workflows in n8n UI (per `FOUNDER_ACTIONS.md` §4) | founder (Conversation tag `alert`) |
| n8n_workflow | n8n | `brain-slack-adapter` (file path in inventory: `infra/hetzner/workflows/brain-slack-adapter.json` — **missing in this checkout**) | infra-ops | [../runbooks/n8n-deprecated-cleanup.md](../runbooks/n8n-deprecated-cleanup.md) | n/a | deactivate in n8n UI | founder (Conversation tag `alert`) |
| n8n_workflow | n8n | `error-notification` (`infra/hetzner/workflows/error-notification.json` — **missing in this checkout**) | infra-ops | [../runbooks/n8n-deprecated-cleanup.md](../runbooks/n8n-deprecated-cleanup.md) | n/a | deactivate in n8n UI | founder (Conversation tag `alert`) |
| n8n_workflow | n8n | `infra-status-slash` (`infra/hetzner/workflows/infra-status-slash.json` — **missing in this checkout**) | infra-ops | [../runbooks/n8n-deprecated-cleanup.md](../runbooks/n8n-deprecated-cleanup.md) | n/a | deactivate in n8n UI | founder (Conversation tag `alert`) |

---

## 7. PostgreSQL databases

**Sources:** `render.yaml` (`databases:` + `DATABASE_URL` wiring), `apis/brain/app/config.py`, `apis/filefree/app/config.py`, `apps/studio/.env.example`, `docs/SECRETS.md`, `infra/hetzner/README.md`.

| surface | provider | name_id | owner | runbook | drift_detector_status | kill_switch_path | on_call_escalation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| postgres | Render | `axiomfolio-db` (managed Postgres per `render.yaml`) | infra-ops | none — flagged for T3.3 | n/a | none (suspend service in Render dashboard) | founder (Conversation tag `alert`) |
| postgres | Neon | `DATABASE_URL` for `filefree-api` (`sync: false` in `render.yaml`; **Neon id not in repo**) | infra-ops | none — flagged for T3.3 | n/a | none | founder (Conversation tag `alert`) |
| postgres | Neon | `DATABASE_URL` for `brain-api` (`sync: false`; **Neon id not in repo**) | infra-ops | [../runbooks/brain-deploy-recovery.md](../runbooks/brain-deploy-recovery.md) | n/a | none | founder (Conversation tag `alert`) |
| postgres | Neon | Studio vault / `apps/studio/.env.example` (`DATABASE_URL` for `/api/secrets`) — **instance id not in repo** | infra-ops | [../runbooks/credential-access.md](../runbooks/credential-access.md) | n/a | none | founder (Conversation tag `alert`) |
| postgres | Docker on Hetzner | Postiz Postgres on `paperwork-ops` (`infra/hetzner/README.md` — **no cloud resource id in repo**) | infra-ops | [../runbooks/hetzner-bootstrap.md](../runbooks/hetzner-bootstrap.md) | n/a | stop container / host | founder (Conversation tag `alert`) |

---

## 8. Redis

**Sources:** `render.yaml` (`REDIS_URL`, `axiomfolio-redis`), `apis/brain/app/config.py` (`REDIS_URL`, `UPSTASH_REDIS_REST_*`), `apis/filefree/app/config.py`.

| surface | provider | name_id | owner | runbook | drift_detector_status | kill_switch_path | on_call_escalation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| redis | Render | `axiomfolio-redis` (keyvalue service) | infra-ops | none — flagged for T3.3 | n/a | none | founder (Conversation tag `alert`) |
| redis | Upstash | `REDIS_URL` for `filefree-api` (inferred from commented `render.yaml` launchfree block: “Upstash redis URI”; **no id in repo**) | infra-ops | none — flagged for T3.3 | n/a | none | founder (Conversation tag `alert`) |
| redis | Upstash | `REDIS_URL` + REST vars for `brain-api` in `render.yaml` (**resource id not in repo**) | infra-ops | none — flagged for T3.3 | n/a | none | founder (Conversation tag `alert`) |
| redis | Docker on Hetzner | Shared Redis on `paperwork-ops` (`infra/hetzner/README.md`) | infra-ops | [../runbooks/hetzner-bootstrap.md](../runbooks/hetzner-bootstrap.md) | n/a | stop compose service | founder (Conversation tag `alert`) |

---

## 9. GCP Cloud Storage buckets

**Sources:** `render.yaml` (`GCS_BUCKET_NAME` for `filefree-api`), `apis/filefree/app/config.py` (`GCS_BUCKET_NAME` default `filefree-uploads-dev`).

| surface | provider | name_id | owner | runbook | drift_detector_status | kill_switch_path | on_call_escalation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gcs_bucket | Google Cloud Storage | env var `GCS_BUCKET_NAME` on `filefree-api` (**production bucket name not committed**) | infra-ops | none — flagged for T3.3 | n/a | IAM / bucket policy in GCP console | founder (Conversation tag `alert`) |

---

## 10. GCP Cloud Vision (OCR)

**Sources:** `.cursorrules` (pipeline narrative), `render.yaml` (`GOOGLE_APPLICATION_CREDENTIALS` on `filefree-api`). **No GCP project number or id is committed in this repo.**

| surface | provider | name_id | owner | runbook | drift_detector_status | kill_switch_path | on_call_escalation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gcp_vision_project | Google Cloud | `unknown — needs founder` (project id not in repo; credentials via `GOOGLE_APPLICATION_CREDENTIALS`) | engineering | none — flagged for T3.3 | n/a | disable Vision API or service account key | founder (Conversation tag `alert`) |

---

## 11. OpenAI org

**Sources:** `docs/AI_MODEL_REGISTRY.md`, `render.yaml` / `apis/brain/app/config.py` (`OPENAI_API_KEY`). **No OpenAI organization id is present in repo config.**

| surface | provider | name_id | owner | runbook | drift_detector_status | kill_switch_path | on_call_escalation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| openai_org | OpenAI | `unknown — needs founder` | agent-ops | none — flagged for T3.3 | n/a | revoke API key in OpenAI dashboard | founder (Conversation tag `alert`) |

---

## 12. Anthropic org

**Sources:** `docs/AI_MODEL_REGISTRY.md`, `render.yaml` (`ANTHROPIC_API_KEY` on `brain-api`), `apis/brain/app/config.py`. **No Anthropic organization id is present in repo config.**

| surface | provider | name_id | owner | runbook | drift_detector_status | kill_switch_path | on_call_escalation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| anthropic_org | Anthropic | `unknown — needs founder` | agent-ops | none — flagged for T3.3 | n/a | revoke API key in Anthropic console | founder (Conversation tag `alert`) |

---

## Related infra docs (not `docs/runbooks/`)

- `docs/infra/RENDER_INVENTORY.md` — live Render ids (as of doc `last_reviewed`)
- `docs/infra/RENDER_REPOINT.md` — blueprint repointing
- `docs/SECRETS.md` — vault + env drift (runbook-style but lives outside `docs/runbooks/`)

---

## Open questions

1. **`infra/hetzner/workflows/` missing:** Many docs (`docs/strategy/N8N_DECOMMISSION_INVENTORY.md`, `docs/AI_MODEL_REGISTRY.md`, CI scripts) still reference JSON under `infra/hetzner/workflows/`. This checkout contains **no such directory** — confirm on `main` whether it was removed intentionally or this branch/worktree is incomplete.
2. **`scripts/vercel-projects.json` vs `apps/accounts`:** Repo contains `apps/accounts/` but the Vercel mapping row has `repoRoot: null` and `TBD_CREATE_BEFORE_MERGE` — reconcile project id + `repoRoot`.
3. **Canonical drift YAML:** `infra/state/README.md` references `cloudflare.yaml`, `render.yaml`, `clerk.yaml` under `infra/state/` — only `vercel.yaml` exists today; other surfaces are code stubs (`apis/brain/app/services/iac_drift.py`).
4. **Registrar-held zones:** Only `paperworklabs.com` + Spaceship context is partially documented (`FOUNDER_ACTIONS.md`, `CLERK_SATELLITE_TOPOLOGY.md`). Other registrars for `filefree.ai`, `launchfree.ai`, `distill.tax`, `axiomfolio.com` are **not enumerated in-repo** — `unknown — needs founder`.
