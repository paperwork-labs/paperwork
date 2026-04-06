import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { marketDataApi } from '../../services/api';
import { REGIME_HEX } from '../../constants/chart';
import { useRegime } from '../../hooks/useRegime';
import { useVolatility } from '../../hooks/useVolatility';
import { useChartColors } from '../../hooks/useChartColors';
import StatCard from '../shared/StatCard';
import {
  ComposedChart, Area, XAxis, YAxis, Tooltip as RTooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { cn } from '@/lib/utils';
import type { RegimeData } from './RegimeBanner';
import { heatTextClass, semanticTextColorClass } from '@/lib/semantic-text-color';
import { Badge } from '@/components/ui/badge';

const DATA_CELL = 'font-mono text-xs tracking-tight';

const REGIME_LABELS: Record<string, string> = {
  R1: 'Bull', R2: 'Bull Extended', R3: 'Chop', R4: 'Bear Rally', R5: 'Bear',
};

const fmtPct = (v: unknown): string => {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—';
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
};

const INDEX_SYMBOLS = ['SPY', 'RSP', 'MDY', 'DIA', 'IWM', 'QQQ'];

interface TopDownViewProps {
  snapshots: any[];
  dashboardPayload: any;
}

function stageEtfBadgeClass(stage: string | undefined | null): string {
  if (!stage) return '';
  if (stage.startsWith('2')) {
    return 'border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300';
  }
  if (stage.startsWith('4')) {
    return 'border-red-500/40 bg-red-500/10 text-red-800 dark:text-red-300';
  }
  if (stage.startsWith('3')) {
    return 'border-orange-500/40 bg-orange-500/10 text-orange-800 dark:text-orange-300';
  }
  return 'border-border bg-muted text-muted-foreground';
}

type VolDashboardFields = {
  vix?: number | null;
  vix3m?: number | null;
  vvix?: number | null;
  term_structure_ratio?: number | null;
  vol_of_vol_ratio?: number | null;
};

const TopDownView: React.FC<TopDownViewProps> = ({ snapshots, dashboardPayload }) => {
  const cc = useChartColors();

  const { data: regimeRaw } = useRegime();
  const regimeData = (regimeRaw ?? null) as RegimeData | null;

  const { data: regimeHistory } = useQuery({
    queryKey: ['regime-history-90'],
    queryFn: async () => {
      const resp = await marketDataApi.getRegimeHistory(90);
      return resp?.data?.history ?? resp?.history ?? [];
    },
    staleTime: 5 * 60_000,
  });

  const { data: volRaw } = useVolatility();
  const volData = volRaw as VolDashboardFields | null | undefined;

  const snapshotMap = React.useMemo(() => {
    const m = new Map<string, any>();
    (snapshots || []).forEach((s: any) => {
      if (s?.symbol) m.set(s.symbol.toUpperCase(), s);
    });
    return m;
  }, [snapshots]);

  const regimeColor = regimeData?.regime_state
    ? REGIME_HEX[regimeData.regime_state] || '#64748B'
    : '#64748B';

  const breadthAbove50 = dashboardPayload?.regime?.above_sma50_count ?? 0;
  const breadthAbove200 = dashboardPayload?.regime?.above_sma200_count ?? 0;
  const total = dashboardPayload?.snapshot_count ?? 1;

  const indexRows = React.useMemo(() =>
    INDEX_SYMBOLS.map(sym => {
      const snap = snapshotMap.get(sym);
      return {
        symbol: sym,
        price: snap?.current_price,
        perf_1d: snap?.perf_1d,
        perf_5d: snap?.perf_5d,
        perf_20d: snap?.perf_20d,
        perf_252d: snap?.perf_252d,
        rsi: snap?.rsi,
      };
    }), [snapshotMap]);

  const sectorRows = React.useMemo(() =>
    (dashboardPayload?.sector_etf_table || []).map((r: any) => ({
      symbol: r.symbol,
      name: r.sector_name,
      change_1d: r.change_1d,
      change_5d: r.change_5d,
      change_20d: r.change_20d,
      rs: r.rs_mansfield_pct,
      stage: r.stage_label,
    })), [dashboardPayload]);

  const regimeChartData = React.useMemo(() =>
    (regimeHistory || []).map((r: any) => ({
      date: r.as_of_date?.slice(5),
      score: r.composite_score,
      state: r.regime_state,
    })), [regimeHistory]);

  const termRatio = volData?.term_structure_ratio ?? 1;
  const termHintClass = cn(
    termRatio < 1
      ? semanticTextColorClass('red.500')
      : termRatio > 1.15
        ? semanticTextColorClass('orange.500')
        : semanticTextColorClass('green.500')
  );
  const volOfVol = volData?.vol_of_vol_ratio ?? 5;
  const volOfVolHintClass = cn(
    volOfVol < 3.5
      ? semanticTextColorClass('green.500')
      : volOfVol > 6
        ? semanticTextColorClass('red.500')
        : 'text-muted-foreground'
  );

  return (
    <div className="flex flex-col gap-5">
      {regimeData && (
        <div
          className="relative overflow-hidden rounded-xl border-2 bg-card p-4"
          style={{ borderColor: regimeColor }}
        >
          <div
            className="pointer-events-none absolute inset-0"
            style={{ backgroundColor: regimeColor, opacity: 0.06 }}
            aria-hidden
          />
          <div className="relative flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-3">
              <div
                className="rounded-md px-3 py-1 text-lg font-bold text-white"
                style={{ backgroundColor: regimeColor }}
              >
                {regimeData.regime_state}
              </div>
              <div>
                <p className="text-base font-semibold">
                  {REGIME_LABELS[regimeData.regime_state] || regimeData.regime_state}
                </p>
                <p className="text-xs text-muted-foreground">
                  Composite: {regimeData.composite_score?.toFixed(2)} | As of {regimeData.as_of_date}
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-4">
              <StatCard label="Sizing Mult" value={`${regimeData.regime_multiplier?.toFixed(2)}x`} />
              <StatCard label="Max Equity" value={`${regimeData.max_equity_exposure_pct}%`} />
              <StatCard label="Cash Floor" value={`${regimeData.cash_floor_pct}%`} />
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="mb-3 text-sm font-semibold">Regime Composite (90d)</p>
          {regimeChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <ComposedChart data={regimeChartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="regimeGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={regimeColor} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={regimeColor} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" tick={{ fontSize: 9, fill: cc.muted }} tickLine={false} axisLine={false} interval={Math.floor(regimeChartData.length / 6)} />
                <YAxis domain={[1, 5]} tick={{ fontSize: 9, fill: cc.muted }} tickLine={false} axisLine={false} width={30} />
                <ReferenceLine y={2.5} stroke={cc.refLine} strokeDasharray="4 3" />
                <ReferenceLine y={3.5} stroke={cc.refLine} strokeDasharray="4 3" />
                <RTooltip
                  contentStyle={{ fontSize: 12, borderRadius: 8, border: `1px solid ${cc.border}`, background: cc.tooltipBg, fontFamily: 'JetBrains Mono, monospace' }}
                  formatter={(v: any) => [Number(v).toFixed(2), 'Composite']}
                />
                <Area type="monotone" dataKey="score" fill="url(#regimeGrad)" stroke={regimeColor} strokeWidth={2} />
              </ComposedChart>
            </ResponsiveContainer>
          ) : (
            <p className="py-8 text-center text-xs text-muted-foreground">No regime history available</p>
          )}
        </div>

        <div className="rounded-lg border border-border bg-card p-4">
          <p className="mb-3 text-sm font-semibold">Volatility</p>
          <div className="grid grid-cols-3 gap-3">
            <div className="text-center">
              <p className="font-mono text-2xl font-bold tracking-tight">{volData?.vix?.toFixed(1) ?? '—'}</p>
              <p className="text-xs text-muted-foreground">VIX</p>
            </div>
            <div className="text-center">
              <p className="font-mono text-2xl font-bold tracking-tight">{volData?.vix3m?.toFixed(1) ?? '—'}</p>
              <p className="text-xs text-muted-foreground">VIX3M</p>
            </div>
            <div className="text-center">
              <p className="font-mono text-2xl font-bold tracking-tight">{volData?.vvix?.toFixed(1) ?? '—'}</p>
              <p className="text-xs text-muted-foreground">VVIX</p>
            </div>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <div className="rounded-md bg-muted/60 p-2 text-center transition-colors">
              <p className="font-mono text-sm font-semibold">
                {volData?.term_structure_ratio?.toFixed(3) ?? '—'}
              </p>
              <p className="text-xs text-muted-foreground">VIX3M/VIX</p>
              <p className={cn('text-[10px]', termHintClass)}>
                {termRatio < 1 ? 'Backwardation' :
                  termRatio > 1.15 ? 'Mkt Overbought' : 'Normal Contango'}
              </p>
            </div>
            <div className="rounded-md bg-muted/60 p-2 text-center transition-colors">
              <p className="font-mono text-sm font-semibold">
                {volData?.vol_of_vol_ratio?.toFixed(2) ?? '—'}
              </p>
              <p className="text-xs text-muted-foreground">VVIX/VIX</p>
              <p className={cn('text-[10px]', volOfVolHintClass)}>
                {volOfVol < 3.5 ? 'Buy Protection' :
                  volOfVol > 6 ? 'Sell Protection' : 'Neutral'}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard label="% Above 50 DMA" value={total > 0 ? `${((breadthAbove50 / total) * 100).toFixed(0)}%` : '—'} />
        <StatCard label="% Above 200 DMA" value={total > 0 ? `${((breadthAbove200 / total) * 100).toFixed(0)}%` : '—'} />
        <StatCard label="Advancing" value={String(dashboardPayload?.regime?.up_1d_count ?? '—')} />
        <StatCard label="Declining" value={String(dashboardPayload?.regime?.down_1d_count ?? '—')} />
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <p className="mb-3 text-sm font-semibold">Index Performance</p>
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="px-2 py-2 text-left font-medium">Index</th>
                <th className="px-2 py-2 text-right font-medium">Price</th>
                <th className="px-2 py-2 text-right font-medium">1D</th>
                <th className="px-2 py-2 text-right font-medium">5D</th>
                <th className="px-2 py-2 text-right font-medium">MTD</th>
                <th className="px-2 py-2 text-right font-medium">YTD</th>
                <th className="px-2 py-2 text-right font-medium">RSI</th>
              </tr>
            </thead>
            <tbody>
              {indexRows.map(row => (
                <tr
                  key={row.symbol}
                  className="border-b border-border/80 transition-colors last:border-0 hover:bg-[rgb(var(--bg-hover))]"
                >
                  <td className="px-2 py-2 font-semibold">{row.symbol}</td>
                  <td className={cn('px-2 py-2 text-right', DATA_CELL)}>{row.price?.toFixed(2) ?? '—'}</td>
                  <td className={cn('px-2 py-2 text-right', DATA_CELL, heatTextClass(row.perf_1d))}>{fmtPct(row.perf_1d)}</td>
                  <td className={cn('px-2 py-2 text-right', DATA_CELL, heatTextClass(row.perf_5d))}>{fmtPct(row.perf_5d)}</td>
                  <td className={cn('px-2 py-2 text-right', DATA_CELL, heatTextClass(row.perf_20d))}>{fmtPct(row.perf_20d)}</td>
                  <td className={cn('px-2 py-2 text-right', DATA_CELL, heatTextClass(row.perf_252d))}>{fmtPct(row.perf_252d)}</td>
                  <td className={cn(
                    'px-2 py-2 text-right',
                    DATA_CELL,
                    (row.rsi ?? 50) > 70 ? semanticTextColorClass('red.500') : (row.rsi ?? 50) < 30 ? semanticTextColorClass('green.500') : undefined
                  )}>{row.rsi?.toFixed(0) ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {sectorRows.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="mb-3 text-sm font-semibold">Sector ETFs</p>
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-2 py-2 text-left font-medium">ETF</th>
                  <th className="px-2 py-2 text-left font-medium">Sector</th>
                  <th className="px-2 py-2 text-right font-medium">1D</th>
                  <th className="px-2 py-2 text-right font-medium">5D</th>
                  <th className="px-2 py-2 text-right font-medium">20D</th>
                  <th className="px-2 py-2 text-right font-medium">RS</th>
                  <th className="px-2 py-2 text-left font-medium">Stage</th>
                </tr>
              </thead>
              <tbody>
                {sectorRows.map((row: any) => (
                  <tr
                    key={row.symbol}
                    className="border-b border-border/80 transition-colors last:border-0 hover:bg-[rgb(var(--bg-hover))]"
                  >
                    <td className="px-2 py-2 font-semibold">{row.symbol}</td>
                    <td className="px-2 py-2 text-xs text-muted-foreground">{row.name || '—'}</td>
                    <td className={cn('px-2 py-2 text-right', DATA_CELL, heatTextClass(row.change_1d))}>{fmtPct(row.change_1d)}</td>
                    <td className={cn('px-2 py-2 text-right', DATA_CELL, heatTextClass(row.change_5d))}>{fmtPct(row.change_5d)}</td>
                    <td className={cn('px-2 py-2 text-right', DATA_CELL, heatTextClass(row.change_20d))}>{fmtPct(row.change_20d)}</td>
                    <td className={cn('px-2 py-2 text-right', DATA_CELL, heatTextClass(row.rs))}>{fmtPct(row.rs)}</td>
                    <td className="px-2 py-2">
                      <Badge variant="outline" className={cn('font-normal', stageEtfBadgeClass(row.stage))}>
                        {row.stage || '—'}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default TopDownView;
