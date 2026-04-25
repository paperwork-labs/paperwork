---
owner: trading
last_reviewed: 2026-04-24
doc_kind: reference
domain: trading
status: active
---
# Trading & Order Execution

Axiomfolio supports order execution via Interactive Brokers Gateway. Orders follow a **preview → confirm → execute** lifecycle with risk guardrails. All order endpoints require authentication; orders are scoped to the authenticated user's email.

## Order Lifecycle

```
PREVIEW → PENDING_SUBMIT → SUBMITTED → PARTIALLY_FILLED → FILLED
                                      → CANCELLED
                            → REJECTED
                            → ERROR
```

- **PREVIEW** — created by `whatIfOrder`; persisted with estimated commission/margin but not sent to broker.
- **SUBMITTED** — sent to IBKR; `broker_order_id` is set.
- **FILLED** / **PARTIALLY_FILLED** — updated by polling `get_order_status`.
- **CANCELLED** — user-initiated via `cancelOrder`.
- **REJECTED** — IBKR `Inactive` status mapped on poll.
- **ERROR** — `place_order` returned an error before or during submission.

## Order Model

Stored in the `orders` table (`app/models/order.py`).

| Field | Type | Notes |
|---|---|---|
| `id` | Integer PK | Auto-increment |
| `symbol` | String(20) | Uppercased on insert |
| `side` | String(10) | `buy` or `sell` |
| `order_type` | String(20) | `market`, `limit`, `stop`, `stop_limit` |
| `status` | String(20) | See lifecycle above |
| `quantity` | Float | Shares |
| `limit_price` | Float | Required for `limit` / `stop_limit` |
| `stop_price` | Float | Required for `stop` / `stop_limit` |
| `filled_quantity` | Float | Updated from broker poll |
| `filled_avg_price` | Float | Updated from broker poll |
| `account_id` | String(100) | IBKR account (nullable) |
| `broker_order_id` | String(100) | IBKR order ID (indexed) |
| `estimated_commission` | Float | From `whatIfOrder` preview |
| `estimated_margin_impact` | Float | From `whatIfOrder` preview |
| `estimated_equity_with_loan` | Float | From `whatIfOrder` preview |
| `preview_data` | JSON | Full preview response blob |
| `error_message` | String(500) | Error details |
| `submitted_at` | DateTime(tz) | Set on successful submit |
| `filled_at` | DateTime(tz) | Set when status becomes FILLED |
| `cancelled_at` | DateTime(tz) | Set on cancel |
| `created_at` | DateTime(tz) | Server default `now()` |
| `updated_at` | DateTime(tz) | Auto-updated on change |
| `created_by` | String(200) | Authenticated user email |

Composite indexes: `(symbol, status)` and `(status, created_at)`.

## API Endpoints

All routes are under `/portfolio/orders` and require a valid auth token.

| Method | Path | Description |
|---|---|---|
| `POST` | `/portfolio/orders/preview` | Run `whatIfOrder` preview. Creates a PREVIEW order record. Returns estimated commission, margin impact, and risk warnings. |
| `POST` | `/portfolio/orders/submit` | Submit a previously previewed order. Body: `{ order_id }`. Transitions PREVIEW → SUBMITTED (or ERROR). |
| `GET` | `/portfolio/orders` | List orders. Query params: `status`, `symbol`, `limit` (default 50). Scoped to current user. |
| `GET` | `/portfolio/orders/{id}` | Get a single order by ID. |
| `GET` | `/portfolio/orders/{id}/status` | Poll broker for latest fill status. Updates `filled_quantity` and status in DB. |
| `DELETE` | `/portfolio/orders/{id}` | Cancel a SUBMITTED or PARTIALLY_FILLED order via IBKR `cancelOrder`. |

## Trading Safety

### Feature Flags

| Flag | Default | Effect |
|---|---|---|
| `ENABLE_TRADING` | `False` | Must be `True` for `place_order` and `cancel_order` to execute. Checked in `ibkr_client.py`. |
| `ALLOW_LIVE_ORDERS` | `False` | Must be `True` when the connection is detected as **live** (non-paper). If `False`, live orders return `"rejected"`. |

Both are defined in `backend/config.py` on the `Settings` model and default to `False`, meaning trading is fully disabled out of the box.

### Paper vs Live Detection

`IBKRClient._is_paper_trading()` uses two signals:

1. `settings.IBKR_TRADING_MODE` — if `"paper"`, returns `True`.
2. Port-based fallback — ports `7496` (TWS paper) and `4001` (Gateway) are treated as paper.

`IBKR_TRADING_MODE` is now declared in Settings and respected (paper/live). Port mapping: 7496/4002 = paper, 7497/4001 = live.

### Risk Guardrails

Enforced in `OrderService.preview_order()` (`app/services/order_service.py`):

| Guardrail | Value | Behavior |
|---|---|---|
| `MAX_ORDER_VALUE` | $100,000 | If `quantity × price > $100K`, preview raises `RiskViolation` (HTTP 422). |
| `MAX_SINGLE_POSITION_PCT` | 25% | Requires per-user portfolio equity calculation (not yet implemented). |

Price estimation for market orders falls back to the most recent `MarketSnapshot.current_price` for the symbol.

## IBKR Integration

### whatIfOrder Preview

`IBKRClient.what_if_order()` calls `ib.whatIfOrderAsync(contract, order)` to simulate an order without placing it. Returns:

- `estimated_commission`
- `estimated_margin_impact` (maintenance margin change)
- `estimated_equity_with_loan`
- `maintenance_margin` (after)
- `initial_margin` (after)

### IB Gateway Container

The project uses the `ghcr.io/extrange/ibkr:stable` Docker image for IB Gateway. Default connection: `127.0.0.1:7497` (TWS paper).

### Connection Lifecycle

- **Singleton** — `IBKRClient` uses `__new__` to enforce a single instance.
- **Lazy connect** — `_ensure_connected()` is called before every operation. If disconnected, it triggers `connect_with_retry()`.
- **Exponential backoff** — `connect_with_retry(max_attempts=5)` retries with delays of 1s, 2s, 4s, 8s, 16s (capped at 16s).
- **Event loop awareness** — if the IB instance is bound to a stale event loop, the client disconnects and reconnects in the current loop.

### ib_insync Library

The project depends on [`ib_insync`](https://github.com/erdewit/ib_insync) for all IBKR communication. The library was **archived by its maintainer in March 2024**. It remains functional with current IB Gateway versions but receives no updates.

## Broker Support Matrix

| Broker | Order Placement | Preview (whatIf) | Status |
|---|---|---|---|
| IBKR | Full | Yes | Production |
| TastyTrade | Not implemented | No | Read-only |
| Schwab | Stub only | No | Read-only |

Only IBKR supports order execution today. TastyTrade and Schwab integrations are limited to account/position reads. Alpaca was dropped (D128); autotrading runs through OrderManager / RiskGate / BrokerRouter against the OAuth-connected brokers above.

## Strategy-to-Trade Pipeline

The strategy system connects market intelligence to automated execution:

1. **Define Rules**: Create entry/exit rules using any MarketSnapshot indicator (RSI, stage, RS Mansfield, ATR distance, etc.)
2. **Backtest**: Replay rules against MarketSnapshotHistory to validate performance
3. **Activate**: Run strategies on paper mode first, generating signals
4. **Signals in Dashboard**: Active strategy signals appear in the Holdings lens of Market Dashboard
5. **Execute**: Trade directly from signals using the Trade button (OrderModal)

### Holdings Mode Signals

The Market Dashboard Holdings lens surfaces:
- Action Queue: positions requiring immediate attention
- Setups: technical patterns forming on your holdings
- Stage Transitions: Weinstein stage changes
- Proximity alerts: price near key levels
- Signal alerts: strategy-generated entry/exit signals
- Earnings: upcoming earnings for held positions
