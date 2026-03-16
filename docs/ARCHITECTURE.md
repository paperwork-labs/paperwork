# Paperwork Labs — Architecture Reference

**Last updated**: 2026-03-16

Visual-first guide to how Paperwork Labs products are built. Diagrams render natively on GitHub.

---

## System Overview

```mermaid
graph TB
    subgraph consumers [Consumer Products — Vercel]
        FF["FileFree<br/>filefree.ai<br/>:3001"]
        LF["LaunchFree<br/>launchfree.ai<br/>:3002"]
        TR["Trinkets<br/>tools.filefree.ai<br/>:3003"]
    end

    subgraph b2b [B2B Platform — Vercel]
        DI["Distill<br/>distill.tax<br/>:3005"]
    end

    subgraph internal [Internal — Vercel]
        ST["Studio<br/>paperworklabs.com<br/>:3004"]
    end

    subgraph apis [APIs — Render]
        FFAPI["FileFree API<br/>api.filefree.ai<br/>:8001"]
        LFAPI["LaunchFree API<br/>api.launchfree.ai<br/>:8002"]
        STAPI["Studio API<br/>api.paperworklabs.com<br/>:8003"]
    end

    subgraph datastores [Data Stores]
        Neon["Neon PostgreSQL<br/>Per-product DBs + Venture DB"]
        Upstash["Upstash Redis<br/>Sessions + CSRF"]
    end

    subgraph gcp [Google Cloud Platform]
        Vision["Cloud Vision API<br/>OCR"]
        GCS["Cloud Storage<br/>Temp uploads, 24hr TTL"]
    end

    subgraph ai [AI Providers]
        GPT["OpenAI GPT-4o / 4o-mini<br/>Field mapping, advisory"]
        Gemini["Gemini 2.5 Flash<br/>State data extraction"]
    end

    subgraph payments [Payments]
        Stripe["Stripe<br/>Consumer billing + Issuing"]
    end

    subgraph ops [Ops — Hetzner CX33]
        N8N["n8n<br/>Workflow automation"]
        Postiz["Postiz<br/>Social scheduler"]
    end

    FF --> FFAPI
    LF --> LFAPI
    DI --> FFAPI
    ST --> STAPI
    STAPI --> FFAPI
    STAPI --> LFAPI
    FFAPI --> Neon
    LFAPI --> Neon
    FFAPI --> Upstash
    LFAPI --> Upstash
    FFAPI --> Vision
    FFAPI --> GPT
    LFAPI --> Gemini
    LFAPI --> Stripe
    FFAPI --> GCS
    N8N --> STAPI
```

### Production Infrastructure

| Service | Provider | Cost | Domain |
|---------|----------|------|--------|
| Frontend (5 apps) | Vercel | Hobby → $20/mo Pro | filefree.ai, launchfree.ai, distill.tax, paperworklabs.com, tools.filefree.ai |
| Backend (FileFree + Distill) | Render | $7/mo Starter | api.filefree.ai |
| Backend (LaunchFree) | Render | $7/mo Starter | api.launchfree.ai |
| Backend (Studio) | Render | $7/mo Starter | api.paperworklabs.com |
| Portal Automation Worker | Render | $7/mo | — (Playwright headless) |
| Database | Neon | Free tier (0.5 GB) | — |
| Sessions | Upstash | Free tier (500K cmd/mo) | — |
| File Storage | GCP Cloud Storage | Pay-per-use | — |
| OCR | GCP Cloud Vision | 1K free/mo, $0.0015/page | — |
| AI | OpenAI + Gemini | Pay-per-use | — |
| Payments | Stripe | Standard + Issuing | — |
| Ops VPS | Hetzner CX33 | $6/mo | n8n.paperworklabs.com |

---

## Monorepo Structure

```
venture/
  apps/
    filefree/               # filefree.ai — Next.js, consumer tax filing
    launchfree/             # launchfree.ai — Next.js, LLC formation
    distill/                # distill.tax — Next.js, B2B compliance SaaS
    studio/                 # paperworklabs.com — Next.js, command center
    trinkets/               # tools.filefree.ai — Next.js SSG, utility tools
  packages/
    ui/                     # shadcn components + 4 brand themes
    auth/                   # shared auth hooks, middleware, session
    analytics/              # PostHog + attribution + PII scrubbing
    data/                   # 50-state configs (formation + tax + compliance)
      formation/{state}.json
      tax/{year}.json
      compliance/{state}.json
    tax-engine/             # tax calculation, form generators, MeF XML
    document-processing/    # OCR pipeline, field extraction, bulk upload
    filing-engine/          # State Filing Engine (portal automation, APIs, mail)
    intelligence/           # financial profiles, recommendations, campaigns
    email/                  # shared email templates (React Email)
  apis/
    filefree/               # FastAPI — consumer tax + Distill B2B routes
    launchfree/             # FastAPI — formation service
    studio/                 # FastAPI — command center aggregator
  infra/
    compose.dev.yaml        # Docker Compose (local dev)
    hetzner/                # n8n + Postiz ops stack
    render.yaml             # Render Blueprints IaC
  docs/                     # All documentation
```

---

## Shared Infrastructure Layer

The core architectural insight: consumer products and B2B APIs consume the same shared packages. Building LaunchFree's Filing Engine simultaneously creates Distill's Formation API. Building FileFree's tax engine simultaneously creates Distill's Tax API.

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
        AUTH["packages/auth<br/>Session + middleware"]
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

## Federated Identity

Each product owns its own user table in its own database. The venture layer adds SSO and cross-product intelligence on top but is fully removable without breaking any product.

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

## Authentication

### Consumer Auth (FileFree, LaunchFree)

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

### B2B Auth (Distill)

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

## OCR Pipeline (FileFree + Distill)

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

## State Filing Engine (LaunchFree + Distill Formation API)

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

## Data Models

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

## Agent Operations Architecture

AI agents are the operations team. They maintain the 50-state data layer, monitor infrastructure health, and handle ongoing codebase maintenance.

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

---

## Local Development

```mermaid
graph LR
    subgraph docker [Docker Compose — venture]
        PG["PostgreSQL 15<br/>:5432"]
        RD["Redis 7<br/>:6379"]
        FFAPI["FileFree API<br/>:8001"]
        LFAPI["LaunchFree API<br/>:8002"]
        STAPI["Studio API<br/>:8003"]
    end

    subgraph apps [pnpm dev — separate terminals]
        FFWEB["apps/filefree :3001"]
        LFWEB["apps/launchfree :3002"]
        TRWEB["apps/trinkets :3003"]
        STWEB["apps/studio :3004"]
        DIWEB["apps/distill :3005"]
    end

    FFWEB --> FFAPI
    LFWEB --> LFAPI
    DIWEB --> FFAPI
    STWEB --> STAPI
    FFAPI --> PG & RD
    LFAPI --> PG & RD
    STAPI --> PG & RD
```

### Port Map

| Service | Port |
|---------|------|
| apps/filefree | 3001 |
| apps/launchfree | 3002 |
| apps/trinkets | 3003 |
| apps/studio | 3004 |
| apps/distill | 3005 |
| apis/filefree | 8001 |
| apis/launchfree | 8002 |
| apis/studio | 8003 |
| PostgreSQL | 5432 |
| Redis | 6379 |

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

## Production Reliability

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
