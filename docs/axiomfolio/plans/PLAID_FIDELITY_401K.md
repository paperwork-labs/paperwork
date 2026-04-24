# Plaid Investments — Single-Phase Pro-Tier Feature

> Supersedes the "no Plaid in v1" clause of D129 (see `docs/KNOWLEDGE.md`). Founder decision on 2026-04-22 (see D130 in the same file): ship Plaid as a first-class Pro-tier feature from day one — no allowlist stop-gap. Founder is currently on `PRO_PLUS` so gating is friction-free; ripping out an allowlist later is more work than wiring tier-gating once.

## Scope

**What ships:** one Plaid integration path for read-only portfolio sync (positions, balances, transactions) against any Plaid-supported Investments institution. The motivating use-case is Fidelity 401k (founder + spouse), but nothing in the design is Fidelity-specific.

**Tier gating:** new `Feature(broker.plaid_investments, min_tier=PRO)` in the feature catalog. Free tier gets a 402 response; Pro and above work. UI surfaces this via the existing `TierGate` component.

**Out of scope (do not include in this PR):**

- Trading via Plaid (Plaid Investments does not support order entry; nothing to build).
- Real-time webhook-driven holdings updates (Phase 1 is daily cron; webhooks are a follow-up wave).
- Cost-model / unit economics dashboard (`app/services/billing/provider_costs.py`) — file this as a separate ticket.
- Marketing copy flip on [`frontend/src/pages/WhyFree.tsx`](../../frontend/src/pages/WhyFree.tsx) lines 116-138 (separate PR once Pro tier goes public).
- Support runbook for re-auth + webhook-failure recovery (build when user_count > 1).

## Pre-flight check (already in place — do not rebuild)

- Tier plumbing: `Feature` catalog in [`app/services/billing/feature_catalog.py`](../../app/services/billing/feature_catalog.py), `require_feature` dep in [`app/api/dependencies.py`](../../app/api/dependencies.py) lines 112-146, `TierGate` component on the frontend. Precedent for broker-feature keys: `execution.single_broker` line 188, `execution.multi_broker` line 195.
- Broker account model already has `BrokerType.FIDELITY` ([`app/models/broker_account.py`](../../app/models/broker_account.py) line 38). **Do not add `BrokerType.PLAID` as a meta-type** — Plaid is a connection method, not a broker. Instead, add a `connection_source: "direct" | "plaid"` column (see step 1 below). This lets `FIDELITY + plaid` coexist with a future `FIDELITY + direct` without enum thrash.
- Tax lot source enum currently lacks an `AGGREGATOR` value ([`app/models/tax_lot.py`](../../app/models/tax_lot.py) line 40-48): add it in the migration below.
- Broker sync registry: [`app/services/portfolio/broker_sync_service.py`](../../app/services/portfolio/broker_sync_service.py) lines 138-146 — new factory row for Plaid.

## Alembic migrations (1 revision)

File: `app/alembic/versions/0075_plaid_integration.py` (parent = `0074_drop_app_settings`).

- Add `broker_accounts.connection_source` `VARCHAR(16)` default `'direct'` not null; backfill existing rows to `'direct'`.
- Add value `'aggregator'` to the `tax_lots.source` enum (`ALTER TYPE taxlotsource ADD VALUE 'aggregator';`).
- Create table `plaid_connections`:
  - `id SERIAL PRIMARY KEY`
  - `user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE`
  - `item_id VARCHAR(64) UNIQUE NOT NULL`  — Plaid `item_id`
  - `access_token_encrypted TEXT NOT NULL`  — Fernet-encrypted (reuse `app.services.oauth.encryption`)
  - `institution_id VARCHAR(32) NOT NULL`
  - `institution_name VARCHAR(128) NOT NULL`
  - `transactions_cursor VARCHAR(256) NULL`
  - `last_sync_at TIMESTAMPTZ NULL`
  - `last_error TEXT NULL`
  - `status VARCHAR(32) NOT NULL DEFAULT 'active'`  — one of `active | needs_reauth | revoked | error`
  - `environment VARCHAR(16) NOT NULL DEFAULT 'sandbox'`
  - `created_at`, `updated_at` timestamp columns (mirror existing model conventions)
  - Index on `(user_id, status)`

## Backend changes

### 1. New model

[`app/models/plaid_connection.py`](../../app/models/plaid_connection.py) — mirrors [`app/models/broker_oauth_connection.py`](../../app/models/broker_oauth_connection.py) in structure. Register in `app/models/__init__.py`.

### 2. Update existing model

[`app/models/broker_account.py`](../../app/models/broker_account.py): add `connection_source = Column(String(16), nullable=False, default="direct")` and a property `is_aggregator: bool` that returns `connection_source == "plaid"`.

### 3. Update tax-lot enum and guard

[`app/models/tax_lot.py`](../../app/models/tax_lot.py):

- Add `AGGREGATOR = "aggregator"` to `TaxLotSource` enum (line 40-48).
- Fix the latent bug at line 141-144: `gain_loss` does `(price - cost_per_share) * qty` but `cost_per_share` can now legitimately be None (aggregator source). Change to: if either is None, return `0.0` **and** add a new property `gain_loss_available: bool` that callers can use to distinguish "zero-ish because unknown" from "zero-ish because break-even". This prevents silent-zero rendering per `.cursor/rules/no-silent-fallback.mdc`.

### 4. New package: Plaid client + sync service

Structure mirrors the IBKR package:

```
app/services/portfolio/plaid/
  __init__.py
  client.py            # thin plaid-python SDK wrapper; handles token encrypt/decrypt
  sync_service.py      # implements the BrokerSyncService protocol
  pipeline.py          # orchestrates: balances -> positions -> transactions -> persist
```

- `client.py` exports `PlaidClient` with methods: `create_link_token(user_id) -> str`, `exchange_public_token(public_token) -> (access_token, item_id)`, `get_accounts(access_token)`, `get_holdings(access_token)`, `get_investments_transactions(access_token, cursor)`.
- `sync_service.py` class `PlaidSyncService` exposes `sync(account_id, session)` returning the same dict shape as `IBKRSyncService.sync`.
- `pipeline.py` reads holdings → creates/updates `Position` rows + one `TaxLot` row per holding with `source=TaxLotSource.AGGREGATOR`, `cost_per_share=None`, `cost_basis=None` (Plaid does not return per-lot basis). Add a structured-counter loop per `.cursor/rules/no-silent-fallback.mdc`: `written`, `skipped_no_holdings`, `errors`; assert sum equals total.

### 5. Register in broker_sync_service

[`app/services/portfolio/broker_sync_service.py`](../../app/services/portfolio/broker_sync_service.py) around line 138-146: add a new factory. Because `BrokerType` does not include `PLAID`, dispatch based on `BrokerAccount.connection_source == "plaid"` **before** the `BrokerType` switch. Extract a helper `_route_to_service(account)` that takes the `BrokerAccount`, checks `connection_source` first, then falls back to `BrokerType`-based dispatch.

### 6. New API routes

[`app/api/routes/plaid.py`](../../app/api/routes/plaid.py), mounted under `/api/v1/plaid`:

- `POST /link_token` → `{ "link_token": "..." }`. Calls Plaid `/link/token/create` with the `auth`, `investments`, `transactions` products.
- `POST /exchange` body `{ public_token: str, metadata: {...} }` → creates a `PlaidConnection` row + one or more `BrokerAccount` rows with `connection_source="plaid"`, `broker_type=FIDELITY` (or whatever Plaid returns; match against `BrokerType` members case-insensitively, fall back to `BrokerType.UNKNOWN_BROKER` with a logged warning).
- `POST /webhook` → no-auth endpoint that verifies Plaid's webhook signature (Plaid uses JWT with JWKs; see [Plaid docs](https://plaid.com/docs/api/webhooks/webhook-verification/)); dispatches a Celery task to resync affected `item_id`.
- `DELETE /connections/{id}` → revokes token via Plaid, marks row `status=revoked`, sets linked `broker_accounts.is_enabled=false`.

**All routes** wrap `Depends(require_feature("broker.plaid_investments"))` **except** `/webhook` (Plaid cannot send a bearer; signature verification is the auth). Scope every DB query by `current_user.id` per multi-tenancy enforcement in `.cursor/rules/engineering.mdc`.

### 7. Feature catalog entry

[`app/services/billing/feature_catalog.py`](../../app/services/billing/feature_catalog.py), alongside the existing `execution.*` entries (lines 188+):

```python
Feature(
    key="broker.plaid_investments",
    name="Investments via Plaid",
    description="Connect 401k and brokerage accounts via Plaid aggregator.",
    min_tier=Tier.PRO,
    category="broker",
),
```

### 8. Celery task

[`app/tasks/portfolio/plaid_sync.py`](../../app/tasks/portfolio/plaid_sync.py):

```python
@shared_task(soft_time_limit=600, time_limit=660)
@task_run("plaid_daily_sync")
def daily_sync() -> dict:
    # iterate PlaidConnection rows with status='active'
    # for each, call PlaidSyncService.sync
    # emit counters: processed, succeeded, needs_reauth, errors
    # assert sum == total (no silent swallow)
```

Job catalog entry in [`app/tasks/job_catalog.py`](../../app/tasks/job_catalog.py): `plaid_daily_sync`, cron `0 5 * * *` UTC (after overnight FX/settlement), queue `heavy`, `timeout_s=660`. Matches `hard_time_limit` per IRON LAW.

### 9. Health dimension

[`app/services/monitoring/admin_health_service.py`](../../app/services/monitoring/admin_health_service.py) (Grep for the existing `dimensions` list): add a `plaid` dimension reporting last successful sync timestamp per user, error counter, and any `needs_reauth` rows. Surfaces in `/admin/health`.

## Frontend changes

### 1. New package: PlaidLink wrapper

Install `react-plaid-link` as a new dep in `frontend/package.json`. Component [`frontend/src/components/connections/PlaidLink.tsx`](../../frontend/src/components/connections/PlaidLink.tsx):

- On mount, `useQuery` hits `POST /api/v1/plaid/link_token`; renders a skeleton while loading.
- Wraps `<PlaidLink>` from the SDK; on `onSuccess(publicToken, metadata)`, `useMutation` hits `POST /api/v1/plaid/exchange`.
- On success, invalidate `['accounts']` and `['portfolio']` query caches.
- Loading/error/empty/data states explicit per `.cursor/rules/no-silent-fallback.mdc`.

### 2. Wrap in TierGate

Wherever `PlaidLink` is embedded (connections page, empty-state CTA on the dashboard), wrap in `<TierGate feature="broker.plaid_investments">`. Reuse the existing pattern from `PortfolioWorkspace` / `MonteCarlo`.

### 3. Connections page tile

Add a Plaid tile to [`frontend/src/pages/settings/Connections.tsx`](../../frontend/src/pages/settings/Connections.tsx) (or the current connections page — Grep for the IBKR tile and clone). Show each connected institution with status + last sync + "Disconnect" button.

### 4. Tax-lot UI honesty

In tax-lot tables, render `—` (with an `<InfoTooltip>`) for any lot where `source === "aggregator"` and `cost_per_share === null`. Tooltip text: **"Cost basis not available from aggregator. Per-lot detail available only via direct broker connection."** Never render `$0.00`.

### 5. Broker catalog capabilities

Add to [`frontend/src/components/connections/brokerCatalog.ts`](../../frontend/src/components/connections/brokerCatalog.ts) a `capabilities` field (if not already present per Wave F5): Plaid gets `{ sync: true, trade: "none", source: "aggregator" }`. Use this to hide the "Trade" column on Plaid-backed accounts across the UI.

## Privacy doc

Add one paragraph to [`docs/privacy.md`](../../docs/privacy.md) listing Plaid as a sub-processor with a link to the Plaid DPA. This is contractually required by Plaid regardless of user count; doing it at ship-time avoids a later audit.

```markdown
### Sub-processors

- **Plaid Inc.** — Used to connect investment accounts at institutions without direct OAuth integration (e.g., Fidelity, Vanguard). Users explicitly authorize each connection via Plaid Link. Plaid receives the user's institution credentials; AxiomFolio never sees or stores them. See [Plaid DPA](https://plaid.com/legal/data-processing-agreement/). Tokens are stored encrypted at rest (Fernet) and revoked on user request.
```

## Environment / config

Add to `backend/config.py` Settings (with matching entries in `infra/env.dev.example`):

- `PLAID_CLIENT_ID: str`
- `PLAID_SECRET: str`
- `PLAID_ENV: Literal["sandbox","development","production"] = "sandbox"`
- `PLAID_PRODUCTS: str = "investments,transactions"`
- `PLAID_WEBHOOK_URL: Optional[str] = None`

Default to `sandbox` in dev; founder provides prod creds via Render env vars. **Do not commit real creds.**

## Tests (new)

- `backend/tests/services/portfolio/plaid/test_client.py` — mocked SDK responses, token encrypt/decrypt round-trip.
- `backend/tests/services/portfolio/plaid/test_sync_service.py` — golden-fixture holdings; asserts `Position` + `TaxLot` rows with `source=AGGREGATOR, cost_per_share=None`.
- `backend/tests/api/routes/test_plaid.py` — route auth (402 for Free tier; 200 for Pro), multi-tenancy (User A cannot see User B's `PlaidConnection`), webhook signature verification (rejects invalid, accepts valid).
- `backend/tests/tasks/test_plaid_sync.py` — counter-loop asserts `processed + needs_reauth + errors == total`; failure path logs and raises (no silent swallow).
- `frontend/src/components/connections/__tests__/PlaidLink.test.tsx` — loading/error/success states; invalidates cache on success.
- Cross-tenant isolation integration test in `backend/tests/api/test_multi_tenancy.py` (new or extend existing).

## Acceptance

- Founder logs in → navigates to Connections → clicks **Connect via Plaid** → Plaid Link modal opens → connects Fidelity 401k → redirected back → tile shows "Fidelity (Plaid) · active · synced just now".
- Positions + balances from the 401k show under a `Fidelity` account with a visible "via Plaid" badge.
- Tax-lot table shows each position with `—` for cost basis (not `$0.00`), tooltip visible on hover.
- Daily 05:00 UTC Celery job runs; emits structured counters to logs; no silent swallow on individual connection failures.
- `/admin/health` has a `plaid` dimension reporting `active_connections`, `needs_reauth_count`, `error_count_24h`, `oldest_successful_sync_age_seconds`.
- `GET /api/v1/plaid/link_token` returns 402 for a Free-tier user.
- Disconnect flow revokes at Plaid, marks row `revoked`, and future syncs skip it.
- `docs/privacy.md` lists Plaid.
- No `any` types added without justification; no `console.log` left in committed frontend code; all tests green.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Plaid access tokens leaked | Fernet encryption at rest; never logged; audit log on decrypt |
| User connects an account type we don't model (e.g., 529) | Log + skip; surface under `/admin/health.plaid.unsupported_subtypes` counter; never silently persist broken rows |
| Webhook signature forgery | JWT + JWKs verification per Plaid spec; reject on any mismatch with a 401 + log |
| Tier gating bypass | Every route uses `Depends(require_feature(...))`; integration test asserts 402 |
| Duplicate sync when webhook and cron race | `PlaidConnection.last_sync_at` + Redis lock per `item_id` (reuse `app.services.cache.redis_client`) |
| Plaid cost surprise (sandbox free; prod = per-API call) | Founder remains the only prod user until cost model ships; Plaid sandbox tokens for all CI/test runs |

## Sizing

- Backend: 2.5 days (model + client + sync + routes + task + catalog + tests)
- Frontend: 1 day (PlaidLink + TierGate wrap + tile + tax-lot UI fix)
- Privacy + config + QA: 0.5 day
- Review + prod verification: 0.5 day
- **Total: ~4-5 dev days, 1 PR, 1 Alembic migration**

## Dispatch pattern

One Cursor Background Agent runs this plan end-to-end on branch `feat/plaid-fidelity-401k`. Opus reviews the final PR focusing on:

- Token encryption path (no plaintext logs; Fernet key read from env)
- Privacy doc diff
- Multi-tenancy assertions in tests
- No silent-zero on tax-lot UI
- Counter-loop assertions in the sync task

## Follow-ups (non-blocking, separate tickets)

- Marketing: flip [`frontend/src/pages/WhyFree.tsx`](../../frontend/src/pages/WhyFree.tsx) lines 116-138 from "Plaid not in v1" to "Plaid available on Pro".
- Support runbook: re-auth flow + webhook-failure recovery.
- Webhook-driven real-time updates (beyond initial daily cron).
- Cost model: `app/services/billing/provider_costs.py` per-provider cost dashboard.
- Extend PlaidConnection to add spouse user via household linking (currently 1 user = 1 auth).
