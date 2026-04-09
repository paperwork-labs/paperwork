import React from 'react';
import { useQuery } from '@tanstack/react-query';
import * as Collapsible from "@radix-ui/react-collapsible";
import { Link as RouterLink } from 'react-router-dom';
import {
  BarChart2,
  ChevronDown,
  ChevronRight,
  Grid3X3,
  Layers,
  Loader2,
  RefreshCw,
  TrendingUp,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Page } from '@/components/ui/Page';
import { cn } from '@/lib/utils';
import { heatTextClass, semanticTextColorClass } from '@/lib/semantic-text-color';
import { marketDataApi } from '../services/api';
import { ChartContext, SymbolLink, ChartSlidePanel, PortfolioSymbolsContext } from '../components/market/SymbolChartUI';
import StatCard from '../components/shared/StatCard';
import { usePortfolioSymbols } from '../hooks/usePortfolioSymbols';
import StageBar from '../components/shared/StageBar';
import StageBadge from '../components/shared/StageBadge';
import RegimeBanner from '../components/market/RegimeBanner';
import { useChartColors } from '../hooks/useChartColors';
import { SECTOR_PALETTE } from '../constants/chart';
import { ETF_SYMBOL_SET } from '../constants/etf';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip as RTooltip, ResponsiveContainer, Cell,
  ScatterChart, Scatter, ZAxis, CartesianGrid, ReferenceLine, ReferenceArea, Legend,
  ComposedChart, Area,
} from 'recharts';
import BubbleChart from '../components/charts/BubbleChart';
import { formatDate } from '../utils/format';
import { useUserPreferences } from '../hooks/useUserPreferences';
import useAdminHealth from '../hooks/useAdminHealth';
import { useVolatility, type VolatilityDashboardData } from '../hooks/useVolatility';
import { useSnapshotAggregates } from '../hooks/useSnapshotAggregates';
import { useSnapshotTable as useSnapshotTableHook } from '../hooks/useSnapshotTable';
import ErrorBoundary from '@/components/ErrorBoundary';
import QuadStatusBar from '../components/market/QuadStatusBar';

const TopDownView = React.lazy(() => import('../components/market/TopDownView'));
const BottomUpView = React.lazy(() => import('../components/market/BottomUpView'));
const SectorView = React.lazy(() => import('../components/market/SectorView'));
const HeatmapView = React.lazy(() => import('../components/market/HeatmapView'));

function LazyBubbleChart({ onSymbolClick, collapsed }: { onSymbolClick: (sym: string) => void; collapsed: boolean }) {
  const { data } = useSnapshotTableHook({ sort_by: 'rs_mansfield_pct', sort_dir: 'desc', limit: 200, offset: 0 });
  const rows = data?.rows ?? [];
  if (rows.length === 0) return <p className="py-4 text-center text-sm text-muted-foreground">No data for scatter chart.</p>;
  return (
    <BubbleChart
      data={rows}
      defaultX="perf_1d"
      defaultY="rs_mansfield_pct"
      defaultColor="stage_label"
      defaultSize="market_cap"
      onSymbolClick={onSymbolClick}
    />
  );
}

type DashboardView = 'overview' | 'top-down' | 'bottom-up' | 'sectors' | 'heatmap';

const VIEW_TABS: { key: DashboardView; label: string; icon: React.ElementType }[] = [
  { key: 'overview', label: 'Overview', icon: BarChart2 },
  { key: 'top-down', label: 'Top-Down', icon: TrendingUp },
  { key: 'bottom-up', label: 'Bottom-Up', icon: Grid3X3 },
  { key: 'sectors', label: 'Sectors', icon: Layers },
  { key: 'heatmap', label: 'Heatmap', icon: Grid3X3 },
];

function TableShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="max-h-[min(60vh,520px)] max-w-full overflow-auto rounded-md border border-border">
      <table className="w-full min-w-[560px] border-collapse text-left text-sm">{children}</table>
    </div>
  );
}

const VIEW_KEY = 'axiomfolio:dashboard:view';

type SetupItem = {
  symbol: string;
  stage_label?: string;
  previous_stage_label?: string;
  perf_1d?: number;
  perf_5d?: number;
  perf_20d?: number;
  rs_mansfield_pct?: number;
  current_stage_days?: number;
  momentum_score?: number;
  sector?: string;
};

type StageTransitionItem = {
  symbol: string;
  previous_stage_label?: string;
  stage_label?: string;
  current_stage_days?: number;
  perf_1d?: number;
};

type SectorETFRow = {
  symbol: string;
  sector_name?: string;
  change_1d?: number;
  change_5d?: number;
  change_20d?: number;
  rs_mansfield_pct?: number;
  stage_label?: string;
  days_in_stage?: number;
};

type SectorMomentumItem = {
  sector: string;
  count: number;
  avg_perf_20d?: number;
  avg_rs_mansfield_pct?: number;
};

type RangeHistogramBin = { bin: string; count: number };
type BreadthPoint = { date: string; above_sma50_pct: number; above_sma200_pct: number; total: number };
type RRGSector = { symbol: string; name: string; rs_ratio: number; rs_momentum: number };
type EarningsItem = { symbol: string; next_earnings: string; stage_label?: string; rs_mansfield_pct?: number; sector?: string };
type FundamentalLeader = { symbol: string; eps_growth_yoy: number; rs_mansfield_pct: number; pe_ttm?: number | null; stage_label?: string; sector?: string; composite_score: number };
type RSIDivergenceItem = { symbol: string; perf_20d: number; rsi: number; stage_label?: string; sector?: string };
type TDSignalItem = { symbol: string; signals: string[]; stage_label?: string; perf_1d?: number; sector?: string };
type GapLeader = { symbol: string; gaps_up: number; gaps_down: number; total_gaps: number; stage_label?: string; sector?: string };

type DashboardPayload = {
  tracked_count?: number;
  snapshot_count?: number;
  latest_snapshot_at?: string;
  coverage?: { status?: string; daily_pct?: number };
  regime?: {
    stage_counts_normalized?: Record<string, number>;
    up_1d_count?: number;
    down_1d_count?: number;
    flat_1d_count?: number;
    above_sma50_count?: number;
    above_sma200_count?: number;
  };
  leaders?: SetupItem[];
  setups?: {
    breakout_candidates?: SetupItem[];
    pullback_candidates?: SetupItem[];
    rs_leaders?: SetupItem[];
  };
  sector_momentum?: SectorMomentumItem[];
  action_queue?: SetupItem[];
  entry_proximity_top?: Array<any>;
  exit_proximity_top?: Array<any>;
  sector_etf_table?: SectorETFRow[];
  entering_stage_2a?: StageTransitionItem[];
  entering_stage_3?: StageTransitionItem[];
  entering_stage_4?: StageTransitionItem[];
  top10_matrix?: Record<string, Array<{ symbol: string; value: number }>>;
  bottom10_matrix?: Record<string, Array<{ symbol: string; value: number }>>;
  range_histogram?: RangeHistogramBin[];
  breadth_series?: BreadthPoint[];
  rrg_sectors?: RRGSector[];
  upcoming_earnings?: EarningsItem[];
  fundamental_leaders?: FundamentalLeader[];
  rsi_divergences?: { bearish?: RSIDivergenceItem[]; bullish?: RSIDivergenceItem[] };
  td_signals?: TDSignalItem[];
  gap_leaders?: GapLeader[];
  constituent_symbols?: string[];
};

const METRIC_ORDER = [
  { key: 'perf_1d', label: '1D Change' },
  { key: 'perf_5d', label: '5D Change' },
  { key: 'perf_20d', label: '20D Change' },
  { key: 'atrx_sma_21', label: '(Price - 21DMA) / ATR' },
  { key: 'atrx_sma_50', label: '(Price - 50DMA) / ATR' },
  { key: 'atrx_sma_200', label: '(Price - 200DMA) / ATR' },
];

const fmtPct = (v: unknown): string => {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—';
  return `${v.toFixed(1)}%`;
};

const fmtValue = (value: unknown, metricKey: string) => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  if (metricKey.startsWith('perf_')) return `${value.toFixed(1)}%`;
  return `${value.toFixed(2)}x`;
};

const normalizeSymbol = (symbol: unknown): string => {
  if (typeof symbol !== 'string') return '';
  return symbol.trim().toUpperCase();
};

const repeatSymbolColor = (symbol: string): string => {
  // Use a broad hue space so repeated symbols are visually distinct.
  let hash = 0;
  for (let i = 0; i < symbol.length; i += 1) {
    hash = (hash * 31 + symbol.charCodeAt(i)) >>> 0;
  }
  const hue = (hash * 137) % 360;
  return `hsl(${hue} 72% 58%)`;
};

/* ===== Sub-components (StatCard, StageBar from shared) ===== */

const SetupCard: React.FC<{ title: string; items: SetupItem[]; showScore?: boolean; linkPreset?: string; showHeldBadge?: boolean }> = ({ title, items, showScore, linkPreset, showHeldBadge = true }) => (
  <Card className="min-w-[220px] flex-1 gap-0 py-3 shadow-xs ring-1 ring-foreground/10">
    <CardContent className="flex flex-col gap-2 px-3">
      <div className="mb-1 flex items-center justify-between">
        {linkPreset ? (
          <RouterLink to={`/market/tracked?preset=${linkPreset}`} className="text-sm font-semibold underline-offset-2 hover:underline">
            {title}
          </RouterLink>
        ) : (
          <span className="text-sm font-semibold">{title}</span>
        )}
        {items.length > 0 ? (
          <Badge variant="secondary" className="h-5 font-normal">
            {items.length}
          </Badge>
        ) : null}
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-muted-foreground">None found</p>
      ) : (
        <div className="max-h-[260px] overflow-y-auto pr-1">
          <div className="flex flex-col gap-1">
            {items.map((item, i) => (
              <div key={`setup-${item.symbol}-${i}`} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-1">
                  <SymbolLink symbol={item.symbol} showHeldBadge={showHeldBadge} />
                  <StageBadge stage={item.stage_label || '?'} />
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {showScore && item.momentum_score != null && (
                    <span className={heatTextClass(item.momentum_score)}>{item.momentum_score.toFixed(1)}</span>
                  )}
                  <span className={heatTextClass(item.perf_20d)}>{fmtPct(item.perf_20d)}</span>
                  <span className={heatTextClass(item.rs_mansfield_pct)}>RS {fmtPct(item.rs_mansfield_pct)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </CardContent>
  </Card>
);

const transitionBadgeClass = (palette: string) =>
  palette === 'green'
    ? 'border-transparent bg-[rgb(var(--status-success)/0.12)] text-[rgb(var(--status-success)/1)]'
    : 'border-transparent bg-destructive/10 text-destructive';

const TransitionList: React.FC<{ title: string; items: StageTransitionItem[]; colorPalette: string; showHeldBadge?: boolean }> = ({ title, items, colorPalette, showHeldBadge = true }) => {
  const symbolsParam = items.map((r) => r.symbol).join(',');
  const titleLink = symbolsParam ? `/market/tracked?symbols=${encodeURIComponent(symbolsParam)}` : undefined;
  return (
    <Card className="min-w-[220px] flex-1 gap-0 py-3 shadow-xs ring-1 ring-foreground/10">
      <CardContent className="flex flex-col gap-2 px-3">
        <div className="mb-1 flex items-center justify-between">
          {titleLink ? (
            <RouterLink to={titleLink} className="text-sm font-semibold underline-offset-2 hover:underline">
              {title}
            </RouterLink>
          ) : (
            <span className="text-sm font-semibold">{title}</span>
          )}
          <Badge variant="secondary" className={cn('font-normal', transitionBadgeClass(colorPalette))}>
            {items.length}
          </Badge>
        </div>
        <div className="max-h-[280px] overflow-y-auto pr-1">
          <div className="flex flex-col gap-1">
            {items.length ? items.map((r, i) => (
              <div key={`trans-${r.symbol}-${i}`} className="flex items-center justify-between text-xs">
                <SymbolLink symbol={r.symbol} showHeldBadge={showHeldBadge} />
                <div className="flex items-center gap-1">
                  <Badge variant="outline" className="h-5 px-1.5 font-normal">
                    {r.previous_stage_label || '—'} → {r.stage_label || '?'}
                  </Badge>
                  {r.current_stage_days != null && (
                    <span className="text-muted-foreground">{r.current_stage_days}d</span>
                  )}
                </div>
              </div>
            )) : <p className="text-xs text-muted-foreground">No recent entries.</p>}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

const RankMatrix: React.FC<{ title: string; data?: Record<string, Array<{ symbol: string; value: number }>> }> = ({ title, data }) => {
  const matrixRows = React.useMemo(() => {
    const maxLen = METRIC_ORDER.reduce(
      (acc, metric) => Math.max(acc, (data?.[metric.key] || []).length),
      0,
    );
    const count = Math.min(maxLen, 10);
    return Array.from({ length: count }, (_, idx) => idx);
  }, [data]);
  const repeatedSymbols = React.useMemo(() => {
    const counts = new Map<string, number>();
    METRIC_ORDER.forEach((metric) => {
      (data?.[metric.key] || []).forEach((item) => {
        const symbol = normalizeSymbol(item?.symbol);
        if (!symbol) return;
        counts.set(symbol, (counts.get(symbol) || 0) + 1);
      });
    });
    return new Set(
      Array.from(counts.entries())
        .filter(([, count]) => count > 1)
        .map(([symbol]) => symbol),
    );
  }, [data]);

  return (
    <Card className="gap-0 py-3 shadow-xs ring-1 ring-foreground/10">
      <CardContent className="flex flex-col gap-2 px-3">
        <p className="text-sm font-semibold">{title}</p>
        <TableShell>
          <thead className="sticky top-0 z-[1] border-b border-border bg-muted/80">
            <tr>
              {METRIC_ORDER.map((m) => (
                <th key={m.key} className="whitespace-nowrap px-2 py-2 font-medium">
                  {m.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrixRows.map((idx) => (
              <tr key={idx} className="border-b border-border/60 last:border-0">
                {METRIC_ORDER.map((m) => {
                  const item = (data?.[m.key] || [])[idx];
                  const symbol = normalizeSymbol(item?.symbol);
                  const hasRepeat = !!symbol && repeatedSymbols.has(symbol);
                  if (!item) {
                    return <td key={`${m.key}-${idx}`} className="px-2 py-1.5">—</td>;
                  }
                  return (
                    <td key={`${m.key}-${idx}`} className="px-2 py-1.5">
                      <span
                        className={cn(hasRepeat && 'font-bold')}
                        style={hasRepeat ? { color: repeatSymbolColor(symbol) } : undefined}
                        data-testid={
                          hasRepeat
                            ? `repeat-text-${title.replace(/\s+/g, '-').toLowerCase()}`
                            : undefined
                        }
                      >
                        <SymbolLink symbol={item.symbol} />{' '}
                        <span className="text-xs text-muted-foreground">({fmtValue(item.value, m.key)})</span>
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </TableShell>
      </CardContent>
    </Card>
  );
};

const RangeHistogram: React.FC<{ bins: RangeHistogramBin[] }> = ({ bins }) => {
  const cc = useChartColors();
  const data = bins.map((b) => {
    const isLow = b.bin.startsWith('0-') || b.bin.startsWith('10-');
    const isHigh = b.bin.startsWith('80-') || b.bin.startsWith('90-');
    return {
      name: b.bin.replace('%', ''),
      count: b.count,
      fill: isLow ? cc.danger : isHigh ? cc.success : cc.neutral,
    };
  });
  return (
    <Card className="gap-0 py-4 shadow-xs ring-1 ring-foreground/10">
      <CardContent className="flex flex-col gap-2 px-4">
      <p className="text-sm font-semibold">52-Week Range Distribution</p>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
          <XAxis
            dataKey="name"
            tick={{ fontSize: 9, fill: cc.muted }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `${v}%`}
          />
          <YAxis hide />
          <RTooltip
            contentStyle={{ fontSize: 12, borderRadius: 8, border: `1px solid ${cc.border}` }}
            formatter={(value) => [`${value} symbols`, 'Count']}
          />
          <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={36}>
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="mt-1 text-center text-xs text-muted-foreground">Left-skew = capitulation · Right-skew = euphoria</p>
      </CardContent>
    </Card>
  );
};

const BreadthChart: React.FC<{ series: BreadthPoint[] }> = ({ series }) => {
  const cc = useChartColors();
  if (!series.length) return null;
  const fmtDate = (raw: string) => {
    const d = new Date(raw);
    if (isNaN(d.getTime())) return raw.slice(5, 10);
    return `${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`;
  };
  const data = series.map((pt) => ({
    date: fmtDate(pt.date),
    sma50: pt.above_sma50_pct,
    sma200: pt.above_sma200_pct,
  }));

  const latest50 = data.length ? data[data.length - 1].sma50 : null;
  const latest200 = data.length ? data[data.length - 1].sma200 : null;

  return (
    <Card className="gap-0 py-4 shadow-xs ring-1 ring-foreground/10">
      <CardContent className="flex flex-col gap-2 px-4">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-semibold">Breadth Over Time</p>
        <div className="flex flex-wrap gap-3">
          {latest50 != null && (
            <div className="flex items-center gap-1">
              <div className="h-0.5 w-2 rounded-full" style={{ backgroundColor: cc.area1 }} />
              <span className="text-[10px] text-muted-foreground">
                &gt;50DMA <span className="font-semibold text-foreground">{latest50.toFixed(0)}%</span>
              </span>
            </div>
          )}
          {latest200 != null && (
            <div className="flex items-center gap-1">
              <div className="h-0.5 w-2 rounded-full" style={{ backgroundColor: cc.area2 }} />
              <span className="text-[10px] text-muted-foreground">
                &gt;200DMA <span className="font-semibold text-foreground">{latest200.toFixed(0)}%</span>
              </span>
            </div>
          )}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <ComposedChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="grad50" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={cc.area1} stopOpacity={0.25} />
              <stop offset="95%" stopColor={cc.area1} stopOpacity={0.02} />
            </linearGradient>
            <linearGradient id="grad200" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={cc.area2} stopOpacity={0.2} />
              <stop offset="95%" stopColor={cc.area2} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="date"
            tick={{ fontSize: 9, fill: cc.muted }}
            tickLine={false}
            axisLine={false}
            interval={Math.max(0, Math.floor(data.length / 5))}
          />
          <YAxis hide domain={[0, 100]} />
          <ReferenceLine y={50} stroke={cc.refLine} strokeDasharray="4 3" label={{ value: '50%', position: 'insideTopLeft', fontSize: 9, fill: cc.muted }} />
          <RTooltip
            contentStyle={{ fontSize: 12, borderRadius: 8, border: `1px solid ${cc.border}` }}
            formatter={(value, name) => [`${Number(value).toFixed(1)}%`, String(name) === 'sma50' ? '% > 50DMA' : '% > 200DMA']}
          />
          <Area type="monotone" dataKey="sma200" fill="url(#grad200)" stroke={cc.area2} strokeWidth={1.5} />
          <Area type="monotone" dataKey="sma50" fill="url(#grad50)" stroke={cc.area1} strokeWidth={2} />
        </ComposedChart>
      </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};

const RRGCustomTooltip: React.FC<any> = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const quad = d.rs_ratio >= 0
    ? d.rs_momentum >= 0 ? 'Leading' : 'Weakening'
    : d.rs_momentum >= 0 ? 'Improving' : 'Lagging';
  return (
    <div className="min-w-[160px] rounded-lg border border-border bg-popover p-3 shadow-md">
      <div className="mb-1 flex items-center gap-2">
        <div className="size-2.5 shrink-0 rounded-full" style={{ backgroundColor: SECTOR_PALETTE[d._idx % SECTOR_PALETTE.length] }} />
        <span className="text-sm font-bold">{d.name}</span>
      </div>
      <p className="text-xs text-muted-foreground">{d.symbol}</p>
      <div className="mt-2 flex flex-col gap-1">
        <div className="flex justify-between text-xs">
          <span className="text-muted-foreground">RS-Ratio</span>
          <span className="font-medium">{d.rs_ratio.toFixed(2)}</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-muted-foreground">RS-Momentum</span>
          <span className="font-medium">{d.rs_momentum.toFixed(2)}</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-muted-foreground">Quadrant</span>
          <span className="font-medium">{quad}</span>
        </div>
      </div>
    </div>
  );
};

const RRGChart: React.FC<{ sectors: RRGSector[] }> = ({ sectors }) => {
  const cc = useChartColors();
  if (!sectors.length) return null;
  const data = sectors.map((s, i) => ({
    ...s,
    z: 200,
    _idx: i,
  }));

  const maxAbs = Math.max(
    ...sectors.map((s) => Math.abs(s.rs_ratio)),
    ...sectors.map((s) => Math.abs(s.rs_momentum)),
    1,
  );
  const pad = Math.ceil(maxAbs * 1.15) || 5;

  return (
    <Card className="flex h-full min-h-[520px] flex-col gap-0 py-4 shadow-xs ring-1 ring-foreground/10">
      <CardContent className="flex flex-1 flex-col gap-2 px-4">
      <p className="text-sm font-semibold">Relative Rotation Graph (Sectors)</p>
      <p className="text-xs text-muted-foreground">Hover each dot to see sector details</p>
      <div className="min-h-[380px] w-full flex-1">
        <ResponsiveContainer width="100%" height={400}>
          <ScatterChart>
          <CartesianGrid strokeDasharray="3 3" stroke={cc.grid} />
          <XAxis
            type="number"
            dataKey="rs_ratio"
            name="RS-Ratio"
            domain={[-pad, pad]}
            hide
          />
          <YAxis
            type="number"
            dataKey="rs_momentum"
            name="RS-Momentum"
            domain={[-pad, pad]}
            hide
          />
          <ZAxis type="number" dataKey="z" range={[160, 160]} />
          <ReferenceArea x1={0} x2={pad} y1={0} y2={pad} fill={cc.success} fillOpacity={0.05} label={{ value: 'Leading ↗', position: 'insideTopRight', fontSize: 11, fill: cc.success, fontWeight: 600 }} />
          <ReferenceArea x1={-pad} x2={0} y1={0} y2={pad} fill={cc.area2} fillOpacity={0.05} label={{ value: '↖ Improving', position: 'insideTopLeft', fontSize: 11, fill: cc.neutral, fontWeight: 600 }} />
          <ReferenceArea x1={-pad} x2={0} y1={-pad} y2={0} fill={cc.danger} fillOpacity={0.05} label={{ value: '↙ Lagging', position: 'insideBottomLeft', fontSize: 11, fill: cc.danger, fontWeight: 600 }} />
          <ReferenceArea x1={0} x2={pad} y1={-pad} y2={0} fill={cc.warning} fillOpacity={0.05} label={{ value: 'Weakening ↘', position: 'insideBottomRight', fontSize: 11, fill: cc.warning, fontWeight: 600 }} />
          <ReferenceLine x={0} stroke={cc.refLine} strokeWidth={1.5} />
          <ReferenceLine y={0} stroke={cc.refLine} strokeWidth={1.5} />
          <RTooltip content={<RRGCustomTooltip />} cursor={false} />
          <Scatter data={data}>
            {data.map((entry, i) => (
              <Cell key={i} fill={SECTOR_PALETTE[i % SECTOR_PALETTE.length]} stroke="white" strokeWidth={1.5} />
            ))}
          </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 grid shrink-0 grid-cols-[repeat(auto-fill,minmax(130px,1fr))] gap-0.5 px-1">
        {data.map((s, i) => (
          <div key={`rrg-${s.symbol}-${i}`} className="flex min-w-0 items-center gap-1">
            <div className="size-2 shrink-0 rounded-full" style={{ backgroundColor: SECTOR_PALETTE[i % SECTOR_PALETTE.length] }} />
            <span className="truncate text-[10px] text-muted-foreground">{s.name}</span>
          </div>
        ))}
      </div>
      </CardContent>
    </Card>
  );
};

/* ===== Volatility Regime ===== */

const REGIME_COLORS: Record<string, { className: string; label: string }> = {
  calm:     { className: 'border-transparent bg-[rgb(var(--status-success)/0.12)] text-[rgb(var(--status-success)/1)]', label: 'Calm' },
  elevated: { className: 'border-transparent bg-amber-500/15 text-amber-800 dark:text-amber-200', label: 'Elevated' },
  fear:     { className: 'border-transparent bg-orange-500/15 text-orange-800 dark:text-orange-200', label: 'Fear' },
  extreme:  { className: 'border-transparent bg-destructive/10 text-destructive', label: 'Extreme' },
  unknown:  { className: 'bg-secondary text-secondary-foreground', label: 'Unknown' },
};

const GaugeBar: React.FC<{
  label: string;
  value: number | null;
  min: number;
  max: number;
  zones: { end: number; color: string; label: string }[];
}> = ({ label, value, min, max, zones }) => {
  const range = max - min;
  const pct = value != null ? Math.max(0, Math.min(100, ((value - min) / range) * 100)) : null;

  return (
    <div>
      <div className="mb-px flex justify-between">
        <span className="text-xs font-medium">{label}</span>
        <span className="text-xs text-muted-foreground">{value != null ? value.toFixed(2) : '—'}</span>
      </div>
      <div className="relative flex h-3.5 overflow-hidden rounded-md">
        {zones.map((zone, i) => {
          const start = i === 0 ? min : zones[i - 1].end;
          const width = ((zone.end - start) / range) * 100;
          return (
            <div
              key={i}
              className="relative h-full opacity-25"
              style={{ width: `${width}%`, backgroundColor: zone.color }}
            />
          );
        })}
        {pct != null && (
          <div
            className="absolute top-0 bottom-0 z-[1] w-0.5 rounded-sm bg-foreground"
            style={{ left: `${pct}%`, transform: 'translateX(-50%)' }}
          />
        )}
      </div>
      <div className="mt-px flex justify-between">
        {zones.map((zone, i) => (
          <span key={i} className="text-[9px] text-muted-foreground">{zone.label}</span>
        ))}
      </div>
    </div>
  );
};

const VolatilityRegime: React.FC<{ data: VolatilityDashboardData | null }> = ({ data }) => {
  if (!data || data.regime === 'unknown') return null;
  const rc = REGIME_COLORS[data.regime] || REGIME_COLORS.unknown;

  return (
    <Card className="gap-0 py-3 shadow-xs ring-1 ring-foreground/10">
      <CardContent className="flex flex-col gap-2 px-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-semibold">Volatility Regime</span>
        <div className="flex items-center gap-2">
          {data.vix != null && <span className="text-xs text-muted-foreground">VIX {data.vix.toFixed(1)}</span>}
          <Badge variant="secondary" className={cn('h-5 font-normal', rc.className)}>{rc.label}</Badge>
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <GaugeBar
          label="Term Structure (VIX3M / VIX)"
          value={data.term_structure_ratio}
          min={0.8}
          max={1.4}
          zones={[
            { end: 1.0,  color: 'red',    label: 'Backwardation' },
            { end: 1.15, color: 'green',  label: 'Normal' },
            { end: 1.4,  color: 'orange', label: 'Overbought' },
          ]}
        />
        <GaugeBar
          label="Vol-of-Vol (VVIX / VIX)"
          value={data.vol_of_vol_ratio}
          min={2.0}
          max={8.0}
          zones={[
            { end: 3.5, color: 'green',  label: 'Buy Protection' },
            { end: 6.0, color: 'gray',   label: 'Neutral' },
            { end: 8.0, color: 'red',    label: 'Sell Protection' },
          ]}
        />
      </div>
      {data.signal ? (
        <p className="mt-2 text-xs text-muted-foreground italic">{data.signal}</p>
      ) : null}
      </CardContent>
    </Card>
  );
};

/* ===== Section visibility & collapse ===== */

type UniverseFilter = 'all' | 'etf' | 'holdings';

const SECTION_VIS = {
  all:      { pulse: true,  actionQueue: true,  sectorRotation: true,  scatter: true,  setups: true,  transitions: true,  ranked: true,  proximity: true,  insights: true,  signals: true,  earnings: true  },
  etf:      { pulse: true,  actionQueue: false, sectorRotation: true,  scatter: true,  setups: false, transitions: false, ranked: false, proximity: true,  insights: true,  signals: false, earnings: false },
  holdings: { pulse: false, actionQueue: true,  sectorRotation: false, scatter: false, setups: true,  transitions: true,  ranked: false, proximity: true,  insights: false, signals: true,  earnings: true  },
} as const;

const MODE_DESCRIPTIONS: Record<UniverseFilter, string> = {
  all: 'S&P 500, NASDAQ 100, DOW 30, and Russell 2000 -- broad market scanning for entries and exits',
  etf: 'Sector and thematic ETFs -- rotation and relative strength analysis',
  holdings: 'Your portfolio positions -- signals, setups, and earnings alerts',
};

const COLLAPSE_KEY = 'axiomfolio:dashboard:collapsed';

function useSectionCollapse() {
  const [collapsed, setCollapsed] = React.useState<Set<string>>(() => {
    try {
      const stored = localStorage.getItem(COLLAPSE_KEY);
      return stored ? new Set(JSON.parse(stored) as string[]) : new Set<string>();
    } catch { return new Set<string>(); }
  });

  const toggle = React.useCallback((key: string) => {
    setCollapsed(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      try { localStorage.setItem(COLLAPSE_KEY, JSON.stringify([...next])); } catch {}
      return next;
    });
  }, []);

  return { collapsed, toggle };
}

const SectionHeading: React.FC<{
  title: string;
  sectionKey: string;
  isCollapsed: boolean;
  onToggle: () => void;
  count?: number;
}> = ({ title, sectionKey, isCollapsed, onToggle, count }) => (
  <div
    role="button"
    tabIndex={0}
    className={cn(
      'flex cursor-pointer select-none items-center gap-2 hover:opacity-80 focus-visible:rounded-md focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
      !isCollapsed && 'mb-2',
    )}
    onClick={onToggle}
    onKeyDown={(e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onToggle();
      }
    }}
    aria-expanded={!isCollapsed}
    aria-controls={`section-${sectionKey}`}
  >
    {isCollapsed ? <ChevronRight className="size-3.5 shrink-0" aria-hidden /> : <ChevronDown className="size-3.5 shrink-0" aria-hidden />}
    <span className="text-sm font-semibold tracking-tight">{title}</span>
    {count != null && count > 0 ? (
      <Badge variant="secondary" className="h-5 font-normal">{count}</Badge>
    ) : null}
  </div>
);

const EmptyState: React.FC<{ mode: UniverseFilter; noun?: string }> = ({ mode, noun = 'items' }) => (
  <p className="py-4 text-center text-sm text-muted-foreground">
    No {noun} for {MODE_DESCRIPTIONS[mode].toLowerCase()}
  </p>
);

/* ===== Main Component ===== */

const UNIVERSE_FILTER_KEY = 'axiomfolio:market-dashboard:universe-filter';

const MarketDashboard: React.FC = () => {
  const { timezone } = useUserPreferences();
  const {
    data: payload,
    isLoading: loading,
    error,
    refetch,
  } = useQuery<DashboardPayload>({
    queryKey: ['market-dashboard'],
    queryFn: async () => (await marketDataApi.getDashboard()) as DashboardPayload,
    staleTime: 60_000,
    refetchInterval: 5 * 60_000,
  });
  const [chartSymbol, setChartSymbol] = React.useState<string | null>(null);
  const openChart = React.useCallback((sym: string) => setChartSymbol(sym), []);
  const portfolioQuery = usePortfolioSymbols();
  const portfolioSymbols = portfolioQuery.data ?? {};
  const { collapsed, toggle } = useSectionCollapse();
  const { health: healthData } = useAdminHealth();

  const [activeView, setActiveView] = React.useState<DashboardView>(() => {
    try {
      const stored = localStorage.getItem(VIEW_KEY) as DashboardView;
      if (stored && VIEW_TABS.some(t => t.key === stored)) return stored;
    } catch {}
    return 'overview';
  });
  const handleViewChange = React.useCallback((view: DashboardView) => {
    setActiveView(view);
    try { localStorage.setItem(VIEW_KEY, view); } catch {}
  }, []);

  const [universeFilter, setUniverseFilter] = React.useState<UniverseFilter>(() => {
    try {
      const stored = localStorage.getItem(UNIVERSE_FILTER_KEY);
      if (stored === 'etf' || stored === 'holdings') return stored;
    } catch {}
    return 'all';
  });

  const handleFilterChange = React.useCallback((f: UniverseFilter) => {
    setUniverseFilter(f);
    try { localStorage.setItem(UNIVERSE_FILTER_KEY, f); } catch {}
  }, []);

  const vis = SECTION_VIS[universeFilter];
  const showHeld = universeFilter !== 'holdings';

  const constituentSet = React.useMemo(
    () => new Set((payload?.constituent_symbols ?? []).map((s: string) => s.toUpperCase())),
    [payload?.constituent_symbols],
  );

  const symbolFilter = React.useCallback((symbol: string): boolean => {
    const sym = symbol?.toUpperCase?.() || '';
    if (universeFilter === 'all') return constituentSet.size === 0 || constituentSet.has(sym);
    if (universeFilter === 'etf') return ETF_SYMBOL_SET.has(sym);
    if (universeFilter === 'holdings') return sym in portfolioSymbols;
    return true;
  }, [universeFilter, portfolioSymbols, constituentSet]);

  const volatilityQuery = useVolatility();
  const volData = volatilityQuery.data ?? null;
  const { data: aggregates } = useSnapshotAggregates();

  /* --- ZONE 1b: effectiveStats (must be before early returns) --- */
  const effectiveStats = React.useMemo(() => {
    const regime = payload?.regime || {};
    const sc = payload?.snapshot_count || aggregates?.total || 0;
    const a50 = regime.above_sma50_count || 0;
    const a200 = regime.above_sma200_count || 0;
    const up = regime.up_1d_count || 0;
    const dn = regime.down_1d_count || 0;
    const flat = (regime.flat_1d_count as number) || 0;
    const serverStageCounts = regime.stage_counts_normalized || {};
    const aggStageCounts: Record<string, number> = {};
    (aggregates?.stage_distribution ?? []).forEach((d) => {
      if (d.stage) aggStageCounts[d.stage] = d.count;
    });
    return {
      count: sc,
      above50: a50,
      above200: a200,
      upCount: up,
      downCount: dn,
      flatCount: flat,
      stageCounts: Object.keys(serverStageCounts).length > 0 ? serverStageCounts : aggStageCounts,
    };
  }, [payload, aggregates]);

  /* --- ZONE 1c: filteredSections (consolidate all sf() calls) --- */
  const filteredSections = React.useMemo(() => {
    function sf<T extends { symbol?: string }>(arr: T[]): T[] {
      return arr.filter((r) => symbolFilter(r.symbol || ''));
    }
    const sfMatrix = (m: Record<string, any[]> | undefined | null) =>
      m ? Object.fromEntries(Object.entries(m).map(([k, arr]) => [k, sf(arr)])) : undefined;

    return {
      sectorRows: sf(payload?.sector_etf_table || []),
      sectorMomentum: payload?.sector_momentum || [],
      breakoutCandidates: sf(payload?.setups?.breakout_candidates || []),
      pullbackCandidates: sf(payload?.setups?.pullback_candidates || []),
      rsLeaders: sf(payload?.setups?.rs_leaders || []),
      leaders: sf(payload?.leaders || []),
      enteringStage2a: sf(payload?.entering_stage_2a || []),
      entering34: sf([...(payload?.entering_stage_3 || []), ...(payload?.entering_stage_4 || [])]),
      entryRows: sf(payload?.entry_proximity_top || []),
      exitRows: sf(payload?.exit_proximity_top || []),
      actionQueue: sf(payload?.action_queue || []),
      top10Matrix: sfMatrix(payload?.top10_matrix),
      bottom10Matrix: sfMatrix(payload?.bottom10_matrix),
      rrgSectors: sf(payload?.rrg_sectors || []),
      rsiBearish: sf(payload?.rsi_divergences?.bearish || []),
      rsiBullish: sf(payload?.rsi_divergences?.bullish || []),
      tdSignals: sf(payload?.td_signals || []),
      gapLeaders: sf(payload?.gap_leaders || []),
      upcomingEarnings: sf(payload?.upcoming_earnings || []),
      fundamentalLeaders: sf(payload?.fundamental_leaders || []),
    };
  }, [payload, symbolFilter]);

  /* --- ZONE 2: Early returns (all hooks are above this line) --- */

  if (loading) {
    return (
      <Page>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" aria-hidden />
          Loading market dashboard…
        </div>
      </Page>
    );
  }

  if (error) {
    return (
      <Page>
        <h1 className="mb-2 font-heading text-2xl font-semibold tracking-tight">Market Dashboard</h1>
        <p className="text-sm text-destructive">{error?.message || 'Failed to load market dashboard'}</p>
      </Page>
    );
  }

  /* --- ZONE 3: Derived plain values + JSX --- */

  const {
    sectorRows, sectorMomentum, breakoutCandidates, pullbackCandidates,
    rsLeaders, leaders, enteringStage2a, entering34, entryRows, exitRows,
    actionQueue, top10Matrix, bottom10Matrix, rrgSectors, rsiBearish,
    rsiBullish, tdSignals, gapLeaders, upcomingEarnings, fundamentalLeaders,
  } = filteredSections;

  const trackedCount = payload?.tracked_count || 0;

  const { count: snapshotCount, above50, above200, upCount, downCount, stageCounts } = effectiveStats;
  const pctAbove50 = snapshotCount > 0 ? ((above50 / snapshotCount) * 100).toFixed(0) : '0';
  const pctAbove200 = snapshotCount > 0 ? ((above200 / snapshotCount) * 100).toFixed(0) : '0';
  const advDecRatio = downCount > 0 ? (upCount / downCount).toFixed(2) : upCount > 0 ? '∞' : '0';
  const advDecColor = (() => {
    const r = downCount > 0 ? upCount / downCount : upCount > 0 ? 2 : 1;
    if (r > 1.2) return 'green.500';
    if (r > 1) return 'green.400';
    if (r < 0.8) return 'red.500';
    if (r < 1) return 'red.400';
    return undefined;
  })();

  const snapshotAge = payload?.latest_snapshot_at
    ? Math.round((Date.now() - new Date(payload.latest_snapshot_at).getTime()) / 60000)
    : null;

  const filterLabels: Record<UniverseFilter, string> = {
    all: `All (${constituentSet.size || trackedCount})`,
    etf: `ETFs (${ETF_SYMBOL_SET.size})`,
    holdings: `Holdings (${Object.keys(portfolioSymbols).length})`,
  };

  return (
    <PortfolioSymbolsContext.Provider value={portfolioSymbols}>
    <ChartContext.Provider value={openChart}>
    <Page>
      <div className="flex flex-col gap-4">
        <div>
          <div className="mb-1 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end sm:justify-between">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-baseline sm:gap-3">
              <h1 className="font-heading text-2xl font-semibold tracking-tight text-foreground md:text-3xl">Market Dashboard</h1>
              <div className="flex flex-wrap gap-1">
                {VIEW_TABS.map((tab) => {
                  const Icon = tab.icon;
                  const isActive = activeView === tab.key;
                  return (
                    <Button
                      key={tab.key}
                      type="button"
                      size="xs"
                      variant={isActive ? 'default' : 'ghost'}
                      className={cn(
                        'gap-1',
                        isActive && 'bg-primary text-primary-foreground hover:bg-primary/90',
                      )}
                      onClick={() => handleViewChange(tab.key)}
                    >
                      <Icon className="size-3" aria-hidden />
                      {tab.label}
                    </Button>
                  );
                })}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {activeView === 'overview' && (
                <div className="flex flex-wrap gap-1">
                  {(['all', 'etf', 'holdings'] as UniverseFilter[]).map((f) => (
                    <Button
                      key={f}
                      type="button"
                      size="xs"
                      variant={universeFilter === f ? 'default' : 'outline'}
                      className={cn(
                        universeFilter === f && f !== 'holdings' && 'bg-secondary',
                        universeFilter === f && f === 'holdings' && 'bg-primary text-primary-foreground',
                      )}
                      onClick={() => handleFilterChange(f)}
                    >
                      {filterLabels[f]}
                    </Button>
                  ))}
                </div>
              )}
              <div className="flex items-center gap-1">
                <span
                  className={cn(
                    'text-xs',
                    snapshotAge != null && snapshotAge > 30
                      ? 'text-[rgb(var(--status-warning)/1)]'
                      : 'text-muted-foreground',
                  )}
                >
                  {snapshotAge != null ? `${snapshotAge}m ago` : ''}
                </span>
                {healthData?.dimensions?.data_accuracy && healthData.dimensions.data_accuracy.mismatch_count > 0 && (
                  <Badge variant="outline" className="h-5 text-[10px] bg-amber-500/15 text-amber-800 dark:text-amber-200">
                    {healthData.dimensions.data_accuracy.mismatch_count} data warnings
                  </Badge>
                )}
                <Button
                  type="button"
                  size="icon-xs"
                  variant="ghost"
                  aria-label="Refresh dashboard"
                  onClick={() => { void refetch(); }}
                >
                  <RefreshCw className="size-3.5" />
                </Button>
              </div>
            </div>
          </div>
          {activeView === 'overview' && (
            <p className="text-xs text-muted-foreground">{MODE_DESCRIPTIONS[universeFilter]}</p>
          )}
        </div>

        {/* Non-overview views */}
        {activeView !== 'overview' && (
          <ErrorBoundary
            fallback={(
              <div className="p-4 text-sm text-muted-foreground">
                Something went wrong loading this view. Try refreshing the page.
              </div>
            )}
            onError={(error, info) => {
              console.error('ErrorBoundary [market-dashboard-view]:', error, info);
            }}
          >
            <React.Suspense fallback={(
              <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" aria-hidden />
                Loading view...
              </div>
            )}>
              {activeView === 'top-down' && (
                <ErrorBoundary
                  fallback={(
                    <div className="p-4 text-sm text-muted-foreground">
                      Something went wrong in this section. Try refreshing the page.
                    </div>
                  )}
                  onError={(error, info) => {
                    console.error('ErrorBoundary [market-dashboard-top-down]:', error, info);
                  }}
                >
                  <TopDownView snapshots={[]} dashboardPayload={payload} />
                </ErrorBoundary>
              )}
              {activeView === 'bottom-up' && (
                <ErrorBoundary
                  fallback={(
                    <div className="p-4 text-sm text-muted-foreground">
                      Something went wrong in this section. Try refreshing the page.
                    </div>
                  )}
                  onError={(error, info) => {
                    console.error('ErrorBoundary [market-dashboard-bottom-up]:', error, info);
                  }}
                >
                  <BottomUpView />
                </ErrorBoundary>
              )}
              {activeView === 'sectors' && (
                <ErrorBoundary
                  fallback={(
                    <div className="p-4 text-sm text-muted-foreground">
                      Something went wrong in this section. Try refreshing the page.
                    </div>
                  )}
                  onError={(error, info) => {
                    console.error('ErrorBoundary [market-dashboard-sectors]:', error, info);
                  }}
                >
                  <SectorView snapshots={[]} dashboardPayload={payload} />
                </ErrorBoundary>
              )}
              {activeView === 'heatmap' && (
                <ErrorBoundary
                  fallback={(
                    <div className="p-4 text-sm text-muted-foreground">
                      Something went wrong in this section. Try refreshing the page.
                    </div>
                  )}
                  onError={(error, info) => {
                    console.error('ErrorBoundary [market-dashboard-heatmap]:', error, info);
                  }}
                >
                  <HeatmapView snapshots={[]} />
                </ErrorBoundary>
              )}
            </React.Suspense>
          </ErrorBoundary>
        )}

        {/* Overview mode — existing content */}
        {activeView === 'overview' && (
        <>
        {/* Regime Banner — always visible in overview */}
        <RegimeBanner />

        {/* Quad Status Bar */}
        <QuadStatusBar />

        {/* Section 1: Market Pulse */}
        {vis.pulse && (
        <div>
          <SectionHeading title="Market Pulse" sectionKey="pulse" isCollapsed={collapsed.has('pulse')} onToggle={() => toggle('pulse')} />
          <Collapsible.Root open={!collapsed.has('pulse')}>
            <Collapsible.Content>
              <div className="mb-3 flex flex-wrap gap-2">
                <StatCard label="% Above 50DMA" value={`${pctAbove50}%`} sub={`${above50} / ${snapshotCount}`} />
                <StatCard label="% Above 200DMA" value={`${pctAbove200}%`} sub={`${above200} / ${snapshotCount}`} />
                <StatCard label="Advance / Decline" value={advDecRatio} sub={`${upCount} up · ${downCount} down`} color={advDecColor} />
              </div>
              <StageBar counts={stageCounts} total={snapshotCount} />
              <div className="mt-3">
                <VolatilityRegime data={volData} />
              </div>
            </Collapsible.Content>
          </Collapsible.Root>
        </div>
        )}

        {/* Action Queue — organized by Weinstein Stage */}
        {vis.actionQueue && (() => {
          if (actionQueue.length === 0) return (
            <div>
              <SectionHeading title="Action Queue" sectionKey="actionQueue" isCollapsed={collapsed.has('actionQueue')} onToggle={() => toggle('actionQueue')} count={0} />
              <Collapsible.Root open={!collapsed.has('actionQueue')}><Collapsible.Content><EmptyState mode={universeFilter} noun="action items" /></Collapsible.Content></Collapsible.Root>
            </div>
          );
          const stageGroups: Record<string, typeof actionQueue> = { '1': [], '2': [], '3': [], '4': [] };
          for (const item of actionQueue) {
            const s = (item.stage_label || '').charAt(0);
            if (s in stageGroups) stageGroups[s].push(item);
            else stageGroups['1'].push(item);
          }
          const stageConfig = [
            { key: '1', label: 'Stage 1 — Base', palette: 'gray' as const },
            { key: '2', label: 'Stage 2 — Uptrend', palette: 'green' as const },
            { key: '3', label: 'Stage 3 — Distribution', palette: 'yellow' as const },
            { key: '4', label: 'Stage 4 — Downtrend', palette: 'red' as const },
          ];
          const stageTitleClass = (p: typeof stageConfig[number]['palette']) =>
            p === 'gray'
              ? 'text-muted-foreground'
              : p === 'green'
                ? 'text-[rgb(var(--status-success)/1)]'
                : p === 'yellow'
                  ? 'text-amber-600 dark:text-amber-400'
                  : 'text-destructive';
          const stageBadgeClass = (p: typeof stageConfig[number]['palette']) =>
            p === 'gray'
              ? 'bg-secondary text-secondary-foreground'
              : p === 'green'
                ? 'border-transparent bg-[rgb(var(--status-success)/0.12)] text-[rgb(var(--status-success)/1)]'
                : p === 'yellow'
                  ? 'border-transparent bg-amber-500/15 text-amber-800 dark:text-amber-200'
                  : 'border-transparent bg-destructive/10 text-destructive';
          return (
            <div>
              <SectionHeading title="Action Queue" sectionKey="actionQueue" isCollapsed={collapsed.has('actionQueue')} onToggle={() => toggle('actionQueue')} count={actionQueue.length} />
              <Collapsible.Root open={!collapsed.has('actionQueue')}>
                <Collapsible.Content>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                {stageConfig.map(({ key, label, palette }) => (
                  <Card key={key} className="gap-0 overflow-hidden py-0 shadow-xs ring-1 ring-foreground/10">
                    <div className="border-b border-border px-3 py-1.5">
                      <div className="flex items-center justify-between">
                        <span className={cn('text-xs font-semibold', stageTitleClass(palette))}>{label}</span>
                        <Badge variant="secondary" className={cn('h-5 px-1.5 text-[10px] font-normal', stageBadgeClass(palette))}>
                          {stageGroups[key].length}
                        </Badge>
                      </div>
                    </div>
                    <CardContent className="max-h-[260px] overflow-y-auto px-3 py-2">
                      {stageGroups[key].length === 0 ? (
                        <p className="text-xs text-muted-foreground">No signals</p>
                      ) : (
                        stageGroups[key].map((item, idx) => {
                          const reasons: string[] = [];
                          if (item.previous_stage_label && item.previous_stage_label !== item.stage_label) {
                            reasons.push(`${item.previous_stage_label} → ${item.stage_label}`);
                          }
                          if (typeof item.perf_1d === 'number' && Math.abs(item.perf_1d) >= 3) {
                            reasons.push(`1D ${item.perf_1d > 0 ? '+' : ''}${item.perf_1d.toFixed(1)}%`);
                          }
                          if (typeof item.rs_mansfield_pct === 'number' && Math.abs(item.rs_mansfield_pct) >= 6) {
                            reasons.push(`RS ${item.rs_mansfield_pct > 0 ? '+' : ''}${item.rs_mansfield_pct.toFixed(1)}`);
                          }
                          return (
                            <div key={`aq-${item.symbol}-${idx}`} className="flex items-center justify-between border-b border-border py-0.5 text-xs last:border-0">
                              <SymbolLink symbol={item.symbol} showHeldBadge={showHeld} />
                              <div className="flex shrink-0 flex-wrap items-center justify-end gap-1">
                                {reasons.map((r, i) => (
                                  <span key={i} className="text-muted-foreground">{r}</span>
                                ))}
                              </div>
                            </div>
                          );
                        })
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
                </Collapsible.Content>
              </Collapsible.Root>
            </div>
          );
        })()}

        {/* Section 2: Sector Rotation */}
        {vis.sectorRotation && (
        <div>
          <SectionHeading title="Sector Rotation" sectionKey="sectorRotation" isCollapsed={collapsed.has('sectorRotation')} onToggle={() => toggle('sectorRotation')} />
          <Collapsible.Root open={!collapsed.has('sectorRotation')}>
            <Collapsible.Content>
          <div className="grid grid-cols-1 gap-3 xl:grid-cols-[1.6fr_0.4fr]">
            <Card className="gap-0 py-3 shadow-xs ring-1 ring-foreground/10">
              <CardContent className="px-3">
                <TableShell>
                  <thead className="border-b border-border bg-muted/50">
                    <tr>
                      <th className="px-2 py-2 font-medium">Sector</th>
                      <th className="px-2 py-2 font-medium">Stage</th>
                      <th className="px-2 py-2 font-medium">Days</th>
                      <th className="px-2 py-2 font-medium">1D%</th>
                      <th className="px-2 py-2 font-medium">5D%</th>
                      <th className="px-2 py-2 font-medium">20D%</th>
                      <th className="px-2 py-2 font-medium">RS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sectorRows.map((r, i) => (
                      <tr key={`sector-${r.symbol}-${i}`} className="border-b border-border/60">
                        <td className="px-2 py-1.5">{r.sector_name || r.symbol}</td>
                        <td className="px-2 py-1.5">
                          {r.stage_label ? <StageBadge stage={r.stage_label} /> : '—'}
                        </td>
                        <td className="px-2 py-1.5">{r.days_in_stage ?? '—'}</td>
                        <td className={cn('px-2 py-1.5', heatTextClass(r.change_1d))}>{fmtPct(r.change_1d)}</td>
                        <td className={cn('px-2 py-1.5', heatTextClass(r.change_5d))}>{fmtPct(r.change_5d)}</td>
                        <td className={cn('px-2 py-1.5', heatTextClass(r.change_20d))}>{fmtPct(r.change_20d)}</td>
                        <td className={cn('px-2 py-1.5', heatTextClass(r.rs_mansfield_pct))}>{fmtPct(r.rs_mansfield_pct)}</td>
                      </tr>
                    ))}
                  </tbody>
                </TableShell>
              </CardContent>
            </Card>

            <Card className="gap-0 py-3 shadow-xs ring-1 ring-foreground/10">
              <CardContent className="px-3">
              <p className="mb-2 text-xs font-semibold">Sector Momentum (by GICS)</p>
              {sectorMomentum.length === 0 ? (
                <p className="text-xs text-muted-foreground">No data</p>
              ) : (
                <div className="flex flex-col gap-1">
                  {sectorMomentum.slice(0, 10).map((sm, i) => (
                    <div key={`sector-mom-${sm.sector}-${i}`} className="flex items-center justify-between text-xs">
                      <span className="max-w-[140px] truncate">{sm.sector}</span>
                      <div className="flex items-center gap-2">
                        <span className={heatTextClass(sm.avg_perf_20d)}>{fmtPct(sm.avg_perf_20d)}</span>
                        <span className="text-muted-foreground">({sm.count})</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              </CardContent>
            </Card>
          </div>
            </Collapsible.Content>
          </Collapsible.Root>
        </div>
        )}

        {/* Scatter/Bubble Chart */}
        {vis.scatter && (
          <div>
            <SectionHeading title="Universe Scatter" sectionKey="scatter" isCollapsed={collapsed.has('scatter')} onToggle={() => toggle('scatter')} />
            <Collapsible.Root open={!collapsed.has('scatter')}>
              <Collapsible.Content>
            <Card className="gap-0 py-4 shadow-xs ring-1 ring-foreground/10">
              <CardContent className="px-4">
              <LazyBubbleChart onSymbolClick={openChart} collapsed={collapsed.has('scatter')} />
              </CardContent>
            </Card>
              </Collapsible.Content>
            </Collapsible.Root>
          </div>
        )}

        {/* Section 3: Trading Setups */}
        {vis.setups && (
        <div>
          <SectionHeading title="Trading Setups" sectionKey="setups" isCollapsed={collapsed.has('setups')} onToggle={() => toggle('setups')} count={breakoutCandidates.length + pullbackCandidates.length + rsLeaders.length + leaders.length} />
          <Collapsible.Root open={!collapsed.has('setups')}>
            <Collapsible.Content>
              {(breakoutCandidates.length + pullbackCandidates.length + rsLeaders.length + leaders.length) === 0 ? (
                <EmptyState mode={universeFilter} noun="trading setups" />
              ) : (
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <SetupCard title="Breakout Candidates" items={breakoutCandidates} linkPreset="breakout" showHeldBadge={showHeld} />
                  <SetupCard title="Pullback Buys" items={pullbackCandidates} linkPreset="pullback" showHeldBadge={showHeld} />
                  <SetupCard title="RS Leaders" items={rsLeaders} linkPreset="rs_leaders" showHeldBadge={showHeld} />
                  <SetupCard title="Momentum Leaders" items={leaders} showScore linkPreset="momentum" showHeldBadge={showHeld} />
                </div>
              )}
            </Collapsible.Content>
          </Collapsible.Root>
        </div>
        )}

        {/* Section 4: Stage Transitions */}
        {vis.transitions && (
        <div>
          <SectionHeading title="Stage Transitions" sectionKey="transitions" isCollapsed={collapsed.has('transitions')} onToggle={() => toggle('transitions')} count={enteringStage2a.length + entering34.length} />
          <Collapsible.Root open={!collapsed.has('transitions')}>
            <Collapsible.Content>
              {(enteringStage2a.length + entering34.length) === 0 ? (
                <EmptyState mode={universeFilter} noun="stage transitions" />
              ) : (
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <TransitionList title="Entering Stage 2A (Bullish)" items={enteringStage2a} colorPalette="green" showHeldBadge={showHeld} />
                  <TransitionList title="Entering Stage 3/4 (Warning)" items={entering34} colorPalette="red" showHeldBadge={showHeld} />
                </div>
              )}
            </Collapsible.Content>
          </Collapsible.Root>
        </div>
        )}

        {/* Section 5: Ranked Metrics */}
        {vis.ranked && (
        <div>
          <SectionHeading title="Top / Bottom 10 Matrix" sectionKey="ranked" isCollapsed={collapsed.has('ranked')} onToggle={() => toggle('ranked')} />
          <Collapsible.Root open={!collapsed.has('ranked')}>
            <Collapsible.Content>
              <div className="flex flex-col gap-3">
                <RankMatrix title="Top 10 Matrix" data={top10Matrix} />
                <RankMatrix title="Bottom 10 Matrix" data={bottom10Matrix} />
              </div>
            </Collapsible.Content>
          </Collapsible.Root>
        </div>
        )}

        {/* Section 6: Entry/Exit Proximity */}
        {vis.proximity && (
        <div>
          <SectionHeading title="Entry / Exit Proximity" sectionKey="proximity" isCollapsed={collapsed.has('proximity')} onToggle={() => toggle('proximity')} />
          <Collapsible.Root open={!collapsed.has('proximity')}>
            <Collapsible.Content>
          <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
            <Card className="gap-0 py-3 shadow-xs ring-1 ring-foreground/10">
              <CardContent className="px-3">
              <p className="mb-2 text-xs font-semibold">Top 10 Closest to Entry</p>
              <TableShell>
                <thead className="border-b border-border bg-muted/50">
                  <tr>
                    <th className="px-2 py-2 font-medium">Symbol</th>
                    <th className="px-2 py-2 font-medium">Stage</th>
                    <th className="px-2 py-2 font-medium">Entry</th>
                    <th className="px-2 py-2 font-medium">Dist %</th>
                    <th className="px-2 py-2 font-medium">Dist ATR</th>
                  </tr>
                </thead>
                <tbody>
                  {entryRows.slice(0, 10).length ? (
                    entryRows.slice(0, 10).map((r: any, i: number) => {
                      const distClass =
                        typeof r.distance_pct === 'number' && Math.abs(r.distance_pct) <= 3
                          ? semanticTextColorClass('green.400')
                          : undefined;
                      return (
                        <tr key={`entry-${r.symbol}-${i}`} className="border-b border-border/60">
                          <td className="px-2 py-1.5"><SymbolLink symbol={r.symbol} showHeldBadge={showHeld} /></td>
                          <td className="px-2 py-1.5"><StageBadge stage={r.stage_label || '?'} /></td>
                          <td className="px-2 py-1.5">{typeof r.entry_price === 'number' ? r.entry_price.toFixed(2) : '—'}</td>
                          <td className={cn('px-2 py-1.5', distClass)}>
                            {typeof r.distance_pct === 'number' ? `${r.distance_pct.toFixed(2)}%` : '—'}
                          </td>
                          <td className="px-2 py-1.5">{typeof r.distance_atr === 'number' ? `${r.distance_atr.toFixed(2)}x` : '—'}</td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={5} className="px-2 py-2 text-xs text-muted-foreground">
                        No entry prices set yet. Set Entry prices in Market Tracked.
                      </td>
                    </tr>
                  )}
                </tbody>
              </TableShell>
              </CardContent>
            </Card>

            <Card className="gap-0 py-3 shadow-xs ring-1 ring-foreground/10">
              <CardContent className="px-3">
              <p className="mb-2 text-xs font-semibold">Top 10 Closest to Exit</p>
              <TableShell>
                <thead className="border-b border-border bg-muted/50">
                  <tr>
                    <th className="px-2 py-2 font-medium">Symbol</th>
                    <th className="px-2 py-2 font-medium">Stage</th>
                    <th className="px-2 py-2 font-medium">Exit</th>
                    <th className="px-2 py-2 font-medium">Dist %</th>
                    <th className="px-2 py-2 font-medium">Dist ATR</th>
                  </tr>
                </thead>
                <tbody>
                  {exitRows.slice(0, 10).length ? (
                    exitRows.slice(0, 10).map((r: any, i: number) => {
                      const distClass =
                        typeof r.distance_pct === 'number' && Math.abs(r.distance_pct) <= 3
                          ? semanticTextColorClass('red.400')
                          : undefined;
                      return (
                        <tr key={`exit-${r.symbol}-${i}`} className="border-b border-border/60">
                          <td className="px-2 py-1.5"><SymbolLink symbol={r.symbol} showHeldBadge={showHeld} /></td>
                          <td className="px-2 py-1.5"><StageBadge stage={r.stage_label || '?'} /></td>
                          <td className="px-2 py-1.5">{typeof r.exit_price === 'number' ? r.exit_price.toFixed(2) : '—'}</td>
                          <td className={cn('px-2 py-1.5', distClass)}>
                            {typeof r.distance_pct === 'number' ? `${r.distance_pct.toFixed(2)}%` : '—'}
                          </td>
                          <td className="px-2 py-1.5">{typeof r.distance_atr === 'number' ? `${r.distance_atr.toFixed(2)}x` : '—'}</td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={5} className="px-2 py-2 text-xs text-muted-foreground">
                        No exit prices set yet. Set Exit prices in Market Tracked.
                      </td>
                    </tr>
                  )}
                </tbody>
              </TableShell>
              </CardContent>
            </Card>
          </div>
            </Collapsible.Content>
          </Collapsible.Root>
        </div>
        )}

        {/* Market Insights */}
        {vis.insights && (
        <div>
          <SectionHeading title="Market Insights" sectionKey="insights" isCollapsed={collapsed.has('insights')} onToggle={() => toggle('insights')} />
          <Collapsible.Root open={!collapsed.has('insights')}>
            <Collapsible.Content>
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <div className="flex flex-col gap-3">
              {(payload?.range_histogram || []).length > 0 && (
                <RangeHistogram bins={payload!.range_histogram!} />
              )}
              {(payload?.breadth_series || []).length > 0 && (
                <BreadthChart series={payload!.breadth_series!} />
              )}
            </div>
            {rrgSectors.length > 0 ? <RRGChart sectors={rrgSectors} /> : null}
          </div>
            </Collapsible.Content>
          </Collapsible.Root>
        </div>
        )}

        {/* Signals & Divergences */}
        {vis.signals && (
        <div>
          <SectionHeading title="Signals & Divergences" sectionKey="signals" isCollapsed={collapsed.has('signals')} onToggle={() => toggle('signals')} count={rsiBearish.length + rsiBullish.length + tdSignals.length + gapLeaders.length} />
          <Collapsible.Root open={!collapsed.has('signals')}>
            <Collapsible.Content>
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
            <Card className="gap-0 py-3 shadow-xs ring-1 ring-foreground/10">
              <CardContent className="px-3">
              <p className="mb-2 text-xs font-semibold">Divergence Watch</p>
              {(rsiBearish.length + rsiBullish.length) === 0 ? (
                <p className="text-xs text-muted-foreground">No divergences detected</p>
              ) : (
                <div className="max-h-[300px] overflow-y-auto pr-1">
                  <div className="flex flex-col gap-2">
                    {rsiBearish.length > 0 && (
                      <div>
                        <Badge variant="destructive" className="mb-1 h-5 border-transparent bg-destructive/10 font-normal">
                          Bearish ({rsiBearish.length})
                        </Badge>
                        {rsiBearish.map((d, i) => (
                          <div key={`div-b-${d.symbol}-${i}`} className="flex items-center justify-between py-px text-xs">
                            <SymbolLink symbol={d.symbol} />
                            <div className="flex items-center gap-2">
                              <span className={semanticTextColorClass('green.400')}>+{d.perf_20d}%</span>
                              <span className={semanticTextColorClass('red.400')}>RSI {d.rsi}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    {rsiBullish.length > 0 && (
                      <div>
                        <Badge variant="secondary" className="mb-1 h-5 border-transparent bg-[rgb(var(--status-success)/0.12)] font-normal text-[rgb(var(--status-success)/1)]">
                          Bullish ({rsiBullish.length})
                        </Badge>
                        {rsiBullish.map((d, i) => (
                          <div key={`div-l-${d.symbol}-${i}`} className="flex items-center justify-between py-px text-xs">
                            <SymbolLink symbol={d.symbol} />
                            <div className="flex items-center gap-2">
                              <span className={semanticTextColorClass('red.400')}>{d.perf_20d}%</span>
                              <span className={semanticTextColorClass('green.400')}>RSI {d.rsi}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
              </CardContent>
            </Card>

            <Card className="gap-0 py-3 shadow-xs ring-1 ring-foreground/10">
              <CardContent className="px-3">
              <div className="mb-1 flex items-center justify-between">
                <p className="text-xs font-semibold">TD Sequential Signals</p>
                {tdSignals.length > 0 ? (
                  <Badge variant="secondary" className="h-5 font-normal">{tdSignals.length}</Badge>
                ) : null}
              </div>
              <p className="mb-2 text-xs text-muted-foreground">Setup 9 = potential reversal. Countdown 13 = exhaustion confirmed.</p>
              {tdSignals.length === 0 ? (
                <p className="text-xs text-muted-foreground">No active signals</p>
              ) : (
                <div className="max-h-[300px] overflow-y-auto">
                  <div className="grid grid-cols-1 gap-1 xl:grid-cols-2 xl:gap-x-3">
                    {tdSignals.map((s, i) => (
                      <div key={`td-${s.symbol}-${i}`} className="flex items-center justify-between border-b border-border py-px text-xs">
                        <div className="flex items-center gap-1">
                          <SymbolLink symbol={s.symbol} />
                          <StageBadge stage={s.stage_label || '?'} />
                        </div>
                        <div className="flex shrink-0 flex-wrap items-center justify-end gap-1">
                          {s.signals.map((sig, j) => (
                            <Badge
                              key={j}
                              variant="outline"
                              className={cn(
                                'h-5 px-1.5 font-normal',
                                sig.includes('Buy')
                                  ? 'border-[rgb(var(--status-success)/0.35)] text-[rgb(var(--status-success)/1)]'
                                  : 'border-destructive/35 text-destructive',
                              )}
                            >
                              {sig}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              </CardContent>
            </Card>

            <Card className="gap-0 py-3 shadow-xs ring-1 ring-foreground/10">
              <CardContent className="px-3">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-xs font-semibold">Open Gaps</p>
                {gapLeaders.length > 0 ? <Badge variant="secondary" className="h-5 font-normal">{gapLeaders.length}</Badge> : null}
              </div>
              <p className="mb-2 text-xs text-muted-foreground">Symbols with unfilled price gaps (potential support/resistance).</p>
              {gapLeaders.length === 0 ? (
                <p className="text-xs text-muted-foreground">No unfilled gaps detected. Gap data populates after indicator computation runs.</p>
              ) : (
                <div className="max-h-[300px] overflow-y-auto">
                  <div className="flex flex-col gap-1">
                    {gapLeaders.map((g, i) => (
                      <div key={`gap-${g.symbol}-${i}`} className="flex items-center justify-between border-b border-border py-px text-xs">
                        <div className="flex items-center gap-1">
                          <SymbolLink symbol={g.symbol} />
                          <StageBadge stage={g.stage_label || '?'} />
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          <span className={semanticTextColorClass('green.400')}>{g.gaps_up}↑</span>
                          <span className={semanticTextColorClass('red.400')}>{g.gaps_down}↓</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              </CardContent>
            </Card>
          </div>
            </Collapsible.Content>
          </Collapsible.Root>
        </div>
        )}

        {/* Earnings & Fundamentals */}
        {vis.earnings && (
        <div>
          <SectionHeading title="Earnings & Fundamentals" sectionKey="earnings" isCollapsed={collapsed.has('earnings')} onToggle={() => toggle('earnings')} count={upcomingEarnings.length + fundamentalLeaders.length} />
          <Collapsible.Root open={!collapsed.has('earnings')}>
            <Collapsible.Content>
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <Card className="gap-0 py-3 shadow-xs ring-1 ring-foreground/10">
              <CardContent className="px-3">
              <p className="mb-2 text-xs font-semibold">Upcoming Earnings (7d)</p>
              {upcomingEarnings.length === 0 ? (
                <p className="text-xs text-muted-foreground">No upcoming earnings</p>
              ) : (
                <div className="max-h-[260px] overflow-y-auto pr-1">
                  <div className="flex flex-col gap-1">
                    {upcomingEarnings.map((e, i) => (
                      <div key={`earn-${e.symbol}-${i}`} className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-1">
                          <SymbolLink symbol={e.symbol} />
                          <StageBadge stage={e.stage_label || '?'} />
                        </div>
                        <span className="text-muted-foreground">{formatDate(e.next_earnings, timezone)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              </CardContent>
            </Card>

            <Card className="gap-0 py-3 shadow-xs ring-1 ring-foreground/10">
              <CardContent className="px-3">
              <p className="mb-2 text-xs font-semibold">Fundamental Leaders</p>
              {fundamentalLeaders.length === 0 ? (
                <p className="text-xs text-muted-foreground">Insufficient data</p>
              ) : (
                <div className="max-h-[260px] overflow-y-auto pr-1">
                  <div className="flex flex-col gap-1">
                    {fundamentalLeaders.map((f, i) => (
                      <div key={`fund-${f.symbol}-${i}`} className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-1">
                          <SymbolLink symbol={f.symbol} />
                          <StageBadge stage={f.stage_label || '?'} />
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          <span>EPS {f.eps_growth_yoy > 0 ? '+' : ''}{f.eps_growth_yoy}%</span>
                          <span className={heatTextClass(f.rs_mansfield_pct)}>RS {fmtPct(f.rs_mansfield_pct)}</span>
                          {f.pe_ttm != null ? <span className="text-muted-foreground">PE {f.pe_ttm}</span> : null}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              </CardContent>
            </Card>
          </div>
            </Collapsible.Content>
          </Collapsible.Root>
        </div>
        )}

        </>
        )}

      </div>
      <ChartSlidePanel symbol={chartSymbol} onClose={() => setChartSymbol(null)} />
    </Page>
    </ChartContext.Provider>
    </PortfolioSymbolsContext.Provider>
  );
};

export default MarketDashboard;
