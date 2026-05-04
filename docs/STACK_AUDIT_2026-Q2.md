# Stack Truth Audit — Paperwork Labs 2026 Q2

**Status**: PROPOSED — pending founder ratification  
**Date**: 2026-05-04  
**Authored by**: T3.0 cheap-agent (composer-2-fast); diff-reviewed by orchestrator (Opus)  
**Supersedes**: prior informal Brain stack notes (not a formally ratified stack audit)  
**Feeds**: T3.14 stack-audit verdicts execution — see `docs/plans/PAPERWORK_LABS_2026Q2_MASTER_PLAN.md`  

**Evidence**: Inspected `render.yaml`, `apps/*/package.json`, `apis/*/requirements.txt` & `pyproject.toml`, `.github/workflows/*`, `packages/auth-clerk/README.md`, `docs/infra/CLERK_SATELLITE_TOPOLOGY.md`, `docs/infra/RENDER_INVENTORY.md`, `docs/infra/RENDER_QUOTA_AUDIT_2026Q2.md`, `infra/state/vercel.yaml`, `scripts/reconcile_clerk_dns.py`, `apis/brain/app/services/embeddings.py`, `apis/brain/app/models/episode.py`, `infra/hetzner/langfuse/docker-compose.yml`.

---

## Summary table

| Layer | Current | Verdict | Cost today | Cost post-change | Effort | Reversibility |
| --- | --- | --- | --- | --- | --- | --- |
| Hosting — Vercel | Next.js **16.2.x** / React **19.2.x** apps on Vercel git deploy; `@vercel/analytics` on consumer surfaces | **KEEP** | **NEEDS_HUMAN** — invoice + seat/app count | Stable at current architecture | **S** | Swap provider = DNS + env migration (L) |
| Hosting — Render | `render.yaml`: **filefree-api** (Python Starter), **brain-api** Docker (**standard** in blueprint), **axiomfolio** web + 2 workers (**standard**), Render Redis + Postgres for AxiomFolio; **launchfree-api** commented out | **UPGRADE** | **NEEDS_HUMAN** — ~\$7 Starter + multiple Standard + DB; pipeline overages per quota audit | Lower churn → fewer build minutes; optional plan right-sizing | **M** | Blueprint-driven; revert via git + sync |
| Hosting — Hetzner CX33 | Ops stack (e.g. Langfuse compose under `infra/hetzner/`); **GitHub self-hosted runners** (`runs-on: [self-hosted, hetzner]`) for heavy CI | **KEEP** | ~\$6–15/mo VM class + maintainer time | Same unless workload grows | **S** | Drain runners + disable labels |
| Hosting — Cloudflare (DNS) | API-driven DNS scripts (`reconcile_clerk_dns.py`, `dns_set_spf_dmarc.py`, token helpers); zones per ops docs | **KEEP** | Often bundled / low marginal | — | **S** | DNS export + NS cutover |
| Frameworks — Next.js / TS | **next ^16.2.4**, **react ^19.2.5**, **tailwindcss ^4.2.x**, **typescript ^5.6**, Turbopack dev scripts | **KEEP** | — | — | **S** ongoing semver | Pin / rollback in **1 PR** |
| Frameworks — FastAPI / Python | **fastapi>=0.136.1**, **uvicorn**, **Python 3.11** on Render env; Brain **Dockerfile** path | **KEEP** | — | — | **S** | Deploy rollback |
| Frameworks — Vercel AI SDK | `ai` **^6**, `@ai-sdk/react` **^3**, `@ai-sdk/openai` **^3** (FileFree); aligns with stack doctrine | **KEEP** | Token spend separate | — | **S** | Library swap only if product needs |
| Auth — Clerk | `@clerk/nextjs` **^7.3**, `@paperwork-labs/auth-clerk` shells, JWT verification for APIs; satellite topology **documented**, cross-apex SSO **incomplete** per runbook | **NEEDS_HUMAN** | **NEEDS_HUMAN** — plan tier | Depends on org/RBAC choices | **M–L** | Config + DNS + Dashboard |
| DNS/CDN — Cloudflare features | Repo proves **DNS API** automation; **no** checked-in Workers / Cache Rules / Transform Rules definitions | **NEEDS_HUMAN** | — | — | **S** audit first | Rule toggle |
| Data — Neon Postgres | Brain + FileFree etc. via `DATABASE_URL` (sync secrets); Studio uses `@neondatabase/serverless` | **KEEP** | Free/low → scales with usage | — | **S** | Logical migration if ever replacing |
| Data — Upstash Redis | REST + Redis URI envs on Brain & FileFree blueprint | **KEEP** | Free tier caps | — | **XS** | Swap URL |
| Data — GCP Cloud Storage | FileFree OCR pipeline / docs (`GOOGLE_APPLICATION_CREDENTIALS`, `GCS_BUCKET_NAME`) | **KEEP** | Usage-based | — | **M** if bucket migration | Dual-write window |
| Data — Vectors | **pgvector** `VECTOR(1536)` on Brain episodes (`episode.py`); embeddings via **OpenAI** `text-embedding-3-small` (`embeddings.py`) — **no** Pinecone/Weaviate | **KEEP** | Embedding \$ + Neon storage | — | **L** if moving off Postgres | DB migration |
| AI — Providers & observability | Brain env: **OPENAI**, **ANTHROPIC**, **GOOGLE** keys; **Langfuse** self-host URL in `render.yaml` + `init_langfuse()`; FileFree front uses **OpenAI** via AI SDK | **UPGRADE** | Model \$ dominant | Gateway consolidation **may** simplify routing | **M** | Feature-flag providers |
| CI/CD — GitHub Actions | **38** workflow files; **`dorny/paths-filter`** gate in `ci.yaml`; mix **`ubuntu-latest`** and **`[self-hosted, hetzner]`**; composite **`.github/actions/vercel-prebuilt`**; limited **`workflow_call`** reuse | **UPGRADE** | GH + self-hosted amortized | Fewer redundant runs → \$ | **M** | YAML revert |
| IaC & drift | **`render.yaml`** consolidated blueprint; **`infra/state/vercel.yaml`** schema stub (**empty** projects); drift scripts (`iac_drift_seed.py`, Cloudflare helpers) | **UPGRADE** | Engineer time | Terraform/Pulumi **REPLACE** only after T3.1 trade-off | **L** | Scripts-first reversible |

---

## Per-layer detail

### 1. Hosting — Vercel

**Current state**: Multiple product frontends (`apps/filefree`, `studio`, `launchfree`, `distill`, `axiomfolio`, `accounts`, `trinkets`, `design`) pin **Next.js 16.2.x** and **React 19.2.x** with shared workspace packages. Deployment is Vercel-native (not represented in `render.yaml`). `infra/state/vercel.yaml` exists as a **drift-detector target** but is **not yet populated** (`projects: []`).

**Alternatives evaluated**: Cloudflare Pages, Netlify, self-hosted Next on Hetzner/Fly — viable for cost control but lose tight integration with AI SDK / Analytics / preview UX unless rebuilt.

**Verdict**: **KEEP** — the team is already on a leading Next major; switching hosts is a distraction unless billing or compliance forces it.

**Cost**: **NEEDS_HUMAN** — confirm Hobby vs Pro, seat count, and included bandwidth vs overages from Vercel invoices.

**Effort**: **S** (ongoing version bumps).

**Reversibility**: Moving DNS and env vars to another host is **medium-to-large** operational work; application code stays portable.

### Hosting — Render

**Current state**: Single root **`render.yaml`** defines **filefree-api** (Python **Starter**, Oregon), **brain-api** (Docker, **`standard`** plan per file — **note**: `docs/infra/RENDER_INVENTORY.md` still lists brain as Starter; treat as **drift risk**), **axiomfolio** API + **two Celery workers** (**standard**), **Render Redis** (starter) and **managed Postgres** (`basic-1gb`) for AxiomFolio. **launchfree-api** is intentionally commented out (frontend still mock-backed).

**Alternatives evaluated**: Fly.io, Railway, ECS/Fargate (violates “zero AWS” doctrine unless explicitly reopened), GCP Cloud Run.

**Verdict**: **UPGRADE** — platform choice is fine; **execution** should improve: reduce deploy churn burn (`RENDER_QUOTA_AUDIT` shows heavy pipeline minutes from frequent superseded/failed builds), reconcile **inventory vs blueprint** for Brain plan tier, and finish LaunchFree API when product is ready (cost vs value).

**Cost**: **NEEDS_HUMAN** — sum Starter + Standard × N + DB + Redis + overages; quota audit gives methodology, not invoice totals.

**Effort**: **M** (policy + Render dashboard hygiene).

**Reversibility**: Services are git-backed; commenting blocks or rolling back blueprint is **one PR**, minus secrets re-binding.

### Hosting — Hetzner / self-hosted CI

**Current state**: Comments and workflows (`ci.yaml`, `vercel-prebuilt.yaml`, `chromatic.yaml`, `brain-golden-suite.yaml`) route selected jobs to **`[self-hosted, hetzner]`**. Langfuse stack lives under **`infra/hetzner/`** compose pattern.

**Alternatives evaluated**: Larger GH-hosted runners (simplest ops), moving builds entirely self-hosted (capacity planning).

**Verdict**: **KEEP** — aligns with cost-conscious build offload already wired.

**Cost**: ~**\$6–15/mo** CX-class VM plus maintenance; exact from Hetzner invoice.

**Effort**: **S**.

**Reversibility**: **High** — disable labels and fall back to `ubuntu-latest`.

### Hosting — Cloudflare (DNS anchor)

**Current state**: DNS reconciliation automation targets Cloudflare API (`reconcile_clerk_dns.py`, SPF/DMARC helpers). This is **authoritative DNS glue** for Clerk satellite cutovers and brand domains.

**Verdict**: **KEEP**.

**Cost**: Often negligible vs registrar; enterprise features **NEEDS_HUMAN**.

**Effort**: **S**.

**Reversibility**: NS migration away from Cloudflare is **possible but painful** (coordination with all satellite domains).

---

### 2. Frameworks — Next.js / React / Tailwind

**Current state**: **Next 16**, **React 19**, **Tailwind 4**, **TypeScript 5.6** across apps; Turbopack in dev scripts.

**Alternatives evaluated**: Remix, Vite SPA-only — rejected by monorepo standard (`AGENTS.md`).

**Verdict**: **KEEP** — versions are current-generation; stay on semver hygiene.

**Cost**: N/A (OSS).

**Effort**: **S** per upgrade wave.

**Reversibility**: Pin lockfile revert.

### Frameworks — FastAPI / Python

**Current state**: APIs declare **`fastapi>=0.136.1`** in requirements; uv/pyproject workspace for packaging discipline.

**Alternatives evaluated**: Django, NestJS — conflicts with **Brain-as-OS doctrine** (Python FastAPI for backends).

**Verdict**: **KEEP**.

**Effort**: **S**.

**Reversibility**: N/A within doctrine.

### Frameworks — Vercel AI SDK

**Current state**: FileFree depends on **`ai`**, **`@ai-sdk/react`**, **`@ai-sdk/openai`** current majors.

**Verdict**: **KEEP** — matches documented frontend AI UX patterns.

**Effort**: **S**.

**Reversibility**: Provider modules swappable within SDK ecosystem.

---

### 3. Auth — Clerk

**Current state**: Shared **`@paperwork-labs/auth-clerk`** package documents **SignInShell**, **SignUpShell**, **RequireAuth**, **`verifyClerkJwt`**, appearance presets. **`CLERK_SATELLITE_TOPOLOGY.md`** describes primary **`accounts.paperworklabs.com`** + satellites; explicitly notes cross-brand SSO **not fully realized** until Dashboard/DNS completion.

**Alternatives evaluated**: Auth0, Cognito, WorkOS — migration cost is high; Clerk matches Next-first DX.

**Verdict**: **NEEDS_HUMAN** — **KEEP** the vendor; **decisions pending** on satellite rollout completeness, **orgs/RBAC** for Studio vs consumer apps, **MFA** defaults, **webhooks** for lifecycle sync, and **JWT templates** for backend claims. Cannot verdict “done” from repo alone.

**Cost**: **NEEDS_HUMAN** — Clerk plan tier scales with MAU and satellite domain rules.

**Effort**: **M–L** for full satellite + org model.

**Reversibility**: **Low** once users rely on Clerk IDs across products.

---

### 4. DNS/CDN — Cloudflare (Workers, caching, transforms)

**Current state**: Infrastructure-as-scripts for **DNS**. No Wrangler worker sources, no exported Cache/Transform Rules YAML in-repo.

**Alternatives evaluated**: Cloudflare remains default CDN/DNS; evaluating Workers vs edge middleware on Next is product-specific.

**Verdict**: **NEEDS_HUMAN** — **dashboard audit required** to describe live **Workers**, **Page/Cache/Transform Rules**, and **Image Resizing**. Without exported config, any verdict on those features would be speculative.

**Cost**: Feature-dependent.

**Effort**: **S** for read-only export inventory.

**Reversibility**: Rule-level rollback.

---

### 5. Data — Neon, Upstash, GCS, vectors

**Current state**: Neon + Upstash referenced throughout APIs and `render.yaml`. GCS for document lifecycle per engineering doctrine. Brain stores embeddings **in Postgres** via **pgvector** (1536-dim) with OpenAI embedding model metadata — **no separate vector SaaS**.

**Alternatives evaluated**: Pinecone/Weaviate (adds \$ + sync); RDS (AWS off-strategy).

**Verdict**: **KEEP** — coherent serverless story; vectors colocated with transactional Brain data simplifies ops.

**Cost**: Usage-tiered; **NEEDS_HUMAN** for Neon/Upstash invoices vs free tiers.

**Effort**: **XS–S** for config; **L** only if migrating vector store.

**Reversibility**: Bucket/URL swaps vs pgvector migration difficulty differs — **vector migration is hard**.

---

### 6. AI — SDK, gateways, cost tracking

**Current state**: Consumer AI UX uses **Vercel AI SDK** + OpenAI. Brain wires **Langfuse** (`LANGFUSE_*` env, `observability.py`) for tracing and carries **multi-provider** secrets (OpenAI, Anthropic, Google). No checked-in **Vercel AI Gateway** routing config found in-repo (may exist only in Vercel Dashboard).

**Alternatives evaluated**: LiteLLM proxy, Helicone, centralized AI Gateway-only routing.

**Verdict**: **UPGRADE** — observability hook exists; **standardize** “every LLM path traced + cost attributed” and decide whether **AI Gateway** should front all providers for rate limits and keys rotation (needs human confirmation vs direct SDK).

**Cost**: Dominated by **model inference**, not tooling margin.

**Effort**: **M**.

**Reversibility**: **High** — toggle proxies/feature flags.

---

### 7. CI/CD — GitHub Actions

**Current state**: Large workflow surface (**38** files): merge automation, docs indexing, Brain guards, AxiomFolio CI, Chromatic, Lighthouse, axe, agent sprint runner, etc. **`ci.yaml`** uses **path filters** to skip unrelated builds. **Composite action** `vercel-prebuilt` exists; **reusable workflows** (`workflow_call`) are **scarce** — mostly copy/paste YAML.

**Alternatives evaluated**: CircleCI, Buildkite — unnecessary churn given GH-native repo.

**Verdict**: **UPGRADE** — extract repeated setup (pnpm cache, Python matrix, path-filter boilerplate) into **`workflow_call`** or shared composites; align self-hosted usage with concurrency caps documented in YAML comments.

**Cost**: GH Actions minutes + self-hosted amortization; **NEEDS_HUMAN** for true blended \$.

**Effort**: **M**.

**Reversibility**: **High**.

---

### 8. IaC & drift detection

**Current state**: **Render Blueprint** is the strongest declarative artifact. **Vercel** state file is a **stub**. Drift tooling is **emerging** (`iac_drift_seed.py` supports multiple surfaces) rather than Terraform/Pulumi mono-stack.

**Alternatives evaluated**: Pulumi or Terraform for Cloudflare + Vercel + Render — stronger blast-radius accounting; heavier upfront cost. Scripts + periodic drift jobs match current team size if enforced.

**Verdict**: **UPGRADE** — fill **`infra/state/vercel.yaml`** from live reconcile, extend drift checks, **defer full IaC framework** until T3.1 compares ROI vs scripts.

**Cost**: Engineer time >> license fees at current scale.

**Effort**: **L** for Terraform-class adoption; **M** for script maturity.

**Reversibility**: **High** for scripts; **medium** once Terraform state is authoritative.

---

## Open questions for founder (NEEDS_HUMAN verdicts)

1. **Vercel billing**: Exact monthly \$ (Pro tier? seat count? bandwidth overages?) and target number of production projects.
2. **Render billing**: Reconcile **brain-api** **Starter vs Standard** between live dashboard and `render.yaml`; confirm desired end-state.
3. **Clerk**: Timeline and scope for **satellite SSO** completion; do we need **organizations**, **step-up MFA**, and **webhooks** for Brain provisioning this quarter?
4. **Cloudflare dashboard**: Export or inventory **Workers / Rules / Image Resizing** actually enabled per zone (not visible in git).
5. **AI Gateway**: Should all server-side LLM calls route through **one** gateway/proxy for quotas and spend dashboards?
6. **Langfuse**: Confirm retention, backup, and whether self-hosted on Hetzner meets compliance expectations vs Langfuse Cloud.

---

## Out of scope (explicitly deferred)

- Executing migrations, vendor switches, or Terraform adoption (**T3.14**).
- Invoice-grade pricing math requiring Dashboard/API secrets not in the repo.
- Security penetration testing or formal SOC2 control mapping.
- Application-layer tax/compliance logic review (not infrastructure).
- **`packages/filing-engine`** TypeScript port decision (**T5.5**) beyond noting it exists.

---

## Not done in this PR

- No configuration or code changes — **documentation only**.
- No Cloudflare Dashboard crawl — Cloudflare layer flagged **NEEDS_HUMAN**.
- No Clerk Dashboard confirmation of enabled features beyond what docs/code imply.
