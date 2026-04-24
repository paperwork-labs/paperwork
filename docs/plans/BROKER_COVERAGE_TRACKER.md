# Broker Coverage Tracker — Evergreen

**Status**: EVERGREEN — single source of truth for broker support (read + write). Update when any broker capability ships or changes tier.
**Created**: 2026-04-22
**Owner**: Founder + platform lead.
**Companions**: [PLATFORM_REVIEW_2026Q2.md](PLATFORM_REVIEW_2026Q2.md) (Chapter 7) · [PORTFOLIO_SYNC_COMPLETENESS_2026Q2.md](PORTFOLIO_SYNC_COMPLETENESS_2026Q2.md) (Wave 8 deep dive) · [GAPS_2026Q2.md](GAPS_2026Q2.md) (G22 FlexQuery validator, G18 sleeves).

---

## 1 — Legend

| Symbol | Meaning |
|--------|---------|
| **LIVE** | Shipped + verified in prod for current users |
| **PARTIAL** | Code exists / partial coverage; some sub-capability missing or unverified |
| **PLANNED** | Scoped in a wave; not yet implemented |
| **—** | Out of scope / not applicable |
| **DROPPED** | Removed from product ([D128](../KNOWLEDGE.md) Alpaca) |

---

## 2 — Capability dimensions

We track ten dimensions per broker. "Read-side" (1–6) supports the Portfolio pillar; "write-side" (7–10) supports the Trading pillar.

1. **Accounts sync** — account metadata, balances, equity, margin.
2. **Positions sync** — symbol, quantity, avg cost.
3. **Trades / transactions history** — buys, sells, dividends, fees, interest, transfers.
4. **Tax lots** — acquired date, cost basis, holding period, lot ID.
5. **Options data** — option positions, Greeks (where returned), expiration, strike.
6. **Corporate actions** — splits, mergers, spin-offs.
7. **Order placement — equities** — live order send via `OrderManager`.
8. **Order placement — options** — live option order send.
9. **Order status / cancel / modify** — mid-lifecycle order management.
10. **Streaming** — real-time fills, account deltas, market data.

---

## 3 — Per-broker state as of 2026-04-22

### IBKR (Interactive Brokers)

**Account type dogfooded:** Taxable (founder IBKR $1.47M equity, 2.13× leverage, margin currently used $1.67M).

| Capability | State | Notes + code path |
|------------|-------|-------------------|
| Accounts sync | LIVE | `backend/services/portfolio/ibkr/flex_query_service.py`; FlexQuery nightly + on-demand |
| Positions sync | LIVE | Gateway `reqPositions` + FlexQuery reconciliation |
| Trades / transactions | LIVE | FlexQuery sections `Trades`, `CashTransactions`, `Dividends`, `Transfers`, `CorporateActions` |
| Tax lots | LIVE ([D140](../KNOWLEDGE.md) verifying) | `OpenPositions` FlexQuery section + FIFO matcher for option lots |
| Options data | LIVE | Gateway positions include options; FlexQuery `OptionEAE` section |
| Corporate actions | LIVE | FlexQuery `CorporateActions` section |
| Order placement — equities | **LIVE** | `ib_insync` via `backend/services/clients/ibkr_client.py` → `backend/services/execution/broker_router.py` |
| Order placement — options | **LIVE** | Same client; option `Contract` type |
| Order status / cancel / modify | **LIVE** | `ib_insync` streaming + `OrderManager` state machine |
| Streaming | **LIVE** | `ib_insync` WS subscriptions; account updates, fills, market data |

**Gaps**: None for v1. G22 FlexQuery validator per [handoff](../handoffs/2026-04-21-g22-shipped-next-g23.md) re-verifies tax-lot and corporate-action fidelity in W8.

---

### Schwab

**Account type dogfooded:** HSA (founder Schwab HSA $33k, equities only — no options trading enabled per founder clarification 2026-04-22).

| Capability | State | Notes + code path |
|------------|-------|-------------------|
| Accounts sync | LIVE | OAuth via `backend/services/clients/schwab_client.py`; `backend/services/portfolio/schwab_sync_service.py` |
| Positions sync | LIVE | `/accounts/{id}/positions` endpoint |
| Trades / transactions | LIVE | `/accounts/{id}/transactions` endpoint; normalized via `schwab_sync_service.py` |
| Tax lots | **PARTIAL** | Partially returned on non-ACATS positions; missing on ACATS-transferred lots (founder symptom) — see [`PORTFOLIO_SYNC_COMPLETENESS_2026Q2.md`](PORTFOLIO_SYNC_COMPLETENESS_2026Q2.md) |
| Options data | **PARTIAL** ([D139](../KNOWLEDGE.md) verifying) | `positionEffect` classification fix merged; **verification in prod pending per [D120](../KNOWLEDGE.md)**; HSA account will not see options data regardless (no options trading enabled) |
| Corporate actions | PARTIAL | Reflected in transactions history; no dedicated endpoint |
| Order placement — equities | **PLANNED (W5)** | Client methods exist; not routed through `OrderManager` |
| Order placement — options | **PLANNED (W5)** | Client methods exist; not routed |
| Order status / cancel / modify | PLANNED (W5) | Partially implemented; full polling + cancel pending |
| Streaming | — | Schwab streaming API planned Phase 5 |

**ACATS cost-basis strategy**: see [`PORTFOLIO_SYNC_COMPLETENESS_2026Q2.md`](PORTFOLIO_SYNC_COMPLETENESS_2026Q2.md) §5 for 4-path recovery (broker API → 1099-B parse → CSV import → manual entry).

---

### TastyTrade

**Account type dogfooded:** Not currently.

| Capability | State | Notes + code path |
|------------|-------|-------------------|
| Accounts sync | LIVE | TastyTrade SDK via `backend/services/clients/tastytrade_client.py` |
| Positions sync | LIVE | SDK `accounts.positions.all()` |
| Trades / transactions | LIVE | SDK `accounts.transactions.get()` |
| Tax lots | LIVE | SDK returns lot-level detail |
| Options data | LIVE | Rich options support; Greeks returned |
| Corporate actions | LIVE | SDK exposes |
| Order placement — equities | **PLANNED (W5)** | SDK supports; not routed |
| Order placement — options | **PLANNED (W5)** | SDK supports multi-leg complex orders; not routed |
| Order status / cancel / modify | PLANNED (W5) | SDK supports |
| Streaming | PARTIAL | SDK streamer available; not integrated |

---

### E*TRADE

| Capability | State | Notes |
|------------|-------|-------|
| Accounts sync | PARTIAL (bronze scaffold) | Per [D130](../KNOWLEDGE.md); read-only OAuth scaffolding |
| Positions sync | PARTIAL | Scaffolded |
| Trades / transactions | PARTIAL | Scaffolded |
| Tax lots | PLANNED | Phase 5 |
| Options data | PLANNED | Phase 5 |
| Corporate actions | PLANNED | Phase 5 |
| Order placement — equities | — | Not on v1 roadmap |
| Order placement — options | — | Not on v1 roadmap |
| Order status / cancel / modify | — | — |
| Streaming | — | — |

---

### Tradier

| Capability | State | Notes |
|------------|-------|-------|
| Accounts sync | PARTIAL (bronze scaffold) | Public API via token; well-documented options layer |
| Positions sync | PARTIAL | |
| Trades / transactions | PARTIAL | |
| Tax lots | PLANNED | |
| Options data | PLANNED | Natural option-chain provider; explore Phase 5 |
| Corporate actions | PLANNED | |
| Order placement — equities | PLANNED (Phase 5) | Straightforward REST API; potential future trading broker |
| Order placement — options | PLANNED (Phase 5) | |
| Order status / cancel / modify | PLANNED | |
| Streaming | PLANNED | WebSocket available |

---

### Coinbase

| Capability | State | Notes |
|------------|-------|-------|
| Accounts sync | PARTIAL (bronze scaffold) | Crypto-only; separate asset-class treatment |
| Positions sync | PARTIAL | |
| Trades / transactions | PARTIAL | |
| Tax lots | PARTIAL | Coinbase provides cost basis on sales |
| Options data | — | N/A (Coinbase does not offer equity options) |
| Corporate actions | — | N/A |
| Order placement — equities | — | — |
| Order placement — options | — | — |
| Order status / cancel / modify | — | — |
| Streaming | PLANNED | Coinbase WS |

---

### Alpaca

**State: DROPPED** per [D128](../KNOWLEDGE.md) / PR #392 (`db6fd281`). No plan to re-add.

**Why dropped**:
- Fractional shares diverged from IBKR/Schwab/Tastytrade whole-share world; tax-lot logic became a special case per-position-per-broker.
- No options → covered by Tastytrade already.
- Paper-trading environment reduced value of live routing (we have `SimulatedOrderManager` for paper).
- Maintenance burden not justified by user demand.

---

### Plaid Investments (explicit no for v1)

**State: REJECTED for v1** per [D129](../KNOWLEDGE.md).

**Why rejected**:
- Read-only; no write-path to orders.
- No options data.
- Adds custody middleware with its own failure modes (auth refresh, re-consent, rate limits).
- v1 ships direct-connect brokers where we own the sync contract end-to-end.
- Revisit Month 12 if direct-connect broker roster stalls.

---

### Read-only brokers planned post-v1 (Phase 5)

| Broker | Why important | Expected path |
|--------|--------------|--------------|
| **Fidelity** | Largest HSA provider; many HNW users hold retirement assets here | Bronze pattern; OAuth or authorized CSV import |
| **Robinhood** | Onboarding funnel wedge for retail traders graduating to Pro | Read-only API where available; fallback 1099-B import |
| **Webull** | Similar retail segment | Read-only API |
| **M1 Finance** | Pie investors (HNW alt model) | Read-only API |
| **Public.com** | Fractional-share social investor | Read-only API |

These are **Phase 5 (post-v1)**; listed for tracking only.

---

## 4 — Roll-up matrix (all brokers, current state)

| Broker | Accounts | Positions | Trades | Tax lots | Options | Corp act | Eq order | Opt order | Status/cancel | Streaming |
|--------|----------|-----------|--------|----------|---------|----------|----------|-----------|---------------|-----------|
| IBKR | LIVE | LIVE | LIVE | LIVE | LIVE | LIVE | **LIVE** | **LIVE** | LIVE | LIVE |
| Schwab | LIVE | LIVE | LIVE | PARTIAL | PARTIAL | PARTIAL | PLANNED W5 | PLANNED W5 | PLANNED | — |
| Tastytrade | LIVE | LIVE | LIVE | LIVE | LIVE | LIVE | PLANNED W5 | PLANNED W5 | PLANNED | PARTIAL |
| E*TRADE | PARTIAL | PARTIAL | PARTIAL | PLANNED | PLANNED | PLANNED | — | — | — | — |
| Tradier | PARTIAL | PARTIAL | PARTIAL | PLANNED | PLANNED | PLANNED | PLANNED (P5) | PLANNED (P5) | PLANNED | PLANNED |
| Coinbase | PARTIAL | PARTIAL | PARTIAL | PARTIAL | — | — | — | — | — | PLANNED |
| Alpaca | DROPPED | DROPPED | DROPPED | DROPPED | — | DROPPED | DROPPED | — | DROPPED | DROPPED |
| Plaid | — | — | — | — | — | — | — | — | — | — |
| Fidelity / RH / Webull / M1 / Public | PLANNED P5 | PLANNED P5 | PLANNED P5 | PLANNED P5 | PLANNED P5 | — | — | — | — | — |

---

## 5 — Snowball parity gaps (read-side)

Snowball Analytics is the user-facing competitor we measure read-side parity against. Gaps:

| Snowball capability | AxiomFolio state | Plan |
|---------------------|-----------------|------|
| 8+ broker support | 3 LIVE (IBKR/Schwab/TT) + scaffolds | Phase 5 adds Fidelity / RH / Webull / M1 / Public |
| Bank & credit card aggregation | — (intentional exclusion) | Not on roadmap — we are a portfolio platform, not a PFM |
| Dividend calendar | LIVE | — |
| Drawdown visualization | LIVE | — |
| Allocation treemap | LIVE | — |
| Rebalancing suggestions | PARTIAL (rule-based, not AUM-index-based) | Improve at Wave 4 |
| Auto-trade on every broker | **NOT MATCHED BY SNOWBALL** | Our structural edge |
| Tax-aware exits | **NOT MATCHED BY SNOWBALL** | Our structural edge |

Snowball cannot match items 7 and 8 without becoming a broker or a custodian. These are the retention anchors.

---

## 6 — Priority targets (next 6 months)

### Tier-zero (blocking v1 launch)

1. **Wave 8 — Schwab ACATS cost-basis recovery**: 4-path fallback. Blocks FileFree 1.1.0 (W3.7) which blocks Quant Desk tax-alpha moat.
2. **Wave 5 — Multi-broker live trading** (Schwab + TastyTrade through `OrderManager`): blocks Pro+ "autotrade on every broker" tagline.

### Tier-one (v1 launch nice-to-have)

3. **Schwab streaming**: better UX; not launch-critical.
4. **Tradier integration** as second options-rich broker: future-proofing.

### Tier-two (post-launch)

5. **Fidelity / RH / Webull / M1 / Public** read-only via bronze.
6. **Plaid revisit**: Month 12 if direct-connect stalls.

---

## 7 — ACATS cost-basis recovery playbook

Applied per-broker, but immediately urgent for **Schwab** (founder HSA symptom).

### Path 1 — Broker-native (try first)

Fetch `/accounts/{id}/positions` with full detail flags. Schwab sometimes returns `longOpenProfitLoss`, `averagePrice`, and per-lot detail on positions originated outside Schwab if the ACATS transfer was complete.

**Gate**: if all lots on all ACATS positions return `costBasis != None`, done.

### Path 2 — 1099-B annual parse

IRS-authoritative. User uploads 1099-B PDF; we parse with existing `pymupdf` stack. Cost-basis fields authoritative for **closed** positions in that tax year. For **open** positions that transferred in, 1099-B does not help directly, but the prior-year broker's year-end statement does.

**Gate**: if user has 1099-B and we can parse it, flag lots as `cost_basis_source=acats_recovered_1099b`.

### Path 3 — CSV import (current-year fallback)

User provides CSV of current-year opens that transferred in. Columns: `symbol, acquired_date, quantity, cost_basis_per_share, total_cost_basis, sub_account_id`.

**Gate**: `cost_basis_source=acats_recovered_csv`. Flag as user-asserted; do not use for IRS-filing-grade exports without disclaimer.

### Path 4 — Manual entry (last resort)

Lot editor UI in `/desk/portfolio/{id}/lots`. User edits individual lots with date + qty + cost. Require explicit "I confirm this data is accurate" checkbox.

**Gate**: `cost_basis_source=manual_entry`. Mark in FileFree 1.1.0 export.

---

## 8 — Schema additions

| Model | Field | Type | Purpose |
|-------|-------|------|---------|
| `TaxLot` | `cost_basis_source` | Enum: `broker_reported \| acats_recovered_csv \| acats_recovered_1099b \| manual_entry \| unknown` | Surface recovery path in UI + FileFree |
| `TaxLot` | `cost_basis_quality` | Enum: `high \| medium \| low` | UI indicator; disable tax-aware exit on `low` without user override |
| `TaxLot` | `acats_transferred` | Boolean | Flag positions that originated from ACATS transfer |
| `TaxLot` | `prior_broker_id` | Nullable FK | Link back to prior broker account if known (helps cross-broker wash-sale) |
| `BrokerConnection` | `options_enabled` | Boolean | Schwab HSA is equities-only; avoid showing phantom "missing options" warnings |

Migrations land in Wave 8.1.

---

## 9 — Update log

| Date | Change |
|------|--------|
| 2026-04-22 | Initial tracker created (Ch 7 companion) |

Update this table on every state change.

---

*Every wave that touches broker capabilities must update the relevant row + the roll-up matrix in §4 and append to §9.*
