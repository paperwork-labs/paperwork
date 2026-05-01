---
owner: engineering
last_reviewed: 2026-04-24
doc_kind: architecture
domain: company
status: active
---
# Architecture Reference

**Last updated**: 2026-04-24

Visual guide to how products are built. Diagrams render on GitHub. For **live deploy vs. blueprint drift** (AxiomFolio repo pointer, `launchfree-api` presence, etc.), see [docs/infra/RENDER_INVENTORY.md](docs/infra/RENDER_INVENTORY.md).

## TL;DR

- **Shape**: One monorepo: [`apps/`](../apps) (Vercel), [`apis/`](../apis) (Render), shared [`packages/`](../packages). [Studio](../apps/studio) → [Brain](../apis/brain) (LLM, personas, tools); [filefree](../apis/filefree), [launchfree](../apis/launchfree), and [axiomfolio](../apis/axiomfolio) are the product backends. Postgres, Redis, and vendor keys per [INFRA.md](INFRA.md).
- **Constraint**: **Multi-tenant and product boundaries are explicit** — no cross-tenant or cross-product data access without the app-layer scopes in [BRAIN_ARCHITECTURE.md](BRAIN_ARCHITECTURE.md) and each product’s auth model; never bypass session/API-key checks.
- **In flight** (Q2 2026): [Docs streamline & frontmatter](DOCS_STREAMLINE_2026Q2.md) across `docs/`; AxiomFolio **Render services still point at the legacy `paperwork-labs/axiomfolio` repo** — repoint to the monorepo and sync [apis/axiomfolio/render.yaml](https://github.com/paperwork-labs/paperwork/blob/main/apis/axiomfolio/render.yaml) per [docs/infra/RENDER_INVENTORY.md](docs/infra/RENDER_INVENTORY.md#f-1--four-axiomfolio--services-still-point-to-the-old-standalone-repo-).

## Production system map (Vercel, Render, data)

**Request path (scannable):** [Studio `apps/studio`](../apps/studio) (UI) → [Brain `apis/brain`](../apis/brain) (orchestration, [personas](../apis/brain/app/personas)) → product APIs; Studio also **health-probes** FileFree/LaunchFree endpoints from [command-center.ts](../apps/studio/src/lib/command-center.ts). Product UIs call their own APIs directly. **Do not** assume a separate `apis/studio` service — it does not exist in this repo.

```
  ┌──────────────┐     ┌─────────────────┐     Personas: apis/brain/app/personas/
  │ Studio (UI)  │───▶│  Brain API      │     (routing + .mdc specs)
  │ Vercel :3004 │     │  Render/8003*   │            │
  └──────┬───────┘     └────────┬────────┘            ▼
         │                    │            ┌────────────────┐
         │ health / admin       ├───────────▶│ AxiomFolio API│──▶ Neon + Redis
         ├─▶ filefree/launchfree│            │ apis/axiomfolio│    (dedicated
         ▼   APIs (Render)     │            └────────────────┘     Render DB)
  ┌────────────┐  ┌───────────┴──────────┐
  │FileFree API│  │LaunchFree API        │
  │ :8001      │  │ :8002                 │
  └─────┬──────┘  └──────────┬──────────┘
        │                    │
        └────────┬───────────┘
                 ▼
        Neon, Upstash, GCS, Vision, OpenAI, Gemini, Stripe, …
        (* host port from [infra/compose.dev.yaml](../infra/compose.dev.yaml) — see Local dev)
```

```mermaid
graph TB
    subgraph consumers [Consumer products — Vercel]
        FF["FileFree<br/>filefree.ai<br/>:3001"]
        LF["LaunchFree<br/>launchfree.ai<br/>:3002"]
        TR["Trinkets<br/>tools.filefree.ai<br/>:3003"]
    end

    subgraph b2b [B2B — Vercel]
        DI["Distill<br/>distill.tax<br/>:3005"]
    end

    subgraph internal [Internal — Vercel]
        ST["Studio<br/>paperworklabs.com<br/>:3004"]
    end

    subgraph brainlayer [Command center — Render]
        BRAIN["Brain API<br/>brain.paperworklabs.com"]
    end

    subgraph apis [Product APIs — Render]
        FFAPI["FileFree API<br/>api.filefree.ai"]
        LFAPI["LaunchFree API"]
        XFAPI["AxiomFolio API<br/>apis/axiomfolio"]
    end

    subgraph datastores [Data stores]
        Neon["Neon PostgreSQL<br/>Per-product + Brain"]
        Upstash["Upstash Redis<br/>Sessions + CSRF + Brain cache"]
    end

    subgraph gcp [Google Cloud]
        Vision["Cloud Vision<br/>OCR"]
        GCS["Cloud Storage<br/>Temp uploads, 24h TTL"]
    end

    subgraph aimodels [Model providers]
        GPT["OpenAI<br/>4o / 4o-mini"]
        Gemini["Google Gemini"]
    end

    subgraph payments [Payments]
        Stripe["Stripe<br/>Billing + Issuing"]
    end

    subgraph ops [Ops — Hetzner]
        N8N["n8n<br/>Workflows"]
        Postiz["Postiz<br/>Social"]
    end

    FF --> FFAPI
    LF --> LFAPI
    ST --> BRAIN
    ST --> FFAPI
    ST --> LFAPI
    BRAIN --> XFAPI
    FFAPI --> Neon
    LFAPI --> Neon
    BRAIN --> Neon
    XFAPI --> Neon
    FFAPI --> Upstash
    LFAPI --> Upstash
    BRAIN --> Upstash
    FFAPI --> Vision
    FFAPI --> GPT
    LFAPI --> Gemini
    LFAPI --> Stripe
    FFAPI --> GCS
    N8N --> BRAIN
```

[apps/distill](../apps/distill) is a **stub B2B UI** (no API calls in tree yet); the historical pattern “Distill B2B shares FileFree’s backend” is a product intent, not a verified wire in the current `apps/distill` code.

### Where production runs

| Layer | Code / docs | Where it runs |
|-------|---------------|---------------|
| **Frontends** | [apps/filefree](../apps/filefree), [apps/launchfree](../apps/launchfree), [apps/trinkets](../apps/trinkets), [apps/studio](../apps/studio), [apps/distill](../apps/distill), [apps/axiomfolio](../apps/axiomfolio) | Vercel (per app) |
| **FileFree API** | [apis/filefree](../apis/filefree) | Render → api.filefree.ai (consumer; B2B direction shares this API) |
| **LaunchFree API** | [apis/launchfree](../apis/launchfree) | Render (see note below) |
| **Brain API** (Studio command center, LLM, personas) | [apis/brain](../apis/brain) | Render → `https://brain.paperworklabs.com` ([`render.yaml`](../render.yaml)) |
| **AxiomFolio** | [apis/axiomfolio](../apis/axiomfolio) | Render ([`apis/axiomfolio/render.yaml`](../apis/axiomfolio/render.yaml)) |
| **Data & cache** | [INFRA.md](INFRA.md) | Neon, Upstash, per-Blueprint Redis/Postgres on Render |
| **Vendors** | wired per service | GCS, Cloud Vision, Stripe, OpenAI, Gemini, Anthropic, … |
| **Ops automation** | [infra/hetzner](../infra/hetzner) | Hetzner: n8n, Postiz, … |

<!-- STALE 2026-04-24: LaunchFree — [RENDER_INVENTORY F-2](docs/infra/RENDER_INVENTORY.md#f-2--launchfree-api-is-defined-in-renderyaml-but-not-deployed): `launchfree-api` in root `render.yaml` may be absent in live Render. Studio’s default health URL is `https://launchfree-api.onrender.com` in [command-center.ts](../apps/studio/src/lib/command-center.ts). -->

<!-- STALE 2026-04-24: AxiomFolio on Render — [RENDER_INVENTORY F-1](docs/infra/RENDER_INVENTORY.md#f-1--four-axiomfolio--services-still-point-to-the-old-standalone-repo-): live `axiomfolio-*` services may still use repo `paperwork-labs/axiomfolio` until repointed; monorepo `apis/axiomfolio/` is the current source tree. -->

---

## Monorepo layout (repo root)

The Git root is the monorepo (there is no `venture/` directory — that name appears only in older docs). High-level:

```
  apps/           # Next.js (and product UIs) — e.g. filefree, launchfree, studio, trinkets, distill, axiomfolio
  apis/           # FastAPI: filefree, launchfree, brain, axiomfolio  (no apis/studio)
  packages/       # shared libraries (ui, data, tax-engine, …)
  infra/          # [compose.dev.yaml](../infra/compose.dev.yaml) — single dev stack; see [INFRA.md](INFRA.md)
  docs/           # this tree
  render.yaml     # root Render Blueprint (brain-api, filefree-api, launchfree-api, …)
```

Layout matches [INFRA.md](INFRA.md) (single `docker compose -f infra/compose.dev.yaml` dev stack, per-app DBs on one Postgres). Product listing: [pnpm-workspace.yaml](../pnpm-workspace.yaml).

---

## Shared packages: one engine, many surfaces

Consumer and B2B surfaces pull from the same [`packages/`](../packages) libraries (tax engine, filing engine, `document-processing`, shared `data`, UI, auth), so one implementation funds multiple product routes.

```mermaid
flowchart TB
    subgraph consumers [Consumer Products]
        FF["FileFree"]
        LF["LaunchFree"]
        TR["Trinkets"]
    end

    subgraph shared [Shared Packages]
        TE["packages/tax-engine<br/>Tax calc, forms, MeF"]
        FE["packages/filing-engine<br/>Portal automation, APIs, mail"]
        DP["packages/document-processing<br/>OCR, extraction, bulk upload"]
        SD["packages/data<br/>50-state configs"]
        UI["packages/ui<br/>Components + themes"]
        AUTH["@paperwork-labs/auth-clerk: shared Clerk wrappers + JWT verifier (Node + Python sidecar) + per-app Appearance factory"]
    end

    subgraph b2b [Distill B2B Platform]
        DCPA["CPA SaaS Dashboard"]
        DFORM["Formation API"]
        DTAX["Tax API"]
        DCOMP["Compliance API"]
    end

    subgraph agents [Agent Operations]
        CURSOR["Cursor Agents<br/>Code + features"]
        N8N["n8n Workflows<br/>State data + monitoring"]
    end

    FF --> TE & DP & UI & AUTH
    LF --> FE & SD & UI & AUTH
    TR --> TE & SD & UI
    DCPA --> DP & TE & UI & AUTH
    DFORM --> FE & SD
    DTAX --> TE
    DCOMP --> SD
    N8N -->|"auto-update"| SD
    N8N -->|"health check"| FE
    CURSOR -->|"maintain"| TE & FE & DP
```

---

## Per-product identity (optional venture link)

Each product owns its own user table in its own database. A venture layer can add SSO and cross-product intelligence; it must remain **optional** so products stay separable.

```mermaid
erDiagram
    venture_identities ||--o{ identity_products : "links to"
    venture_identities ||--o{ user_events : "tracks"
    venture_identities ||--o{ user_segments : "computed"

    venture_identities {
        uuid id PK
        string email UK
        string name
        timestamp created_at
    }

    identity_products {
        uuid venture_identity_id FK
        string product
        uuid product_user_id
        timestamp first_used
    }

    user_events {
        uuid id PK
        uuid venture_identity_id FK
        string event_type
        string product
        jsonb metadata
        timestamp timestamp
    }

    user_segments {
        uuid venture_identity_id FK
        string segment
        timestamp computed_at
    }
```

**Product databases** (independent, can be separated):

```
filefree DB:
  users: id, email, name, password_hash, ...filefree-specific...
         venture_identity_id (OPTIONAL, nullable FK)

launchfree DB:
  users: id, email, name, password_hash, ...launchfree-specific...
         venture_identity_id (OPTIONAL, nullable FK)
```

If FileFree is acquired: remove the `venture_identity_id` column. FileFree still works independently.

---

## Auth patterns (session cookies vs B2B API key)

### Consumer (FileFree, LaunchFree) — cookie session + CSRF

Implemented in [apis/filefree](../apis/filefree) / [apis/launchfree](../apis/launchfree) (see routers under `app/routers/`).

```mermaid
sequenceDiagram
    participant Browser
    participant FastAPI
    participant Redis
    participant PostgreSQL

    note over Browser,PostgreSQL: Registration
    Browser->>FastAPI: POST /auth/register
    FastAPI->>PostgreSQL: Create user (email, hash, encrypted name)
    FastAPI->>Redis: SETEX session:token user_id TTL=7d
    FastAPI->>Redis: SETEX csrf:token csrf_value TTL=7d
    FastAPI->>Browser: Set-Cookie httponly secure samesite=lax + csrf_token

    note over Browser,PostgreSQL: Authenticated Request
    Browser->>FastAPI: GET /api/v1/... (cookie)
    FastAPI->>Redis: GET session:token
    Redis-->>FastAPI: user_id
    FastAPI->>PostgreSQL: Query
    FastAPI-->>Browser: JSON response

    note over Browser,PostgreSQL: Account Deletion (CCPA)
    Browser->>FastAPI: DELETE /auth/account (cookie + CSRF)
    FastAPI->>PostgreSQL: CASCADE delete all user data
    FastAPI->>Redis: DEL session + csrf
    FastAPI->>Browser: Clear cookie, 200 OK
```

### B2B (Distill) — API key, firm-scoped

<!-- STALE 2026-04-24: The sequence below is the **intended** Distill B2B pattern. Grep did not find `/api/v1/pro/` in [apis/filefree](../apis/filefree) — re-verify before copying paths into runbooks. -->

Target: tenant-isolated, API-key access to the same document/tax **capabilities** as FileFree (as productized B2B routes on the FileFree or follow-on API surface).

```mermaid
sequenceDiagram
    participant Client as API Client
    participant FastAPI
    participant PostgreSQL

    note over Client,PostgreSQL: API Key Authentication
    Client->>FastAPI: POST /api/v1/pro/... (Authorization: Bearer api_key)
    FastAPI->>PostgreSQL: Lookup api_key → firm_id
    FastAPI->>FastAPI: Inject firm_id into request scope
    FastAPI->>PostgreSQL: Query (WHERE firm_id = scoped_firm_id)
    FastAPI-->>Client: JSON response (tenant-isolated)
```

---

## Document OCR and extraction (FileFree + Distill)

```mermaid
flowchart TD
    Upload["Document Upload<br/>W-2, 1099, etc."]
    Preprocess["Pillow Preprocessing<br/>EXIF rotate, contrast, resize"]
    CloudVision["GCP Cloud Vision<br/>DOCUMENT_TEXT_DETECTION<br/>$0.0015/page"]
    SSNExtract["Local PII Extraction<br/>SSN/EIN regex — never leaves server"]
    Scrub["Scrub PII from text<br/>Replace with XXX-XX-XXXX"]
    GPT4oMini["GPT-4o-mini Structured Output<br/>Map scrubbed text to fields<br/>~$0.001/doc"]
    ConfCheck{"Confidence<br/>≥ 85%?"}
    GPT4oVision["GPT-4o Vision Fallback<br/>Send actual image<br/>~$0.02/doc"]
    Validate["Post-Validation<br/>Format checks, cross-field"]
    Result["ExtractionResult<br/>All amounts in cents"]

    Upload --> Preprocess --> CloudVision --> SSNExtract --> Scrub --> GPT4oMini --> ConfCheck
    ConfCheck -->|"Yes"| Validate
    ConfCheck -->|"No"| GPT4oVision --> Validate
    Validate --> Result
```

| Tier | When Used | Cost/doc | % of Requests |
|------|-----------|----------|---------------|
| Tier 1 | Cloud Vision + GPT-4o-mini | ~$0.002 | ~90% |
| Tier 2 | GPT-4o vision fallback | ~$0.02 | ~10% |
| **Blended** | | **~$0.005** | |

---

## State Filing Engine (LaunchFree + Distill formation API)

```mermaid
flowchart TD
    Request["Formation Request<br/>User or API client"]
    Orchestrator["Filing Orchestrator<br/>packages/filing-engine"]
    Config["State Config Lookup<br/>packages/data/formation/{state}.json"]
    TierCheck{"State Filing<br/>Tier?"}

    Tier1["Tier 1: State API<br/>Delaware ICIS, etc.<br/>Direct API submission"]
    Tier2["Tier 2: Portal Automation<br/>Playwright headless browser<br/>~45 states"]
    Tier3["Tier 3: Print-and-Mail<br/>Lob API for ~2 mail-only states"]

    Payment["Stripe Issuing<br/>Virtual card for state filing fee"]
    Track["Filing Status Tracker<br/>Poll state portal or parse email"]
    Result["FilingSubmission record<br/>Status: submitted → confirmed"]

    Request --> Orchestrator --> Config --> TierCheck
    TierCheck -->|"API available"| Tier1
    TierCheck -->|"Online portal"| Tier2
    TierCheck -->|"Mail only"| Tier3
    Tier1 & Tier2 & Tier3 --> Payment --> Track --> Result
```

### Tier Breakdown

| Tier | Method | States | Marginal Cost | Example |
|------|--------|--------|---------------|---------|
| 1 | State API | ~3-5 (Delaware ICIS, etc.) | ~$0 + filing fee | Delaware |
| 2 | Playwright automation | ~45 | ~$0.25 compute + filing fee | California, Texas, New York |
| 3 | Print-and-mail (Lob) | ~2 | ~$1.50 postage + filing fee | Maine |

**Dual-use**: Same engine serves LaunchFree (consumer, $0 service fee) and Distill Formation API (B2B, $20-40/filing).

---

## Data models (by product)

### FileFree (Tax)

```mermaid
erDiagram
    users ||--o{ filings : "has many"
    filings ||--o{ documents : "has many"
    filings ||--o| tax_profiles : "has one"
    filings ||--o| tax_calculations : "has one"
    filings ||--o| submissions : "has one"

    users {
        uuid id PK
        string email UK
        string password_hash
        string full_name_encrypted
        string referral_code UK
        uuid venture_identity_id FK
    }

    filings {
        uuid id PK
        uuid user_id FK
        int tax_year
        enum status
    }

    documents {
        uuid id PK
        uuid filing_id FK
        enum document_type
        jsonb extraction_data
        jsonb confidence_scores
    }

    tax_calculations {
        uuid id PK
        uuid filing_id FK
        int adjusted_gross_income
        int taxable_income
        int federal_tax
        int refund_amount
        int owed_amount
    }
```

### LaunchFree (Formation)

```mermaid
erDiagram
    users ||--o{ formations : "has many"
    formations ||--o| filing_submissions : "has one"
    formations ||--o{ compliance_items : "has many"

    formations {
        uuid id PK
        uuid user_id FK
        string state
        string llc_name
        enum status
        jsonb documents_generated
    }

    filing_submissions {
        uuid id PK
        uuid formation_id FK
        enum tier
        enum status
        string tracking_id
        jsonb state_response
        timestamp submitted_at
    }

    state_portal_configs {
        string state_code PK
        enum tier
        string portal_url
        int filing_fee_cents
        jsonb automation_script_ref
        timestamp last_verified
    }

    compliance_items {
        uuid id PK
        uuid formation_id FK
        string item_type
        date due_date
        enum status
    }
```

### Distill (B2B)

```mermaid
erDiagram
    firms ||--o{ firm_members : "has many"
    firms ||--o{ clients : "has many"
    firms ||--o{ api_keys : "has many"
    clients ||--o{ documents : "has many"

    firms {
        uuid id PK
        string name
        string plan
        timestamp created_at
    }

    api_keys {
        uuid id PK
        uuid firm_id FK
        string key_hash
        string label
        int rate_limit
        boolean active
    }

    clients {
        uuid id PK
        uuid firm_id FK
        string name
        string email
    }
```

---

## Ops agents (Cursor, n8n)

**Cursor** for repo work; **n8n** on Hetzner for schedules and webhooks. The **LLM + agent loop** for the command center is in [apis/brain](https://github.com/paperwork-labs/paperwork/tree/main/apis/brain) ([`render.yaml`](../render.yaml) `brain-api`); n8n is a channel adapter, not the primary “brain” (see [BRAIN_ARCHITECTURE.md](BRAIN_ARCHITECTURE.md) D1–D2).

```mermaid
flowchart LR
    subgraph triggers [Triggers]
        CRON["n8n Cron Schedules"]
        WEBHOOK["Slack / Email Alerts"]
        MANUAL["Founder Request"]
    end

    subgraph agents [Agent Layer]
        CURSOR["Cursor Agents<br/>Code changes, features, fixes"]
        N8N_WF["n8n Workflows<br/>Automated operations"]
    end

    subgraph tasks [Maintenance Tasks]
        STATEDATA["50-State Data Refresh<br/>Monitor SOS websites for fee/form changes"]
        PORTALHEALTH["Portal Health Monitoring<br/>Test automation scripts against live portals"]
        CODEFIX["Code Maintenance<br/>Bug fixes, dependency updates, feature builds"]
        COMPLIANCE["Compliance Calendar<br/>Track deadlines, send alerts"]
    end

    subgraph outputs [Outputs]
        PR["GitHub PRs<br/>Code changes via branches"]
        SLACK["Slack Notifications<br/>#filing-engine, #dev"]
        CONFIGS["Updated JSON Configs<br/>packages/data/"]
    end

    CRON --> N8N_WF
    WEBHOOK --> CURSOR
    MANUAL --> CURSOR
    N8N_WF --> STATEDATA & PORTALHEALTH & COMPLIANCE
    CURSOR --> CODEFIX
    STATEDATA --> CONFIGS --> PR
    PORTALHEALTH --> SLACK
    CODEFIX --> PR
    COMPLIANCE --> SLACK
```

### Agent Maintenance Cadence

| Task | Frequency | Agent | Output |
|------|-----------|-------|--------|
| State fee/form change detection | Weekly | n8n + Gemini | Updated `packages/data/formation/*.json` |
| Portal automation health check | Daily | n8n + Playwright | Slack alert if script fails |
| Filing Engine status check | Hourly | n8n | Slack alert for stuck/failed submissions |
| Tax bracket updates | Annually (October) | Cursor agent | Updated `packages/data/tax/*.json` |
| Dependency updates | Monthly | Cursor agent | PR with updated packages |
| Compliance deadline alerts | Daily | n8n | Slack + email to affected users |

<!-- STALE 2026-04-24: Agent cadence (models per row) — re-verify “n8n + Gemini” for state/fee detection against the workflows checked into [infra/hetzner](../infra/hetzner) and n8n. -->

---

## Local development ([`infra/compose.dev.yaml`](../infra/compose.dev.yaml))

Host port map and service names match [INFRA.md](INFRA.md) (`postgres` **5433**, `redis` **6380** on the host — not 5432/6379).

```mermaid
graph LR
    subgraph docker [Docker Compose]
        PG["Postgres 17<br/>host :5433"]
        RD["Redis 7<br/>host :6380"]
        FFAPI["api-filefree<br/>:8001"]
        LFAPI["api-launchfree<br/>:8002"]
        BRAPI["api-brain<br/>:8003"]
        XFAPI["api-axiomfolio<br/>:8004"]
    end

    subgraph apps [Frontends — pnpm, separate terminals]
        FFWEB["apps/filefree :3001"]
        LFWEB["apps/launchfree :3002"]
        TRWEB["apps/trinkets :3003"]
        STWEB["apps/studio :3004"]
        DIWEB["apps/distill :3005"]
    end

    FFWEB --> FFAPI
    LFWEB --> LFAPI
    DIWEB --> FFAPI
    STWEB --> BRAPI
    FFAPI --> PG & RD
    LFAPI --> PG & RD
    BRAPI --> PG & RD
    XFAPI --> PG & RD
```

### Port map (see [INFRA.md](INFRA.md) for full table)

| Service | Host port |
|---------|-----------|
| apps/filefree | 3001 |
| apps/launchfree | 3002 |
| apps/trinkets | 3003 |
| apps/studio | 3004 |
| apps/distill | 3005 |
| apis/filefree | 8001 |
| apis/launchfree | 8002 |
| apis/brain | 8003 |
| apis/axiomfolio | 8004 |
| postgres | 5433 |
| redis | 6380 |

### Quick Reference

```bash
make dev          # Start Docker services + all apps
make dev-d        # Start Docker services (background)
make stop         # Stop all services
make test         # Run all tests
make lint         # Run all linters
make format       # Auto-fix formatting
make migrate      # Run Alembic migrations (all APIs)
```

---

## Degradation behavior and PII

### Circuit Breakers

| External Service | Degradation Behavior |
|-----------------|---------------------|
| GCP Cloud Vision | Return "manual entry required" — user types fields |
| OpenAI GPT | Skip AI insights, show static tips. OCR falls back to manual. |
| Stripe | Queue payment, retry with exponential backoff |
| State Portal (Filing Engine) | Queue submission, alert via Slack, manual fallback |
| Neon PostgreSQL | App returns 503, retry after 30s |
| Upstash Redis | Fall back to stateless JWT (no session revocation) |

### PII Encryption

All personally identifiable fields (`full_name`, `ssn`, `ein`, `address`, `date_of_birth`) are encrypted at rest using AES-256 (Fernet) with a key separate from database encryption. PII is never stored in plaintext. PII is never logged.

---

## Related docs

- [INFRA.md](INFRA.md) — single dev compose, ports, and per-app databases.
- [BRAIN_ARCHITECTURE.md](BRAIN_ARCHITECTURE.md) — Brain API, memory, personas, and agent loop.
- [philosophy/INFRA_PHILOSOPHY.md](philosophy/INFRA_PHILOSOPHY.md) — why infra is split the way it is.
- [philosophy/BRAIN_PHILOSOPHY.md](philosophy/BRAIN_PHILOSOPHY.md) — product philosophy for the Brain.
- [axiomfolio/ARCHITECTURE.md](axiomfolio/ARCHITECTURE.md) — AxiomFolio (portfolio / trading data plane).
  
There is no `MEDALLION_ARCHITECTURE.md` at the repo root; medallion details live under [docs/axiomfolio/](axiomfolio/) and related data docs.
