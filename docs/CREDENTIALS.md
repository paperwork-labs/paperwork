# FileFree Credential Registry

Single source of truth for every credential across all systems. QA audits against this document. Any new credential MUST be added here before merge.

**Last Updated**: 2026-03-08

---

## Core Infrastructure

| Credential | Purpose | Systems | Where Configured | Rotation Policy | Owner |
|---|---|---|---|---|---|
| `DATABASE_URL` | Neon PostgreSQL connection string | Backend API | Render dashboard | On compromise | Engineering |
| `REDIS_URL` | Upstash Redis connection string | Backend API | Render dashboard | On compromise | Engineering |
| `SECRET_KEY` | JWT/session signing key | Backend API | Render dashboard (auto-generated) | On compromise | Engineering |
| `ENCRYPTION_KEY` | AES-256 PII encryption at rest | Backend API | Render dashboard | On compromise, requires re-encryption | Engineering |

## OAuth

| Credential | Purpose | Systems | Where Configured | Rotation Policy | Owner |
|---|---|---|---|---|---|
| `GOOGLE_CLIENT_ID` | Google Sign In (server validation) | Backend API, Frontend | Render dashboard (API), Vercel dashboard (Web as `NEXT_PUBLIC_GOOGLE_CLIENT_ID`) | Annual or on compromise | Engineering |
| `GOOGLE_CLIENT_SECRET` | Google OAuth server-side token exchange | Backend API | Render dashboard | Annual or on compromise | Engineering |
| `APPLE_CLIENT_ID` | Apple Sign In | Backend API, Frontend | Render dashboard (API), Vercel dashboard (Web as `NEXT_PUBLIC_APPLE_CLIENT_ID`) | Annual or on compromise | Engineering |
| `APPLE_TEAM_ID` | Apple Developer Team ID | Backend API | Render dashboard | Rarely changes | Engineering |
| `APPLE_KEY_ID` | Apple Sign In key identifier | Backend API | Render dashboard | When key is rotated | Engineering |
| `APPLE_PRIVATE_KEY_PATH` | Path to Apple Sign In private key file | Backend API | Render dashboard (mounted file or env var) | Annual | Engineering |
| `NEXT_PUBLIC_APPLE_REDIRECT_URI` | Apple OAuth callback URL | Frontend | Vercel dashboard | On domain change | Engineering |

## AI / ML Pipeline

| Credential | Purpose | Systems | Where Configured | Rotation Policy | Owner |
|---|---|---|---|---|---|
| `OPENAI_API_KEY` | GPT-4o-mini field mapping, GPT-4o vision fallback, AI insights | Backend API, n8n agents | Render dashboard (API), n8n credential store (agents) | Monthly or on compromise | Engineering |
| `GOOGLE_APPLICATION_CREDENTIALS` | GCP Cloud Vision OCR + Cloud Storage | Backend API | Render dashboard (service account JSON path) | Annual, rotate service account key | Engineering |
| `GCS_BUCKET_NAME` | Cloud Storage bucket for W-2 uploads | Backend API | Render dashboard | On bucket change | Engineering |

## Analytics & Monitoring

| Credential | Purpose | Systems | Where Configured | Rotation Policy | Owner |
|---|---|---|---|---|---|
| `NEXT_PUBLIC_POSTHOG_KEY` | PostHog analytics project API key | Frontend | Vercel dashboard, `.env.local` (dev) | On compromise (regenerate in PostHog) | Engineering |
| `NEXT_PUBLIC_POSTHOG_HOST` | PostHog ingest endpoint | Frontend | `.env.development` (default), `.env.production` (default) | Rarely changes | Engineering |
| `NEXT_PUBLIC_SENTRY_DSN` | Sentry error tracking DSN | Frontend | Vercel dashboard, `.env.local` (dev) | On project recreation | Engineering |

## Ops Dashboard (Next.js Server-Side)

| Credential | Purpose | Systems | Where Configured | Rotation Policy | Owner |
|---|---|---|---|---|---|
| `N8N_API_KEY` | n8n REST API access for workflow status | Frontend (server-side API route) | Vercel dashboard, `.env.local` (dev) | On n8n re-setup | Engineering |
| `N8N_HOST` | n8n instance URL | Frontend (server-side API route) | `.env.development`, `.env.production` | On domain change | Engineering |
| `GITHUB_TOKEN` | GitHub API for CI run status | Frontend (server-side API route) | Vercel dashboard, `.env.local` (dev) | 90-day PAT expiry | Engineering |

## Hetzner Ops Stack (Docker Compose)

| Credential | Purpose | Systems | Where Configured | Rotation Policy | Owner |
|---|---|---|---|---|---|
| `POSTGRES_PASSWORD` | Ops PostgreSQL root password | n8n, Postiz | Hetzner `.env` file | On compromise | Engineering |
| `REDIS_PASSWORD` | Ops Redis password | n8n, Postiz | Hetzner `.env` file | On compromise | Engineering |
| `N8N_USER` / `N8N_PASSWORD` | n8n dashboard login | n8n web UI | Hetzner `.env` file | On compromise | Engineering |
| `POSTIZ_JWT_SECRET` | Postiz session signing | Postiz | Hetzner `.env` file | On compromise | Engineering |

## n8n Agent Credentials (configured in n8n UI)

These credentials are stored in n8n's encrypted credential store, NOT in env vars. Configure via n8n.filefree.tax > Credentials.

| Credential | Purpose | Which Workflows Use It |
|---|---|---|
| OpenAI API Key | AI content generation, analysis | All 6 workflows |
| Notion API Key | Write content drafts, strategy docs, reviews | Social Content Generator, Growth Content Writer, Weekly Strategy Check-in, Partnership Outreach Drafter, CPA Tax Review |
| GitHub PAT | Create issues for security findings | QA Security Scan |
| Postiz API Key | Schedule social media posts | Social Content Generator |

## CI (GitHub Actions)

| Value | Purpose | Where Configured | Notes |
|---|---|---|---|
| `DATABASE_URL` | Test database connection | Hardcoded in `ci.yaml` | Test-only value, not a real secret |
| `SECRET_KEY` | Test auth signing | Hardcoded in `ci.yaml` | Test-only value (`ci-test-secret-key-not-for-production`) |

No `${{ secrets.* }}` references in CI yet. When GITHUB_TOKEN is needed for CI (e.g., gitleaks), it uses the built-in `GITHUB_TOKEN` that GitHub Actions provides automatically.

---

## Security Rules

1. **Never commit secrets to tracked files.** Use `.env.local` (gitignored) for dev secrets. Use Vercel/Render dashboards for production.
2. **Gitleaks runs in CI** on every PR to catch accidental secret commits.
3. **PostHog API key (`phc_tBJ...`)** was historically committed in `web/.env.production`. It has been moved to `.env.local`. The key is a write-only ingest key (low risk) but should not have been tracked.
4. **n8n credentials** are encrypted at rest in n8n's own store. They cannot be exported or read via API.
5. **All credentials in this document are references, not values.** Never put actual credential values in this file.
