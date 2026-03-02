# Frontend UI (Chakra v3 + Ladle)

Frontend theming, components, and Ladle. For route-to-page mapping see [ARCHITECTURE.md](ARCHITECTURE.md#frontend-pages).

---

## Table of contents

- [What we're using](#what-were-using)
- [Chakra v3 architecture](#chakra-v3-architecture-in-this-repo)
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

---

## What we're using

- **React + Vite**: `frontend/`
- **Chakra UI v3**: design system + primitives via a single `system` configuration.
- **Ladle**: lightweight component explorer (Storybook alternative).

## Chakra v3 architecture in this repo

#### 1) Single source of truth: `system`
The canonical Chakra v3 system lives in:
- `frontend/src/theme/system.ts`

It defines:
- **Tokens**: core brand palette, typography, radii.
- **Semantic tokens**: `bg.*`, `fg.*`, `border.*` for consistent light/dark theming.
- **Recipes**: base styles for `button`, `input`, etc.

The app mounts Chakra like this:
- `frontend/src/App.tsx` → `<ChakraProvider value={system}>`

#### 2) App-level primitives

We build "app primitives" on top of Chakra v3 components so pages stay consistent:
- `frontend/src/components/ui/AppCard.tsx`
- `frontend/src/components/ui/Page.tsx`
- `frontend/src/components/ui/FormField.tsx`
- `frontend/src/components/ui/Pagination.tsx`

Pages should prefer **semantic tokens** like `bg.card`, `border.subtle`, `fg.muted` instead of hardcoded colors.

### Portfolio component map

- **Pages**: PortfolioOverview, PortfolioHoldings, PortfolioOptions, PortfolioTransactions, PortfolioCategories, PortfolioWorkspace (under `frontend/src/pages/portfolio/`).
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
Ladle uses the same Chakra v3 system provider as the app:
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

Recharts components use theme-aware colors via the `useChartColors()` hook in `MarketDashboard.tsx`, which resolves `chart.*` semantic tokens at runtime.

### Symbol Interaction Pattern

Symbols throughout the Market Dashboard follow a hover + click interaction model:

- **Hover** (250ms delay): Opens a popover showing a mini `Sparkline` of the last 20 close prices, current price, and 1-day percentage change. Price data is lazy-fetched from `marketDataApi.getHistory()` and cached in an in-memory `Map` for the session.
- **Click**: Opens a right-edge slide-out panel with a full `TradingViewChart` for the symbol. The panel covers ~50vw on desktop / 90vw on mobile and can be closed via X button, click-away, or Escape.
- **No page navigation**: Symbol clicks stay on the dashboard — there is no redirect to `/market/tracked`.

The pattern is implemented via **ChartContext** + **SymbolLink** + **ChartSlidePanel**: `ChartContext` provides the `openChart` callback to nested `SymbolLink` instances without prop drilling; `SymbolLink` renders a `PopoverRoot` for hover (sparkline); `ChartSlidePanel` renders a `DialogRoot` for the slide-out TradingView chart. Used across Market Dashboard and Portfolio (Holdings, etc.).

### Chart Semantic Tokens

The `system.ts` theme defines `chart.*` semantic tokens for consistent chart styling across light and dark modes:

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `chart.danger` | `#DC2626` | `#F87171` | Histogram low-range bins, bearish indicators |
| `chart.success` | `#16A34A` | `#4ADE80` | Histogram high-range bins, bullish indicators |
| `chart.neutral` | `#3B82F6` | `#60A5FA` | Mid-range histogram bins |
| `chart.warning` | `#D97706` | `#FBBF24` | RRG "Weakening" quadrant |
| `chart.area1` | `#16A34A` | `#34D399` | Breadth chart 50DMA area fill |
| `chart.area2` | `#2563EB` | `#60A5FA` | Breadth chart 200DMA area fill |
| `chart.grid` | `rgba(15,23,42,0.08)` | `rgba(255,255,255,0.08)` | Grid lines |
| `chart.axis` | `rgba(15,23,42,0.4)` | `rgba(255,255,255,0.45)` | Axis labels |
| `chart.refLine` | `rgba(15,23,42,0.2)` | `rgba(255,255,255,0.2)` | Reference/zero lines |

### Dashboard Components

Reusable sub-components within `MarketDashboard.tsx`:

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
- Chakra is pinned to v3 (`@chakra-ui/react`).
- Upgrades: update versions, then validate from **repo root** using the [Makefile](../Makefile) (see [docs/README.md](README.md)#makefile-quick-reference):
  - `make frontend-check` (lint + type-check + test), or `make test-frontend`
  - `make ladle-build`
  - If you need a full production build, run it inside the frontend container (e.g. with dev stack up: `docker compose ... exec frontend npm run build`).
