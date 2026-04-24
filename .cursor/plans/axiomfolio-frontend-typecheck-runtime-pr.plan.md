---
name: Frontend type-check, runtime fixes, and PR feedback
overview: Fix frontend type-check so make test-all passes; fix Vite 504 / dynamic import and duplicate React key MSTR; incorporate PR review comments once provided.
todos:
  - id: typecheck-sellorder
    content: Type orderStatus in SellOrderModal (OrderStatusResult), fix ReactNode usage
    status: pending
  - id: typecheck-collapsible
    content: Remove or type-assert unmountOnExit on Collapsible.Content in MarketDashboard
    status: pending
  - id: typecheck-workspace
    content: Type lots.reduce accumulator as LotTotals in PortfolioWorkspace
    status: pending
  - id: runtime-vite
    content: Document Vite 504 fix (clear cache, restart dev server)
    status: pending
  - id: runtime-duplicate-key
    content: Fix duplicate key MSTR in MarketDashboard (unique keys per list)
    status: pending
  - id: pr-orders-auth
    content: "PR: portfolio_orders.py — add get_current_user, scope by user, persist user on Order"
    status: pending
  - id: pr-ibkr-margin-type
    content: "PR: ibkr_client what_if_order — return numeric floats for margin fields (not str)"
    status: pending
  - id: pr-ibkr-live-gate
    content: "PR: ibkr_client place_order — hard-block live unless ALLOW_LIVE_TRADING + confirm"
    status: pending
  - id: pr-order-service-est-value
    content: "PR: order_service — est_value for market/stop using preview/price fallback"
    status: pending
  - id: pr-finviz-import
    content: "PR: FinvizHeatMap.tsx — move HEAT_MAP_COLORS import to top of module"
    status: pending
  - id: pr-sellorder-effective-price
    content: "PR: SellOrderModal — effectivePrice use stopPrice when orderType === 'stop'"
    status: pending
  - id: pr-orders-invalidate
    content: "PR: PortfolioOrders.tsx — invalidateQueries(['allOrders']) not 'allOrders'"
    status: pending
  - id: pr-section-heading-a11y
    content: "PR: MarketDashboard SectionHeading — keyboard focus + Enter/Space handlers"
    status: pending
  - id: pr-workspace-invalidate
    content: "PR: PortfolioWorkspace invalidateLotQueries — use real keys e.g. portfolioStocks"
    status: pending
  - id: pr-compose-readonly
    content: "PR: compose.dev.yaml IBC_ReadOnlyApi — opt-in via env or comment + override file"
    status: pending
isProject: false
---

# Frontend type-check, runtime fixes, and PR feedback

## PR review comments (Copilot, PR 215)

Actionable items from the PR; implement when executing the plan.

1. **backend/api/routes/portfolio_orders.py** — **Authn/authz**
  Order routes do not use `get_current_user` or scope by user; any authenticated caller can list/submit/cancel all orders. Add `Depends(get_current_user)`, persist a user identifier on the `Order` row, and enforce ownership in get/list/submit/cancel/poll.
2. **backend/services/clients/ibkr_client.py** (what_if_order, ~line 633) — **Margin field types**
  `what_if_order()` returns margin fields as strings (`str(state.maintMarginChange)` etc.). These are persisted into Float columns and can cause DB/coercion issues. Return numeric floats (or store as string consistently); prefer floats to match schema.
3. **backend/services/clients/ibkr_client.py** (place_order, ~line 690) — **Live trading gate**
  `place_order()` allows LIVE orders when `ENABLE_TRADING` is true and only logs a warning. Add a hard gate: block non-paper execution unless an explicit setting (e.g. `ALLOW_LIVE_TRADING`) is enabled and a confirmation (e.g. `IBKR_LIVE_TRADING_CONFIRMED=yes`) is set; otherwise return rejected with a clear error.
4. **backend/services/order_service.py** (~line 59) — **Risk guardrail est_value**
  `est_value = quantity * (limit_price or 0)` makes `MAX_ORDER_VALUE` ineffective for market/stop (est_value becomes 0). Use a better notional estimate: e.g. from preview (`estimated_gross_value`, `notional_value`) or whatIf response (`estimated_fill_price`, `last_price`, `mark_price`) so the guardrail applies to all order types.
5. **frontend/src/components/charts/FinvizHeatMap.tsx** (line 21) — **Import order**
  `HEAT_MAP_COLORS` import is after type/interface declarations. Move it to the top of the module with other imports for consistency and lint.
6. **frontend/src/components/orders/SellOrderModal.tsx** (~line 131) — **effectivePrice for stop**
  `effectivePrice` ignores `stopPrice` for stop orders (uses `currentPrice`), making estimated proceeds misleading. Use `stopPrice` when `orderType === 'stop'`, and keep limit/stop logic consistent in the preview step.
7. **frontend/src/pages/portfolio/PortfolioOrders.tsx** (lines 90, 247) — **Query key shape**
  Query key is `['allOrders']` but invalidation uses `'allOrders'` (string). React-query won’t match. Use `invalidateQueries(['allOrders'])` (or match key shape) in both cancel and refresh.
8. **frontend/src/pages/MarketDashboard.tsx** (SectionHeading, ~line 693) — **Keyboard a11y**
  SectionHeading is clickable with `role="button"` but not keyboard-focusable and has no Enter/Space handlers. Use a real `<Button>`/`<IconButton>` or add `tabIndex={0}` and `onKeyDown` for Enter/Space.
9. **frontend/src/pages/PortfolioWorkspace.tsx** (~line 356) — **invalidateLotQueries keys**
  `invalidateLotQueries()` invalidates `'workspaceTaxLots'`, `'portfolioTaxLots'`, `'positions'`, which may not match actual query keys (e.g. `usePositions()` uses `['portfolioStocks', accountId]`). Invalidate the real keys (e.g. `['portfolioStocks']` prefix and relevant tax-lot keys) so save/delete refreshes holdings and tax lot views.
10. **infra/compose.dev.yaml** (~line 208) — **IBC_ReadOnlyApi default**
  `IBC_ReadOnlyApi: "no"` in dev enables order placement from the gateway; high-risk default. Make it opt-in via an env var (default read-only) or add a prominent comment and a separate override compose file for trading-enabled dev.

---

## 1. Type-check fixes (make test-all / frontend-typecheck)


| File                                                                    | Error                                                                                                                     | Fix                                                                                                                                                                       |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [SellOrderModal.tsx](frontend/src/components/orders/SellOrderModal.tsx) | `unknown` not assignable to `ReactNode` for `orderStatus.id`, `.broker_order_id`, `.filled_quantity`, `.filled_avg_price` | Define `OrderStatusResult` interface; type `orderStatus` state as `OrderStatusResult | null`; ensure rendered values are valid ReactNode (e.g. `String(orderStatus.id)`). |
| [MarketDashboard.tsx](frontend/src/pages/MarketDashboard.tsx)           | `unmountOnExit` does not exist on `CollapsibleContentProps`                                                               | Remove `unmountOnExit` from both `<Collapsible.Content>` usages (lines 1095, 1269), or use type assertion if you need the behavior.                                       |
| [PortfolioWorkspace.tsx](frontend/src/pages/PortfolioWorkspace.tsx)     | `LotRow` has no `cost`/`value`; `acc.shares`/`totals.shares` possibly undefined                                           | Type reducer: `lots.reduce<{ shares: number; cost: number; value: number }>(...)` so accumulator and `totals` are typed; keep `(totals.shares || 1)` for division.        |


---

## 2. Runtime: Vite 504 (Outdated Optimize Dep) and dynamic import failures

**Symptoms:**  
`504 (Outdated Optimize Dep)` on deps like `lightweight-charts.js`, `react-icons_ri.js`, `@dnd-kit_*.js`, and then:

- `TypeError: Failed to fetch dynamically imported module: .../PortfolioWorkspace.tsx`
- Same for `PortfolioCategories.tsx` (and other route chunks that pull in those deps).

**Cause:** Vite’s pre-bundled dependency cache (e.g. `node_modules/.vite/deps`) is out of date after installs or version changes, so the browser requests old hashes and the dev server returns 504.

**Fix:**

1. Stop the dev server.
2. Clear Vite’s cache:
  `rm -rf frontend/node_modules/.vite`  
   (or from repo root: `rm -rf node_modules/.vite` if frontend lives there).
3. Restart: `npm run dev` (or `make up` / your usual frontend command).

If it persists, try a clean install: `rm -rf node_modules package-lock.json && npm install` then repeat the cache clear and restart.

**Doc:** Add a short “Dev server 504 / Failed to fetch module” note to [docs/FRONTEND_UI.md](docs/FRONTEND_UI.md) or [docs/ONBOARDING.md](docs/ONBOARDING.md) under troubleshooting: clear `node_modules/.vite` and restart.

---

## 3. Runtime: Duplicate React key `MSTR`

**Symptom:**  
`Encountered two children with the same key, 'MSTR'. Keys should be unique...`

**Cause:** Some list in [MarketDashboard.tsx](frontend/src/pages/MarketDashboard.tsx) is keyed only by `symbol`. The API or derived data can contain the same symbol more than once (e.g. MSTR in two sectors or two setup lists), so two siblings get `key="MSTR"`.

**Fix:** Use a key that is unique per item in that list, not just per symbol. Options:

- **Preferred:** Include the index in the key so duplicates are allowed:  
`key={\`sector-${r.symbol}-${index}}`(and similarly for other maps that use`key={r.symbol}`or`key={item.symbol}`).
- **Alternative:** Dedupe by symbol before render so each symbol appears once; then `key={r.symbol}` is safe.

**Where to change:** In [MarketDashboard.tsx](frontend/src/pages/MarketDashboard.tsx), every `.map()` that uses `key={\`…-${r.symbol}}`or`key={item.symbol}` (or similar) and can have duplicate symbols should use index in the key. Likely spots include:

- Line 1047: `sectorRows.map((r) => ... key={\`sector-${r.symbol}})` → add index.
- Lines 1003, 1191, 1234, 1306, 1320, 1347, 1376, 1412, 1433: same idea for `entry`, `exit`, `div-b`, `div-l`, `td-`, `gap-`, `earn-`, `fund-` and action-queue lists.

Use a single pattern, e.g. `key={\`${sectionId}-${row.symbol}-${i}}` in each map callback.

---

## 4. Verification

- **Type-check:** From repo root run `make frontend-typecheck` (or `make test-all`); exit code 0.
- **Runtime:** After Vite cache clear and key fixes, run dev server, open dashboard and portfolio routes; no 504, no “Failed to fetch module”, no duplicate-key warning for MSTR.
- **PR items:** Implement each of the 10 Copilot items in section above; re-run tests and smoke where relevant.

---

## Summary


| Item                      | Action                                                                                                      |
| ------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Type-check                | SellOrderModal (OrderStatusResult), MarketDashboard (unmountOnExit), PortfolioWorkspace (LotTotals reduce). |
| Vite 504 / dynamic import | Clear `node_modules/.vite`, restart dev server; optional doc note.                                          |
| Duplicate key MSTR        | Unique keys (symbol + index) in MarketDashboard list maps.                                                  |
| PR: portfolio_orders      | Auth: get_current_user, scope by user, persist user on Order.                                               |
| PR: ibkr_client           | what_if numeric margin fields; place_order live-trading hard gate.                                          |
| PR: order_service         | est_value for market/stop from preview/price fallback.                                                      |
| PR: FinvizHeatMap         | Move HEAT_MAP_COLORS import to top.                                                                         |
| PR: SellOrderModal        | effectivePrice = stopPrice when orderType === 'stop'.                                                       |
| PR: PortfolioOrders       | invalidateQueries(['allOrders']).                                                                           |
| PR: SectionHeading        | Keyboard focus + Enter/Space (or use Button).                                                               |
| PR: PortfolioWorkspace    | invalidateLotQueries use real keys (portfolioStocks etc.).                                                  |
| PR: compose.dev           | IBC_ReadOnlyApi opt-in or comment + override file.                                                          |


