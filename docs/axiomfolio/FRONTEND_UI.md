---
owner: engineering
last_reviewed: 2026-04-24
doc_kind: reference
domain: design
status: active
---
# Frontend UI (Radix + Tailwind + Ladle)

Frontend structure, theming, and Ladle. For route-to-page mapping see [ARCHITECTURE.md](ARCHITECTURE.md#frontend-pages).

---

## Table of contents

- [What we're using](#what-were-using)
- [UI stack in this repo](#ui-stack-in-this-repo)
- [Portfolio component map](#portfolio-component-map)
- [Skeleton loading](#skeleton-loading)
- [Pagination pattern](#pagination-pattern)
- [AccountFilterWrapper pattern](#accountfilterwrapper-pattern)
- [Ladle (component explorer)](#ladle-component-explorer)
- [Charts](#charts)
- [Symbol interaction](#symbol-interaction-pattern)
- [Chart semantic tokens](#chart-semantic-tokens)
- [Dashboard components](#dashboard-components)
- [Keeping UI libraries current](#keeping-ui-libraries-current)
- [Troubleshooting](#troubleshooting)

---

## What we're using

- **React + Vite**: `frontend/`
- **Radix UI** (`@radix-ui/react-*`): accessible primitives (dialog, popover, tabs, tooltip, etc.).
- **Tailwind CSS v4** (`@tailwindcss/vite`): utility styling and layout; design tokens live in `frontend/src/index.css` as CSS variables.
- **shadcn-style wrappers**: composed components under `frontend/src/components/ui/` (Button, Card, Dialog, …) built from Radix + `class-variance-authority` + `tailwind-merge`.
- **Ladle**: lightweight component explorer (Storybook alternative).
- **Framer Motion** (`framer-motion` v12.38.0): animations in `frontend/src/pages/AdminAgent.tsx`, `frontend/src/components/agent/AgentChatPanel.tsx`, `frontend/src/components/chat/ChatPanel.tsx`, and `frontend/src/components/chat/ChatBubble.tsx`.

## UI stack in this repo

#### 1) Single source of truth: `index.css`

Semantic colors and chart tokens are defined as CSS custom properties on `:root` and `.dark` in:

- `frontend/src/index.css`

Examples: `--bg-canvas`, `--fg-muted`, `--border-subtle`, `--chart-success`, `--status-danger`. Tailwind maps shadcn-style tokens (`--primary`, `--card`, …) in the same file via `@theme inline`.

Legacy `frontend/src/theme/system.ts` is a **stub** (Chakra was removed from the app root); extend the Tailwind/CSS layer instead.

#### 2) App shell

- `frontend/src/App.tsx` wraps the tree with **`ColorModeProvider`** (`frontend/src/theme/colorMode.tsx`) and TanStack Query — no Chakra `Provider`.

#### 3) App-level primitives

Shared building blocks:

- `frontend/src/components/ui/AppCard.tsx`, `Page.tsx`, `PageHeader.tsx`, `FormField.tsx`, `Pagination.tsx`, `button.tsx`, `card.tsx`, `dialog.tsx`, etc.

Prefer **semantic CSS variables** (e.g. `rgb(var(--bg-panel) / 1)`, `text-muted-foreground`, `border-border`) over raw hex in new code.

### Portfolio component map

- **Pages**: PortfolioOverview, PortfolioHoldings, PortfolioOptions, PortfolioTransactions, PortfolioCategories, PortfolioWorkspace, PortfolioOrders (`frontend/src/pages/portfolio/`).
- **Shared** (`frontend/src/components/shared/`): StatCard, StageBar, StageBadge, PnlText, Skeleton (StatCardSkeleton, TableSkeleton, ChartSkeleton).
- **UI**: AccountFilterWrapper, SortableTable (with debounced filter inputs), Pagination.
- **Utils**: `frontend/src/utils/portfolio.ts` – buildAccountsFromBroker, toStartEnd, timeAgo, stageCountsFromPositions, sectorAllocationFromPositions, topMoversFromPositions.
- **Account filter**: Global selection via AccountContext; `useAccountContext().selected` used for API filters and selector display; sync to context on change in AccountFilterWrapper.

### Skeleton loading

Use `StatCardSkeleton`, `TableSkeleton`, `ChartSkeleton` from `frontend/src/components/shared/Skeleton.tsx` for loading states instead of spinner-only so layout is communicated.

**Pattern**: When using `AccountFilterWrapper`, pass optional `loadingComponent` to show a skeleton instead of the default Spinner when account/data is loading:

```tsx
<AccountFilterWrapper
  data={positions}
  accounts={accounts}
  loading={positionsQuery.isLoading || accountsQuery.isLoading}
  loadingComponent={<TableSkeleton rows={8} cols={6} />}
>
  {(filteredData, filterState) => <SortableTable data={filteredData} ... />}
</AccountFilterWrapper>
```

For page-level loading (e.g. activity), render the skeleton when the main query is loading and the table when not:

```tsx
{activityQuery.isLoading ? (
  <TableSkeleton rows={10} cols={7} />
) : (
  <SortableTable data={activity} ... />
)}
```

### Pagination pattern

Use `Pagination` from `frontend/src/components/ui/Pagination.tsx` with local state for `page` and `pageSize`; pass `total` from the API (e.g. activity response `total`). Reset `page` to 1 when filters change (e.g. via `useEffect` on filter deps):

```tsx
const [page, setPage] = useState(1);
const [pageSize, setPageSize] = useState(50);
useEffect(() => setPage(1), [dateRange, category, selected]);

<Pagination
  page={page}
  pageSize={pageSize}
  total={total}
  onPageChange={setPage}
  onPageSizeChange={(ps) => { setPageSize(ps); setPage(1); }}
/>
```

### AccountFilterWrapper pattern

- Wraps account selector (All / per-account) and filters data by selected account. Children receive `(filteredData, filterState)`.
- When `loading` is true: if `loadingComponent` is provided, it is rendered; otherwise a Spinner + "Loading account data…" is shown.
- Use `loadingComponent` with `TableSkeleton` or custom skeleton so users see layout while data loads.

### Ladle (component explorer)

#### Run Ladle locally

From the repo root (Docker):

```bash
make ladle-up
```

Ladle runs on port **61000** (see `frontend/package.json`), via a dedicated compose service in `infra/compose.dev.yaml`.

#### Build Ladle

```bash
make ladle-build
```

#### Ladle provider setup

Ladle wraps stories with the same **`ColorModeProvider`** as the app:

- `frontend/.ladle/components.tsx`

#### Ladle story inventory

Stories live under `frontend/src/stories/`:

- **Brand.stories.tsx** — brand/logo
- **Components.stories.tsx** — shared components
- **LoadingStates.stories.tsx** — skeletons, spinners
- **Charts.stories.tsx** — Recharts, sparkline
- **Tokens.stories.tsx** — theme tokens
- **Accounts.stories.tsx** — account selector, filter
- **UIPrimitives.stories.tsx** — buttons, inputs, cards
- **DashboardLayout.stories.tsx** — layout shell
- **Tables.stories.tsx** — SortableTable

### Charts

The app uses several charting approaches depending on the use case:

| Library | Component | Purpose |
|---------|-----------|---------|
| **Recharts** | `BarChart`, `ComposedChart`, `ScatterChart` | Market Dashboard charts: 52-week range histogram, breadth over time, Relative Rotation Graph (RRG) |
| **TradingView Widget** | `TradingViewChart` (`components/charts/TradingViewChart.tsx`) | Full interactive price charts with indicators, used in the slide-out symbol panel |
| **Sparkline** | `Sparkline` (`components/charts/Sparkline.tsx`) | Mini bar charts for quick price visualization in popovers and table cells |
| **SymbolChartWithMarkers** | `SymbolChartWithMarkers` (`components/charts/SymbolChartWithMarkers.tsx`) | Lightweight-charts based candle charts with trade markers |

Recharts components use theme-aware colors via hooks that read `--chart-*` / semantic CSS variables (see `useChartColors` patterns in dashboard code).

### Symbol Interaction Pattern

Symbols throughout the Market Dashboard follow a hover + click interaction model:

- **Hover** (250ms delay): Opens a popover showing a mini `Sparkline` of the last 20 close prices, current price, and 1-day percentage change. Price data is lazy-fetched from `marketDataApi.getHistory()` and cached in an in-memory `Map` for the session.
- **Click**: Opens a right-edge slide-out panel with a full `TradingViewChart` for the symbol. The panel covers ~50vw on desktop / 90vw on mobile and can be closed via X button, click-away, or Escape.
- **No page navigation**: Symbol clicks stay on the dashboard — there is no redirect to `/market/tracked`.

The pattern is implemented via **ChartContext** + **SymbolLink** + **ChartSlidePanel**: `ChartContext` provides the `openChart` callback to nested `SymbolLink` instances without prop drilling; `SymbolLink` uses a Radix `Popover` for hover (sparkline); `ChartSlidePanel` uses a Radix `Dialog` for the slide-out TradingView chart. Used across Market Dashboard and Portfolio (Holdings, etc.).

### Chart Semantic Tokens

`index.css` defines `--chart-*` RGB triples (and shadcn `--chart-1`…`--chart-5`) for consistent chart styling across light and dark modes. Use these via Tailwind (`text-chart-1`, etc.) or `rgb(var(--chart-success) / 1)` where appropriate.

| Token (examples) | Usage |
|------------------|--------|
| `--chart-danger`, `--chart-success`, `--chart-neutral`, `--chart-warning` | Series and regime-style accents |
| `--chart-area1`, `--chart-area2` | Area fills (e.g. breadth) |
| `--chart-grid`, `--chart-axis`, `--chart-refLine` | Grid and axes |

### Dashboard Components

Reusable sub-components within `MarketDashboard.tsx` (representative list):

| Component | Description |
|-----------|-------------|
| `StatCard` | Compact KPI card with label, value, and optional sub-label |
| `StageBar` | Horizontal stacked bar showing normalized stage distribution |
| `SetupCard` | Card listing symbols matching a trading setup (breakout, pullback, RS leaders) |
| `TransitionList` | List of symbols transitioning between stages with badges |
| `RankMatrix` | Multi-column ranked table (top/bottom performers by metric) |
| `RangeHistogram` | Recharts bar chart showing 52-week range distribution |
| `BreadthChart` | Recharts composed chart showing % above 50DMA/200DMA over time |
| `RRGChart` | Recharts scatter chart implementing Relative Rotation Graph with quadrant annotations |
| `SymbolLink` | Interactive symbol text with hover sparkline popover and click-to-chart |
| `ChartSlidePanel` | Right-edge slide-out dialog containing a TradingView chart |
| `SparklinePopoverContent` | Popover body that lazy-fetches and displays a mini sparkline |

### Keeping UI libraries current

- Frontend dependencies live in `frontend/package.json`.
- Upgrades: update versions, then validate from **repo root** using the [Makefile](../Makefile) (see [docs/README.md](README.md)#makefile-quick-reference):
  - `make frontend-check` (lint + type-check + test), or `make test-frontend`
  - `make ladle-build`
  - For a full production build, run it inside the frontend container (e.g. with dev stack up: `docker compose ... exec frontend npm run build`).

### Troubleshooting

- **Dev server 504 / Failed to fetch module**: If you see `504 (Outdated Optimize Dep)` or `TypeError: Failed to fetch dynamically imported module` in the browser, Vite's pre-bundled dependency cache is stale. Stop the dev server, run `rm -rf frontend/node_modules/.vite`, then restart (`npm run dev` or your usual frontend command). If it persists, try a clean install: `rm -rf node_modules package-lock.json && npm install`, then clear the cache again and restart.
