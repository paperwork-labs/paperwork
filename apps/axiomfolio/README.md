# Axiomfolio Frontend

## Quick Start

```bash
npm install
npm run dev          # Vite dev server on :3000
npm run ladle        # Component explorer on :61000
npm run test         # Vitest test runner
npm run lint         # ESLint
npm run type-check   # TypeScript check
```

## Tech Stack

| Category | Library |
|----------|---------|
| UI Framework | React 19, Radix UI, Tailwind CSS, shadcn/ui-style components, Framer Motion |
| Build | Vite 5, TypeScript 5.9 |
| Data Fetching | TanStack Query v5 |
| Routing | React Router v7 |
| Charts | Recharts v3, lightweight-charts v5 |
| Forms | React Hook Form |
| Testing | Vitest 4, Testing Library, happy-dom |
| Linting | ESLint 9 |
| Component Dev | Ladle 5 |

## Project Structure

```
src/
  components/   # UI components (shared/, ui/, orders/, market/, portfolio/, settings/)
  pages/        # Page-level components (lazy-loaded via React.lazy)
  services/     # API client (api.ts), service hooks
  hooks/        # Custom React hooks
  context/      # React context providers (Auth, Account)
  theme/        # Color mode and legacy theme helpers (Tailwind + CSS variables are primary)
  types/        # TypeScript type definitions
  utils/        # Utility functions
  test/         # Test setup (Vitest)
```

Path alias: `@/*` maps to `src/*` (configured in `tsconfig.json` and `vite.config.ts`).

## API Client

`src/services/api.ts` exports a configured Axios instance and domain-specific API objects:

- **`portfolioApi`** — holdings, dashboard, categories, tax lots, performance, balances
- **`optionsApi`** — options portfolio and summary
- **`marketDataApi`** — price history, snapshots, volatility dashboard
- **`activityApi`** — transactions and daily summaries
- **`accountsApi`** — account CRUD, sync, credentials
- **`aggregatorApi`** — broker connections (Schwab, TastyTrade, IBKR)
- **`authApi`** — login, register, invite, profile
- **`adminUsersApi`** — user management, invites
- **`tasksApi`** — trigger Discord notifications and alerts

Key features:
- JWT attached automatically via request interceptor (`localStorage` key `qm_token`)
- Built-in request queue (max 6 concurrent) to avoid backend connection saturation
- Auto-retry on network errors; 401 responses trigger `auth:logout` event and token removal
- `unwrapResponse` / `unwrapResponseSingle` helpers for normalizing nested backend envelopes

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `VITE_API_BASE_URL` | API base path used by Axios | `/api/v1` |
| `VITE_PROXY_TARGET` | Vite dev-server proxy target (local dev only) | `http://backend:8000` |

The Vite dev server runs host-side (not in Docker). It proxies `/api` to
`http://localhost:8004` which is where the `api-axiomfolio` container
exposes its backend in the unified dev stack.

## Running locally

The frontend is a pnpm workspace member (`@paperwork-labs/axiomfolio`) and
runs via pnpm directly — no Docker container for the frontend. This
matches the house pattern (filefree, launchfree, studio, distill, trinkets
all run their dev servers host-side).

```bash
# From repo root:
pnpm install
pnpm dev:axiomfolio          # Vite dev server on :3006
pnpm build:axiomfolio        # Production build

# From this directory:
pnpm dev
pnpm run ladle               # Component workshop
pnpm run ladle:build
```

The backend stack (postgres, redis, api-axiomfolio, celery workers)
boots via the root compose:

```bash
# From apis/axiomfolio/:
make up                      # backend + celery worker + celery beat
make up-ibkr                 # + IB Gateway (optional profile)
make down
```

See `docs/INFRA.md` for the full architecture.
