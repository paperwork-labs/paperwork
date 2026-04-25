---
owner: trading
last_reviewed: 2026-04-22
doc_kind: plan
domain: trading
status: active
---
# Wave F — Trading Parity Across All Six Brokers

> Source-of-truth plan for Wave F. Supersedes ad-hoc trading-parity notes. Written so each sub-wave (F0 through F5) is a single merge-able PR executable by a single Background Agent (exception: F0 is Opus-only — see gating note).

## Goal

Bring the write-path (live and paper order placement) to parity with the sync-path (already multi-broker). Today `app/services/execution/broker_router.py` only registers `ibkr` and `paper`; the sync side already ships IBKR, TastyTrade, Schwab, E*TRADE, Tradier, and Coinbase. This wave closes the gap.

**Founder-confirmed scope (2026-04-22):**

- **Live:** IBKR (shipped), Schwab, TastyTrade, E*TRADE, Tradier
- **Paper-only:** Coinbase (crypto live execution deferred to a later wave)
- **Out of scope:** order modify (no `modify_order` in `BrokerExecutor` protocol today — stays out); Robinhood (no OAuth partner terms yet); Fidelity/Vanguard (covered by the Plaid plan, read-only).

## Anchors (authoritative file references)

- Executor protocol: [`app/services/execution/broker_base.py`](../../app/services/execution/broker_base.py) lines 91-111 (`BrokerExecutor` Protocol: `preview_order`, `place_order`, `cancel_order`, `get_order_status`, `is_paper_trading`)
- Router: [`app/services/execution/broker_router.py`](../../app/services/execution/broker_router.py) lines 44-52 (`create_default_router`)
- Reference live executor: [`app/services/execution/ibkr_executor.py`](../../app/services/execution/ibkr_executor.py)
- Reference paper executor: [`app/services/execution/paper_executor.py`](../../app/services/execution/paper_executor.py)
- Order manager (caller): [`app/services/execution/order_manager.py`](../../app/services/execution/order_manager.py)
- Risk gate (DANGER ZONE): [`app/services/execution/risk_gate.py`](../../app/services/execution/risk_gate.py) `_check_stage_regime_sizing` lines 181-239 assumes Weinstein stages
- Order enum: [`app/models/order.py`](../../app/models/order.py) lines 54-57 — only has `IBKR, TASTYTRADE, SCHWAB`. Live write path needs `ETRADE, TRADIER, COINBASE` added.
- Sync-side broker list: [`app/services/portfolio/broker_sync_service.py`](../../app/services/portfolio/broker_sync_service.py) lines 116-154 already knows all 7. `BrokerType` in `app/models/broker_account.py` already has all values.
- OAuth token store: [`app/models/broker_oauth_connection.py`](../../app/models/broker_oauth_connection.py) `OAuthBrokerType` already includes `ETRADE, SCHWAB, TASTYTRADE, TRADIER, COINBASE`
- Broker REST clients (already built for sync, extend for write): [`app/services/bronze/tradier/client.py`](../../app/services/bronze/tradier/client.py), [`app/services/bronze/etrade/client.py`](../../app/services/bronze/etrade/client.py), [`app/services/clients/schwab_client.py`](../../app/services/clients/schwab_client.py), [`app/services/clients/tastytrade_client.py`](../../app/services/clients/tastytrade_client.py), [`app/services/clients/coinbase_client.py`](../../app/services/clients/coinbase_client.py) (if missing, Agent creates it)
- Frontend broker catalog: [`frontend/src/components/connections/brokerCatalog.ts`](../../frontend/src/components/connections/brokerCatalog.ts)
- Frontend trade panel (executor dropdown): Grep `broker_type` under `frontend/src/components/trade/` and `frontend/src/pages/trade/`

## Cross-cutting design decisions

### 1. Crypto risk path (F0, DANGER ZONE)

`risk_gate._check_stage_regime_sizing` assumes equity Weinstein stages + `MarketSnapshot` regime. For Coinbase (crypto), none of those apply. The change:

- Add a helper `_is_crypto_symbol(symbol: str) -> bool` that returns `True` for `BTC, ETH, ADA, SOL, MATIC, DOGE` plus any symbol ending in `-USD` or `-USDT` (founder-curated starter set; expand later).
- Add an early-return in `_check_stage_regime_sizing`: if `_is_crypto_symbol(req.symbol)`, do not consult `MarketSnapshot`/regime; instead call a new `_check_crypto_sizing(req, price_estimate, risk_budget)` that enforces a lighter rule: position value ≤ `CRYPTO_MAX_POSITION_PCT * portfolio_equity` (default 5%, new setting in [`backend/config.py`](../../backend/config.py)).
- The top-level `RiskGate.check` still runs `est_value > max_order_value` and `pct > max_position_pct` — those stay global.
- **Non-negotiable:** the 1% per-trade / 6% portfolio-heat / 2%-3%-5% circuit-breaker framing per `.cursor/rules/risk-manager.mdc` must still apply to crypto. The only relaxation is the stage/regime sizing, because crypto has no Weinstein stages.

Why Opus-only: any edit to `risk_gate.py` is a DANGER ZONE edit per [`.cursor/rules/protected-regions.mdc`](../../.cursor/rules/protected-regions.mdc). Background agents are **not** permitted to touch risk_gate without explicit Opus approval per `.cursor/rules/delegation.mdc`. Opus writes F0 by hand.

### 2. OAuth token freshness

Every live executor's `place_order`/`cancel_order` **must** call `ensure_valid_token()` before the first API call. Today, OAuth token refresh only runs in the sync path ([`app/services/oauth/refresh.py`](../../app/services/oauth/refresh.py)). If a trade is submitted with an expired token, the broker rejects it and we lose order-ID capture.

Shared helper to add in F0: `app/services/execution/oauth_executor_mixin.py` — a mixin or small helper that wraps `OAuthBrokerAdapter.ensure_valid_token(connection)` and raises a typed error if refresh fails. All F1-F4 executors use it.

### 3. Broker order-ID capture + cancel parity

Every `place_order` must populate `OrderResult.broker_order_id`; every `cancel_order` takes that ID back and must succeed even if the order is already filled (return `status="filled"` rather than raising). Test coverage in each sub-wave asserts the round-trip.

### 4. Frontend broker-capability flag

Today `brokerCatalog.ts` lists brokers but does not distinguish "can trade live" vs "sync only". Add a `capabilities: { sync: boolean; trade: "live" | "paper" | "none" }` field; drive the trade panel's broker dropdown from this. Frontend unit test: given a mock catalog with Coinbase = `trade: "paper"`, the trade panel renders a "Paper only" badge next to Coinbase and the submit button is labeled "Submit paper order".

## Sub-waves

### F0 — Foundation (Opus, not delegated, 0.5d)

**PR branch:** `feat/wave-f0-foundation`

Work:

1. Extend `BrokerType` enum in [`app/models/order.py`](../../app/models/order.py) to include `ETRADE, TRADIER, TRADIER_SANDBOX, COINBASE`. (The column is `String(20)` so no Alembic needed for the enum itself — but add a migration `0075_broker_type_check.py` that adds a `CHECK (broker_type IN (...))` constraint to enforce valid values at the DB level.)
2. Add `CRYPTO_MAX_POSITION_PCT: float = 0.05` to [`backend/config.py`](../../backend/config.py) Settings.
3. Modify [`app/services/execution/risk_gate.py`](../../app/services/execution/risk_gate.py) per the crypto design above. Add unit test `backend/tests/execution/test_risk_gate_crypto.py` covering: BTC-USD passes a 3%-of-equity order; BTC-USD rejects a 10%-of-equity order; AAPL still routes through `_check_stage_regime_sizing`.
4. Create `app/services/execution/oauth_executor_mixin.py` exposing `async def ensure_broker_token(connection: BrokerOAuthConnection) -> None`.
5. Create [`app/services/execution/coinbase_paper_executor.py`](../../app/services/execution/coinbase_paper_executor.py) — mirrors [`app/services/execution/paper_executor.py`](../../app/services/execution/paper_executor.py) but: (a) sets `broker_name = "coinbase-paper"`; (b) tags every `Order.notes` with `"paper"`; (c) rejects symbols that do not match `_is_crypto_symbol`.
6. Register `coinbase` (paper) in `create_default_router` in [`app/services/execution/broker_router.py`](../../app/services/execution/broker_router.py).
7. Smoke test `backend/tests/execution/test_f0_smoke.py`: submit buy/cancel through `OrderManager` for `(ibkr, paper, coinbase)` via `router.get()`; assert all three round-trip.

Acceptance:

- `BrokerRouter().available_brokers` returns `["ibkr", "paper", "coinbase"]` minimum after F0.
- Risk gate tests pass; no regression in existing equity tests.
- Frontend: no change in F0 (the trade panel dropdown update lands in F5 once all capability flags are meaningful).

### F1 — Tradier live (Background Agent, 1-2d)

**PR branch:** `feat/wave-f1-tradier-live`

Why Tradier first: simplest OAuth 2 + REST flow; lowest-risk canary for the executor template.

Work:

1. Create [`app/services/execution/tradier_executor.py`](../../app/services/execution/tradier_executor.py). Model after `ibkr_executor.py`. Implement `preview_order` via Tradier's `/v1/accounts/{id}/orders?preview=true`, `place_order` via POST `/v1/accounts/{id}/orders`, `cancel_order` via DELETE, `get_order_status` via GET. Use `TradierClient` from [`app/services/bronze/tradier/client.py`](../../app/services/bronze/tradier/client.py); extend that client if order endpoints are not yet exposed.
2. Call `await ensure_broker_token(connection)` at the top of every write method using the F0 mixin.
3. Register `tradier` and `tradier_sandbox` in `create_default_router` (same instance, parameterized by `environment`).
4. Integration test in `backend/tests/execution/test_tradier_executor.py` using `responses` mocks for the 4 endpoints.

Acceptance:

- Submit → cancel round-trip passes in sandbox (agent uses `TRADIER_SANDBOX_*` env vars from `infra/env.dev.example`).
- `OrderResult.broker_order_id` populated from Tradier's `order.id`.
- Token refresh exercised in one test (expired `access_token`, mixin refreshes, call succeeds).

### F2 — E*TRADE live (Background Agent, 2-3d)

**PR branch:** `feat/wave-f2-etrade-live`

Complications: OAuth 1.0a (not 2.0); HMAC-SHA1 request signing. The signing is already implemented for sync in [`app/services/bronze/etrade/client.py`](../../app/services/bronze/etrade/client.py) lines 65-71.

Work mirrors F1. Use E*TRADE sandbox endpoints (`etws.etrade.com`) during tests; respect the 2-step order flow (preview returns a `previewId` that must be echoed in the place step). **Explicit safety: gate `environment == "prod"` behind a `ETRADE_ALLOW_LIVE=true` feature flag for the first two weeks post-merge so an accidental prod config doesn't route real orders.**

Acceptance same shape as F1.

### F3 — Schwab live (Background Agent, 2-3d)

**PR branch:** `feat/wave-f3-schwab-live`

Replace the `not_implemented` stub at [`app/services/clients/schwab_client.py`](../../app/services/clients/schwab_client.py) lines 506-511. Schwab Trader API requires an `account_hash` (not the plain `account_id`) — the sync service already resolves this; reuse the same resolver. Status requires polling since Schwab does not push; the executor's `get_order_status` polls the Schwab order endpoint.

Acceptance same shape as F1.

### F4 — TastyTrade live (Background Agent, 2-3d)

**PR branch:** `feat/wave-f4-tastytrade-live`

TastyTrade uses a session token that refreshes on a 24h rolling window (distinct from OAuth 2 refresh). Its SDK ([`tastytrade`](https://pypi.org/project/tastytrade/)) handles this; the executor wraps it. TastyTrade is options-capable — ensure `place_order` accepts an `option_symbol` pathway (but do not block on options trading; equity first, options follow as a non-blocking note).

Acceptance same shape as F1.

### F5 — Coinbase paper hardening + capability-flag frontend (Background Agent, 0.5d)

**PR branch:** `feat/wave-f5-coinbase-paper-hardening`

Work:

1. Frontend: add the `capabilities` field to [`frontend/src/components/connections/brokerCatalog.ts`](../../frontend/src/components/connections/brokerCatalog.ts); drive the trade panel dropdown off `capabilities.trade`; render "Paper only" badge for Coinbase; disable Submit if `capabilities.trade === "none"`.
2. Backend: ensure [`app/services/execution/coinbase_paper_executor.py`](../../app/services/execution/coinbase_paper_executor.py) cannot be "upgraded" to live by a config typo — add a module-level `assert os.getenv("COINBASE_ALLOW_LIVE") != "true"` guard with a clear error message if set.
3. Add an end-to-end test `frontend/src/pages/trade/__tests__/TradePanel.capabilities.test.tsx` that mocks the catalog and asserts the badge + disabled-state behavior.

Acceptance: trade panel looks correct in the UI (founder eyeballs); Coinbase cannot accidentally route live.

## Aggregate acceptance (entire wave)

- `broker_router.available_brokers` returns `["ibkr", "paper", "tradier", "tradier_sandbox", "etrade", "etrade_sandbox", "schwab", "tastytrade", "coinbase"]` (9 entries).
- For each live broker, one integration test exercising `OrderManager.submit` → `cancel` → `get_order_status` passes against the sandbox.
- Coinbase orders tagged `paper` in `Order.notes` + trade journal.
- Frontend broker dropdown + badges match backend capabilities.
- No silent zero fallbacks in any executor (per `.cursor/rules/no-silent-fallback.mdc`); all failure paths log + raise.
- No regression in existing IBKR path (regression suite in `backend/tests/execution/test_ibkr_executor.py`).

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| OAuth token race between sync and write paths | F0 mixin serializes `ensure_valid_token` under a per-connection Redis lock (already available via `app.services.cache.redis_client`, see R40) |
| Crypto symbol detection misses exotic pairs | F0 ships a curated list; expand via `CRYPTO_SYMBOLS` env override; unit tests guard the default set |
| E*TRADE prod accidentally enabled | F2 ships with `ETRADE_ALLOW_LIVE=false` default; flip requires explicit founder action |
| Schwab account hash stale after re-auth | Executor re-resolves `account_hash` on each `place_order` via cached-but-per-request lookup |
| Background Agent accidentally touches `risk_gate.py` | Prompt explicitly forbids it; Opus code-reviews every PR before merge |

## Sizing and sequencing

| Sub-wave | Owner | Calendar days | Parallelizable with |
|---|---|---|---|
| F0 | Opus | 0.5 | — (blocker for F1-F5) |
| F1 Tradier | Agent | 1-2 | F2, F3, F4 |
| F2 E*TRADE | Agent | 2-3 | F1, F3, F4 |
| F3 Schwab | Agent | 2-3 | F1, F2, F4 |
| F4 TastyTrade | Agent | 2-3 | F1, F2, F3 |
| F5 Paper hardening | Agent | 0.5 | Runs after F1-F4 land (touches same frontend catalog) |

Total calendar time with parallel agents: **~4-5 days** (F0 + max(F1-F4) + F5).

## Dispatch pattern (for the follow-up session)

1. Opus opens and merges F0 by hand with founder review (DANGER ZONE policy).
2. In a single message, Opus launches 4 parallel Background Agents for F1-F4 with this plan doc as the execution spec.
3. Each agent opens its PR, fixes CI, tags `@founder` for review. Opus reviews each PR before founder merges.
4. After F1-F4 merge, Opus launches the F5 agent.

## Post-merge verification (every sub-wave)

Per [`.cursor/rules/production-verification.mdc`](../../.cursor/rules/production-verification.mdc):

- Wait for Render deploy to live on the new SHA.
- `curl /api/v1/trading/available_brokers` returns the expected list.
- Submit one canary order via `paper-shadow` mode for the new broker; confirm `JobRun` log + `Order` row.
- Watch logs for 5 minutes.

## Follow-ups (non-blocking)

- `modify_order` capability on `BrokerExecutor` protocol (new wave after F5).
- Robinhood integration (requires partner agreement).
- Coinbase live execution (deferred; reconsider once paper-shadow shows clean P&L for 30 days).
- IBKR Options trading via the same executor (today only equity; add options path as a small follow-up PR).
