# Stack audit — Q2 2026 (T3.0)

**Purpose:** Read-only snapshot of repository-declared stack choices for **Master Plan Track 3** input (feeds future **T3.14** modernization decisions).  
**Audit date:** 2026-05-04  
**Method:** Inspected committed files only (`package.json`, `pnpm-workspace.yaml`, `pyproject.toml`, `requirements*.txt`, `render.yaml`, `.github/workflows/*.yaml`, Dockerfiles, `turbo.json`, app wiring). **No** live API calls to registries, dashboards, or vaults.

**Canonical pointers (not duplicated here):** high-level agent and stack doctrine lives in [`AGENTS.md`](../AGENTS.md) and [`.cursor/rules/engineering.mdc`](../.cursor/rules/engineering.mdc) (see also root `.cursorrules` for full monorepo doctrine).

---

## 1. Workspace & root tooling

| Item | Value (from repo) |
| --- | --- |
| Package manager | `pnpm@10.33.2` (`package.json` `packageManager`) |
| Workspaces | `apps/*`, `!apps/_archive/**`, `packages/*`, `packages/skills/*` (`pnpm-workspace.yaml`) |
| Node engine | `>=20.9.0` (root + apps; `.node-version` = `20`) |
| TypeScript (root devDep) | `5.7.3` (root `package.json`) |
| Task runner | Turborepo `^2.9.8` (`turbo.json` — build/lint/type-check/test graph) |
| Python (repo pin) | `.python-version` → **3.11** |
| Python workspace | Root `pyproject.toml` — `uv` workspace, `members = ["apis/*", "packages/python/*"]`, `requires-python = ">=3.11"` |
| Root `uv.lock` | **Not present** in this checkout (resolution for `uv sync` / lock discipline not verifiable from disk alone) |

---

## 2. Applications (`apps/*/package.json` — summary)

| Package name | Role | Notable pins (dependencies) |
| --- | --- | --- |
| `@paperwork-labs/filefree` | Consumer tax web | `next` `^16.2.4`, `react` `^19.2.5`, `@clerk/nextjs` `^7.3.0`, `@sentry/nextjs` `^10.51.0`, Vercel AI `ai` / `@ai-sdk/*`, `posthog-js`, `@paperwork-labs/*` workspace |
| `@paperwork-labs/studio` | Command center / admin | Same Next/React/Clerk generation; `@neondatabase/serverless`, `@paperwork/observability`, TipTap — **no** `@sentry/nextjs` in manifest |
| `@paperwork-labs/launchfree` | Formation web | Next 16 / React 19 / Clerk; `zod` `^4.4.2` |
| `@paperwork-labs/distill` | B2B web | Next 16 / React 19 / Clerk (minimal dep set) |
| `@paperwork-labs/trinkets` | Utility tools web | Next 16 / React 19 / Clerk |
| `@paperwork-labs/accounts` | Clerk Account Portal shell (see `docs/infra/VERCEL_PROJECTS.md` for product/DNS nuance) | Next 16 / React 19 / Clerk |
| `@paperwork-labs/axiomfolio` | Portfolio web | Next 16 / React 19 / Clerk; heavier Radix/lightweight-charts surface |
| `@paperwork-labs/design` | Storybook design system | Storybook `^10.3.6`, Vite `^8.0.10`, **`typescript` `^6.0.3`** (intentional divergence from other apps) |
| `@paperwork/probes` | Synthetic Playwright probes | `@playwright/test` `^1.59.1` only |

**Front-end env hooks (Turbo):** `turbo.json` build passes through `NEXT_PUBLIC_SENTRY_DSN`, PostHog keys, AxiomFolio feature flags, etc. Actual values are **vault-only**.

---

## 3. Selected workspace packages (`packages/*`)

| Package | Notes |
| --- | --- |
| `@paperwork-labs/ui` | Shared shadcn/Radix layer; Tailwind ^4.x in package (see manifest) |
| `@paperwork-labs/auth-clerk` | Canonical Clerk wrappers + JWT helpers; peers `next` `^15 \|\| ^16`, `@clerk/nextjs` `^7` |
| `@paperwork-labs/analytics` | `posthog-js` wrapper |
| `@paperwork-labs/data` | Zod `^4.4.2`; JSON/schema surface for reference data |
| `@paperwork/observability` | TypeScript package (built with `tsc`); consumed by Studio — **no Sentry SDK in this manifest** |
| `@paperwork-labs/pwa` | PWA helpers (studio) |
| `packages/skills/*` | Domain skills packages (pnpm workspace) |

---

## 4. Python backends (`apis/*`)

| API | Layout | Runtime evidence | Dependency style |
| --- | --- | --- | --- |
| `apis/filefree` | `pyproject.toml` + `requirements.txt` | `requires-python ">=3.11"`; **Render `PYTHON_VERSION` `3.11.0`** in `render.yaml` | Lower bounds in `requirements.txt` (e.g. `fastapi>=0.136.1`); editable installs of `packages/python/*` |
| `apis/brain` | `pyproject.toml` + `requirements.txt` | **Dockerfile:** `python:3.11.9-slim`; **Brain `tool.mypy`:** `python_version = "3.13"` ⚠ mismatch vs image | Lower bounds + Langfuse, LiteLLM, APScheduler, etc. |
| `apis/axiomfolio` | `pyproject.toml` + **`requirements.txt` (pinned `==`)** | **Dockerfile:** `python:3.11-slim` | Strict pins; Celery/redis/market-data stack |
| `apis/launchfree` | `pyproject.toml` + `requirements.txt` | Local/dev only in practice; **`launchfree-api` service commented out** in root `render.yaml` | Lower bounds + shared packages |

---

## 5. Shared Python (`packages/python/*`)

On-disk packages (each with `pyproject.toml`): **`api-foundation`**, **`clerk-auth`**, **`data-engine`**, **`mcp-server`**, **`money`**, **`observability`** (OTel stack), **`pii-scrubber`**, **`rate-limit`**.

**Doc drift:** `packages/python/README.md` “Current packages” table lists only `mcp-server` as live and names others as future — README is **behind** the tree above.

---

## 6. Hosting & data plane (`render.yaml` — declared intent)

| Service | Type | Notes |
| --- | --- | --- |
| `filefree-api` | Render web (Python/pip) | `DATABASE_URL`, `REDIS_URL`, GCS/OpenAI secrets `sync: false`; Alembic pre-deploy |
| `brain-api` | Render web (**Docker**) | Langfuse envs, Neon + Upstash REST vars, Brain secrets; mounts repo slices in image |
| `axiomfolio-api` | Render web (**Docker**) | Postgres via Render `axiomfolio-db`; Redis via `axiomfolio-redis` Render Key Value |
| `axiomfolio-worker` / `-worker-heavy` | Render workers | Celery queues split; **`--beat` only on fast worker** |
| `axiomfolio-redis` | Render Key Value | Dedicated cache/queue backbone |
| `axiomfolio-db` | Render PostgreSQL (`basic-1gb`) | **Not** Neon — separate product DB path |
| `launchfree-api` | **Absent (comment block)** | Spec preserved; provisioning deferred |

**Vercel:** Consumer/B2C Next apps are explicitly **out of `render.yaml`** (comment header). Deploy mechanics documented under `docs/infra/VERCEL_PREBUILT.md` (prebuilt flows; often tied to **`runs-on: [self-hosted, hetzner]`**).

---

## 7. CI / GitHub Actions — runner usage (high level)

There is **`no`** `docs/infra/HETZNER_RUNNERS.md` in this repository; runner rationale appears in workflow comments and `docs/infra/VERCEL_PREBUILT.md`, `docs/infra/GITHUB_ACTIONS_QUOTA_AUDIT_2026Q2.md`, and `infra/hetzner/README.md`.

| Pattern | Workflows (examples) | `runs-on` |
| --- | --- | --- |
| Default CI | `ci.yaml` — lint, path filters, UI purity, secrets scan | `ubuntu-latest` |
| Heavy integration | `ci.yaml` — API tests (Postgres + Redis services), comment: cost / minutes | `[self-hosted, hetzner]` |
| Vercel prebuilt deploy | `vercel-prebuilt.yaml` | mix: `ubuntu-latest` + `[self-hosted, hetzner]` |
| Chromatic | `chromatic.yaml` | `[self-hosted, hetzner]` |
| Brain golden / smoke | `brain-golden-suite.yaml`, `brain-post-deploy-smoke.yml` | self-hosted / ubuntu mix |
| AxiomFolio CI | `axiomfolio-ci.yml` | self-hosted for selected jobs |

**Policy inference only:** self-hosted runners are used to **reduce GitHub-hosted minute burn** and run heavier jobs; exact capacity, labels, and hardening are **operator / infra**, not fully specified in YAML.

---

## 8. Identity & auth surfaces

| Surface | Evidence |
| --- | --- |
| Clerk (Next) | `@clerk/nextjs` + `@clerk/themes` across product apps; shared `@paperwork-labs/auth-clerk` |
| Clerk JWT (Python) | `packages/auth-clerk/src/python` copied into Docker images (see `apis/axiomfolio/Dockerfile`); `packages/python/clerk-auth` for shared validation patterns |
| Studio DB driver | `@neondatabase/serverless` in `apps/studio` (Serverless driver — not proof of which Neon project/env) |

---

## 9. Observability (repo-visible)

| Layer | Tooling |
| --- | --- |
| FileFree Next | `@sentry/nextjs` + `sentry.*.config.ts` / `instrumentation.ts` |
| Brain API | `langfuse` dependency + `LANGFUSE_*` env keys in `render.yaml` |
| Shared Python | `packages/python/observability` — OpenTelemetry exporters + FastAPI integration |
| AxiomFolio API | Custom OTel stack comments in `requirements.txt` (New Relic removed historically) |
| Studio TS | `@paperwork/observability` package (implementation not expanded in this audit) |

**Gap:** no single “all products report to X” statement in code; Sentry is **FileFree-only** in manifests reviewed.

---

## 10. Layer verdicts (for T3.14 planning)

| Layer | Verdict | One-line rationale | Risk | Effort | Owner suggestion |
| --- | --- | --- | --- | --- | --- |
| pnpm + Turborepo monorepo | **KEEP** | Mature workspace split; turbo env contract is explicit. | Workspace sprawl if apps diverge further | S | Composer fleet (hygiene) |
| Node 20 + Next 16 + React 19 | **KEEP** | Aligned across active apps; matches current engineering target. | Upgrade churn if Framework majors diverge | S | Orchestrator for major bumps |
| TypeScript dual tracks (5.x apps vs 6.x design) | **DEFER** | Intentional for Storybook/Vite; acceptable until convergence plan exists. | Type tooling confusion for contributors | M | Composer + design owner |
| FileFree + shared packages on Zod 4 | **KEEP** | Consistent where adopted; validates reference data client-side. | Any remaining Zod 3 islands need migration clarity | M | Composer fleet |
| Python 3.11 pin (`.python-version`) | **KEEP** | Matches Docker bases and Render `PYTHON_VERSION` for FileFree. | Brain `mypy` claims 3.13 without 3.13 runtime — tooling noise | S | Composer (align mypy/docker) |
| Brain mypy `3.13` vs `python:3.11.9` image | **UPGRADE** (reconcile) | Single source of truth for language + typing should match runtime. | False confidence in CI/type checks | S | Composer |
| uv workspace without committed `uv.lock` | **UPGRADE** | README promises lockfile discipline; absent file blocks reproducible proofs from repo alone. | Non-deterministic dependency resolution in fresh envs | M | Composer + orchestrator gate |
| `requirements.txt` style split (ranges vs pins) | **UPGRADE** | FileFree/LaunchFree/Brain use lower bounds; AxiomFolio pins — unify policy per tier. | Accidental drift / supply-chain surprises | M | Orchestrator decides policy |
| `packages/python/*` shared libs | **KEEP** | Correct direction vs duplicated backend logic per `.cursorrules` brain doctrines. | Package README stale vs reality | XS | Composer (docs) |
| `render.yaml` split (web vs Docker; LaunchFree deferred) | **DEFER** | LaunchFree API consciously commented; avoids surprise billing until FE wired. | Blueprint sync could re-enable accidentally | S | Orchestrator |
| Axiom on Render Postgres + Render Redis | **KEEP** | Coherent dedicated stack for trading domain. | Cost + backup ops outside Neon pattern | M | Infra/orchestrator |
| FileFree/Brain Neon + Upstash hints | **KEEP** (pattern) | Industry-standard serverless pairing; refs in manifests/docs. | Secret misconfiguration yields outage | — | Vault + infra |
| GHA self-hosted Hetzner runners | **KEEP** | Used for expensive jobs explicitly. | Runner compromise or mis-label blocks CI | L | Orchestrator + infra |
| Clerk + `@paperwork-labs/auth-clerk` | **KEEP** | Centralized SSO story and JWT bridge to Python. | DNS / instance mis-wiring (`accounts` nuance per infra docs) | M | Composer + partnerships N/A |
| Sentry only on FileFree | **UPGRADE** | Errors on other surfaced products lack same capture path unless elsewhere wired. | Blind spots Studio/Distill/Axiom | M | Composer fleet |
| Langfuse on Brain | **KEEP** | LLM tracing is product-critical for orchestration. | Data residency / cost — see vault | M | CFO + orchestrator |

---

## 11. Unknown / needs vault / external confirmation

The following cannot be asserted from Git alone:

- **Exact resolved versions** from `pnpm-lock.yaml` / PyPI (audit used manifest ranges/pins only; lockfile not parsed here).
- **Production secrets:** scopes and rotation state for Clerk, Neon, Upstash, GCP, OpenAI, Render, Vercel, GitHub tokens, Langfuse, Hetzner API tokens, etc.
- **Whether `uv.lock` exists in another branch or CI artifact** — absent at repo root in this checkout.
- **Live Sentry project configuration** (DSN, sampling, PII rules) — only `NEXT_PUBLIC_SENTRY_DSN` wiring is visible.
- **Vercel/Render dashboard reality** vs `render.yaml` (manual env overrides, scaled plans, region drift).
- **Self-hosted runner security baseline** (OS patch level, network isolation) — not in YAML.

Record confirmations in the Studio vault / `docs/SECRETS.md` workflow per [`AGENTS.md`](../AGENTS.md); do not infer from this file.

---

## 12. Follow-ups suggested for T3.14 (non-binding)

1. Refresh `packages/python/README.md` “Current packages” to match on-disk packages.  
2. Align Brain Docker base Python with `tool.mypy.python_version` (pick 3.11 everywhere **or** move image to 3.13 with explicit QA).  
3. Decide **one** Python dependency policy: pinned prod (`==`) vs bounded (`>=`) per API, document in `AGENTS.md` or `docs/infra/`.  
4. Expand Sentry (or equivalent) beyond FileFree **or** document intentional exception per app.  
5. Add and commit **`uv.lock`** at repo root if uv workspace is production truth (per `packages/python/README.md` claims).
