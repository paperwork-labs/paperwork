## Frontend UI (Chakra v3 + Ladle)

### What we’re using
- **React + Vite**: `frontend/`
- **Chakra UI v3**: design system + primitives via a single `system` configuration.
- **Ladle**: lightweight component explorer (Storybook alternative).

### Chakra v3 architecture in this repo

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
We build “app primitives” on top of Chakra v3 components so pages stay consistent:
- `frontend/src/components/ui/AppCard.tsx`
- `frontend/src/components/ui/Page.tsx`
- `frontend/src/components/ui/FormField.tsx`
- `frontend/src/components/ui/Pagination.tsx`

Pages should prefer **semantic tokens** like `bg.card`, `border.subtle`, `fg.muted` instead of hardcoded colors.

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

The pattern is implemented via `SymbolLink` (renders a `PopoverRoot` for hover) and `ChartSlidePanel` (renders a `DialogRoot` for the slide-out). A `ChartContext` React context passes the `openChart` callback to all nested `SymbolLink` instances without prop drilling.

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
- Upgrades should be done by updating versions and validating:
  - `docker compose --project-name axiomfolio --env-file infra/env.dev -f infra/compose.dev.yaml exec -T frontend npm test`
  - `docker compose --project-name axiomfolio --env-file infra/env.dev -f infra/compose.dev.yaml exec -T frontend npm run build`
  - `make ladle-build`


