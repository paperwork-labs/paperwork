# FileFree — Architecture Reference

**Last updated**: 2026-03-10

A visual-first guide to how FileFree is built. Diagrams are rendered natively on GitHub.

---

## System Overview

```mermaid
graph TB
    subgraph client [Client]
        Browser["Browser / Mobile"]
    end

    subgraph vercel [Vercel]
        NextJS["Next.js 14 App Router<br/>filefree.tax"]
    end

    subgraph render [Render]
        FastAPI["FastAPI<br/>api.filefree.tax"]
    end

    subgraph datastores [Data Stores]
        Neon["Neon PostgreSQL"]
        Upstash["Upstash Redis<br/>Sessions + CSRF"]
    end

    subgraph gcp [Google Cloud Platform]
        Vision["Cloud Vision API<br/>OCR"]
        GCS["Cloud Storage<br/>Temp uploads, 24hr TTL"]
    end

    subgraph openai [OpenAI]
        GPT4oMini["GPT-4o-mini<br/>Field mapping"]
        GPT4o["GPT-4o Vision<br/>Fallback OCR"]
    end

    Browser -->|"HTTPS"| NextJS
    NextJS -->|"REST + cookies"| FastAPI
    FastAPI -->|"asyncpg"| Neon
    FastAPI -->|"redis-py"| Upstash
    FastAPI -->|"DOCUMENT_TEXT_DETECTION"| Vision
    FastAPI -->|"Structured output"| GPT4oMini
    FastAPI -->|"Vision fallback"| GPT4o
    FastAPI -->|"Upload / signed URL"| GCS
```

### Production Infrastructure

| Service | Provider | Plan | Domain |
|---------|----------|------|--------|
| Frontend | Vercel | Hobby | filefree.tax |
| Backend | Render | Starter ($7/mo) | api.filefree.tax |
| Database | Neon | Free tier | — |
| Sessions | Upstash | Free tier (500K cmd/mo) | — |
| File Storage | GCP Cloud Storage | Pay-per-use | — |
| OCR | GCP Cloud Vision | 1K free/mo, $0.0015/page | — |
| AI | OpenAI | Pay-per-use | — |
| Ops VPS | Hetzner | CX33 ($5.49/mo) | n8n / social.filefree.tax |

---

## Authentication Flow

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
    FastAPI->>Browser: Set-Cookie: session (httponly, secure, samesite=lax)<br/>Body: { csrf_token }

    note over Browser,PostgreSQL: Authenticated Request
    Browser->>FastAPI: GET /auth/me (cookie: session)
    FastAPI->>Redis: GET session:token
    Redis-->>FastAPI: user_id
    FastAPI->>PostgreSQL: SELECT user WHERE id = user_id
    FastAPI-->>Browser: UserResponse (email, name, referral_code)

    note over Browser,PostgreSQL: State-Changing Request (CSRF required)
    Browser->>FastAPI: POST /auth/logout (cookie + X-CSRF-Token header)
    FastAPI->>Redis: GET csrf:token → validate
    FastAPI->>Redis: DEL session:token, csrf:token
    FastAPI->>Browser: Clear cookie

    note over Browser,PostgreSQL: Account Deletion (CCPA)
    Browser->>FastAPI: DELETE /auth/account (cookie + X-CSRF-Token)
    FastAPI->>PostgreSQL: CASCADE delete user → filings → documents, profiles, calculations
    FastAPI->>Redis: DEL session + csrf
    FastAPI->>Browser: Clear cookie, 200 OK
```

### Auth Endpoints

| Method | Path | Auth | CSRF | Rate Limit | Description |
|--------|------|------|------|------------|-------------|
| POST | `/auth/register` | No | No | 5/min | Create account, set cookie |
| POST | `/auth/login` | No | No | 5/min | Verify credentials, set cookie |
| POST | `/auth/logout` | Yes | Yes | — | Clear session + cookie |
| GET | `/auth/me` | Yes | No | — | Return current user |
| DELETE | `/auth/account` | Yes | Yes | — | Delete all data (CCPA) |

---

## OCR Pipeline

```mermaid
flowchart TD
    Upload["W-2 Photo Upload"]
    Preprocess["Pillow Preprocessing<br/>EXIF rotate, contrast, resize"]
    CloudVision["GCP Cloud Vision<br/>DOCUMENT_TEXT_DETECTION<br/>$0.0015/page"]
    SSNExtract["Local SSN Extraction<br/>Regex: \\d{3}-?\\d{2}-?\\d{4}"]
    Scrub["Scrub SSN from text<br/>Replace with XXX-XX-XXXX"]
    GPT4oMini["GPT-4o-mini Structured Output<br/>Map scrubbed text → W-2 fields<br/>~$0.001/doc"]
    ConfCheck{"Confidence<br/>≥ 85%?"}
    GPT4oVision["GPT-4o Vision Fallback<br/>Send actual image<br/>~$0.02/doc"]
    Validate["Post-Validation<br/>SSN format, EIN format,<br/>wage amounts, cross-field checks"]
    Result["W2ExtractionResult<br/>All amounts in cents"]

    Upload --> Preprocess
    Preprocess --> CloudVision
    CloudVision --> SSNExtract
    SSNExtract --> Scrub
    Scrub --> GPT4oMini
    GPT4oMini --> ConfCheck
    ConfCheck -->|"Yes"| Validate
    ConfCheck -->|"No"| GPT4oVision
    GPT4oVision --> Validate
    Validate --> Result
```

### SSN Isolation

SSNs are extracted via regex locally from Cloud Vision text output. They are **never** sent to OpenAI or any LLM. The scrubbed text (with `XXX-XX-XXXX` placeholders) is what GPT receives. Google Cloud Vision does not store images or use them for training.

### Cost Model

| Tier | When Used | Cost/doc | % of Requests |
|------|-----------|----------|---------------|
| Tier 1 | Cloud Vision + GPT-4o-mini | ~$0.002 | ~90% |
| Tier 2 | GPT-4o vision fallback | ~$0.02 | ~10% |
| **Blended** | | **~$0.005** | |

---

## Data Model

```mermaid
erDiagram
    users ||--o{ filings : "has many"
    users ||--o{ users : "referred_by"
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
        uuid referred_by_id FK
        enum role
        enum advisor_tier
        enum auth_provider
        boolean email_verified
        jsonb attribution
    }

    filings {
        uuid id PK
        uuid user_id FK
        int tax_year
        enum filing_status_type
        enum status
        timestamp submitted_at
    }

    documents {
        uuid id PK
        uuid filing_id FK
        enum document_type
        string storage_key
        enum extraction_status
        jsonb extraction_data
        jsonb confidence_scores
        timestamp processed_at
    }

    tax_profiles {
        uuid id PK
        uuid filing_id FK
        string ssn_encrypted
        string full_name_encrypted
        jsonb address_encrypted
        string date_of_birth_encrypted
        int total_wages
        int total_federal_withheld
        int total_state_withheld
        string state
    }

    tax_calculations {
        uuid id PK
        uuid filing_id FK
        int adjusted_gross_income
        int standard_deduction
        int taxable_income
        int federal_tax
        int state_tax
        int total_withheld
        int refund_amount
        int owed_amount
        jsonb ai_insights
    }

    submissions {
        uuid id PK
        uuid filing_id FK
        string transmitter_partner
        string submission_id_external
        enum irs_status
        jsonb rejection_codes
        timestamp submitted_at
    }

    waitlist {
        uuid id PK
        string email UK
        string source
        jsonb attribution
    }
```

### Cascade Behavior

All child tables use `ON DELETE CASCADE` at the database level and `cascade="all, delete-orphan"` at the ORM level. Deleting a user cascades through filings to all child records — this powers the CCPA account deletion endpoint.

### PII Encryption

All personally identifiable fields (`full_name`, `ssn`, `address`, `date_of_birth`) are encrypted at rest using AES-256 (Fernet) with a separate key from database encryption. SSNs are never stored in plaintext anywhere.

---

## Local Development Stack

```mermaid
graph LR
    subgraph docker [Docker Compose — filefree]
        Postgres["filefree-postgres<br/>PostgreSQL 15<br/>:5432"]
        Redis["filefree-redis<br/>Redis 7<br/>:6379"]
        API["filefree-api<br/>FastAPI + Uvicorn<br/>:8000"]
        Web["filefree-web<br/>Next.js Dev<br/>:3000"]
    end

    Web -->|"depends_on healthy"| API
    API -->|"depends_on healthy"| Postgres
    API -->|"depends_on healthy"| Redis

    Dev["Developer"] -->|"localhost:3000"| Web
    Dev -->|"localhost:8000/docs"| API
```

### Quick Reference

```bash
make dev          # Start all services (foreground)
make dev-d        # Start all services (background)
make stop         # Stop all services
make test-local   # Run backend tests (no Docker)
make lint-local   # Run linters (no Docker)
make logs-api     # Tail API logs
make db           # Open psql shell
```

---

## Backend Structure

```
api/
├── app/
│   ├── main.py              # FastAPI app, lifespan, middleware, routes
│   ├── config.py             # Pydantic Settings (env vars)
│   ├── database.py           # SQLAlchemy async engine + session
│   ├── redis.py              # Async Redis pool lifecycle
│   ├── rate_limit.py         # Shared slowapi Limiter instance
│   ├── dependencies.py       # get_current_user, require_csrf
│   ├── models/               # SQLAlchemy models (User, Filing, Document, ...)
│   ├── schemas/              # Pydantic request/response models
│   ├── routers/              # FastAPI route handlers
│   ├── services/             # Business logic (auth, OCR, tax calc)
│   ├── repositories/         # Database access (repository pattern)
│   └── utils/                # Encryption, security, PII scrubbing, exceptions
├── alembic/                  # Database migrations
├── tax-data/                 # Tax brackets and deductions by year
├── tests/                    # pytest + pytest-asyncio
└── requirements.txt
```

---

## Request Flow

```mermaid
sequenceDiagram
    participant Browser
    participant NextJS as Next.js (Vercel)
    participant FastAPI as FastAPI (Render)
    participant DB as PostgreSQL (Neon)
    participant Cache as Redis (Upstash)

    Browser->>NextJS: Page request
    NextJS-->>Browser: SSR/static HTML

    Browser->>FastAPI: API call (cookie auth)
    FastAPI->>Cache: Validate session
    Cache-->>FastAPI: user_id
    FastAPI->>DB: Query data
    DB-->>FastAPI: Results
    FastAPI-->>Browser: JSON response
```
