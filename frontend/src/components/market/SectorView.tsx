import React from 'react';
import StageBadge from '../shared/StageBadge';
import { SymbolLink } from './SymbolChartUI';
import { heatTextClass, semanticTextColorClass } from '@/lib/semantic-text-color';
import { useChartColors } from '../../hooks/useChartColors';
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, Tooltip as RTooltip,
  ResponsiveContainer, ReferenceLine, ReferenceArea, Cell, CartesianGrid,
} from 'recharts';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';

const DATA_CELL = 'font-mono text-xs tracking-tight';

/** Distinct fills for RRG scatter — theme chart tokens (SVG-safe). */
const SECTOR_SCATTER_FILLS = [
  'var(--chart-1)',
  'var(--chart-2)',
  'var(--chart-3)',
  'var(--chart-4)',
  'var(--chart-5)',
] as const;

const fmtPct = (v: unknown): string => {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—';
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
};

interface SectorViewProps {
  snapshots: any[];
  dashboardPayload: any;
}

function sectorFill(i: number): string {
  return SECTOR_SCATTER_FILLS[i % SECTOR_SCATTER_FILLS.length];
}

function healthBadgeClass(health: string): string {
  if (health === 'bullish') {
    return 'border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300';
  }
  if (health === 'bearish') {
    return 'border-red-500/40 bg-red-500/10 text-red-800 dark:text-red-300';
  }
  return 'border-border bg-muted text-muted-foreground';
}

const SectorView: React.FC<SectorViewProps> = ({ snapshots, dashboardPayload }) => {
  const cc = useChartColors();
  const [selectedSector, setSelectedSector] = React.useState<string | null>(null);

  const sectorMap = React.useMemo(() => {
    const m = new Map<string, any[]>();
    snapshots.forEach((s: any) => {
      const sector = s.sector || 'Unknown';
      if (!m.has(sector)) m.set(sector, []);
      m.get(sector)!.push(s);
    });
    return m;
  }, [snapshots]);

  const sectorSummaries = React.useMemo(() =>
    Array.from(sectorMap.entries()).map(([sector, stocks]) => {
      const n = stocks.length;
      const avgPerf1d = stocks.reduce((a: number, s: any) => a + (s.perf_1d || 0), 0) / n;
      const avgPerf20d = stocks.reduce((a: number, s: any) => a + (s.perf_20d || 0), 0) / n;
      const avgRS = stocks.reduce((a: number, s: any) => a + (s.rs_mansfield_pct || 0), 0) / n;
      const stage2count = stocks.filter((s: any) => s.stage_label?.startsWith('2')).length;
      const stage4count = stocks.filter((s: any) => s.stage_label?.startsWith('4')).length;
      return {
        sector, count: n, avgPerf1d, avgPerf20d, avgRS,
        stage2pct: (stage2count / n) * 100,
        stage4pct: (stage4count / n) * 100,
        health: stage2count > stage4count ? 'bullish' : stage4count > stage2count ? 'bearish' : 'neutral',
      };
    }).sort((a, b) => b.avgRS - a.avgRS),
    [sectorMap]);

  const rrgData = React.useMemo(() =>
    (dashboardPayload?.rrg_sectors || []).map((s: any, i: number) => ({
      ...s, z: 200, _idx: i,
    })), [dashboardPayload]);

  const selectedStocks = React.useMemo(() => {
    if (!selectedSector) return [];
    return (sectorMap.get(selectedSector) || [])
      .sort((a: any, b: any) => (b.rs_mansfield_pct || 0) - (a.rs_mansfield_pct || 0));
  }, [selectedSector, sectorMap]);

  const maxAbs = React.useMemo(() => {
    if (!rrgData.length) return 5;
    return Math.max(
      ...rrgData.map((s: any) => Math.abs(s.rs_ratio || 0)),
      ...rrgData.map((s: any) => Math.abs(s.rs_momentum || 0)),
      1,
    );
  }, [rrgData]);
  const pad = Math.ceil(maxAbs * 1.15) || 5;

  return (
    <div className="flex flex-col gap-5">
      {rrgData.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="mb-2 text-sm font-semibold">Relative Rotation Graph</p>
          <ResponsiveContainer width="100%" height={380}>
            <ScatterChart>
              <CartesianGrid strokeDasharray="3 3" stroke={cc.grid} />
              <XAxis type="number" dataKey="rs_ratio" domain={[-pad, pad]} hide />
              <YAxis type="number" dataKey="rs_momentum" domain={[-pad, pad]} hide />
              <ZAxis type="number" dataKey="z" range={[160, 160]} />
              <ReferenceArea x1={0} x2={pad} y1={0} y2={pad} fill={cc.success} fillOpacity={0.05} label={{ value: 'Leading', position: 'insideTopRight', fontSize: 11, fill: cc.success, fontWeight: 600 }} />
              <ReferenceArea x1={-pad} x2={0} y1={0} y2={pad} fill={cc.area2} fillOpacity={0.05} label={{ value: 'Improving', position: 'insideTopLeft', fontSize: 11, fill: cc.neutral, fontWeight: 600 }} />
              <ReferenceArea x1={-pad} x2={0} y1={-pad} y2={0} fill={cc.danger} fillOpacity={0.05} label={{ value: 'Lagging', position: 'insideBottomLeft', fontSize: 11, fill: cc.danger, fontWeight: 600 }} />
              <ReferenceArea x1={0} x2={pad} y1={-pad} y2={0} fill={cc.warning} fillOpacity={0.05} label={{ value: 'Weakening', position: 'insideBottomRight', fontSize: 11, fill: cc.warning, fontWeight: 600 }} />
              <ReferenceLine x={0} stroke={cc.refLine} strokeWidth={1.5} />
              <ReferenceLine y={0} stroke={cc.refLine} strokeWidth={1.5} />
              <RTooltip
                contentStyle={{ fontSize: 12, borderRadius: 8, border: `1px solid ${cc.tooltipBorder}`, background: cc.tooltipBg, fontFamily: 'JetBrains Mono, monospace' }}
                formatter={(v: any, name: any) => [Number(v).toFixed(2), String(name ?? '')]}
              />
              <Scatter data={rrgData}>
                {rrgData.map((_: any, i: number) => (
                  <Cell key={i} fill={sectorFill(i)} stroke="#ffffff" strokeWidth={1.5} />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
          <div className="mt-2 grid gap-px" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))' }}>
            {rrgData.map((s: any, i: number) => (
              <div key={s.symbol} className="flex items-center gap-1">
                <div
                  className="size-2 shrink-0 rounded-full"
                  style={{ backgroundColor: sectorFill(i) }}
                  aria-hidden
                />
                <span className="truncate text-[10px] text-muted-foreground">{s.name}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="rounded-lg border border-border bg-card p-4">
        <p className="mb-3 text-sm font-semibold">Sector Health Matrix</p>
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="px-2 py-2 text-left font-medium">Sector</th>
                <th className="px-2 py-2 text-right font-medium">Count</th>
                <th className="px-2 py-2 text-right font-medium">Avg 1D</th>
                <th className="px-2 py-2 text-right font-medium">Avg 20D</th>
                <th className="px-2 py-2 text-right font-medium">Avg RS</th>
                <th className="px-2 py-2 text-right font-medium">Stage 2 %</th>
                <th className="px-2 py-2 text-right font-medium">Stage 4 %</th>
                <th className="px-2 py-2 text-left font-medium">Health</th>
              </tr>
            </thead>
            <tbody>
              {sectorSummaries.map(row => (
                <tr
                  key={row.sector}
                  className={cn(
                    'cursor-pointer border-b border-border/80 transition-colors last:border-0 hover:bg-[rgb(var(--bg-hover))]',
                    selectedSector === row.sector && 'bg-muted/60'
                  )}
                  onClick={() => setSelectedSector(prev => prev === row.sector ? null : row.sector)}
                >
                  <td className="px-2 py-2 text-xs font-semibold">{row.sector}</td>
                  <td className={cn('px-2 py-2 text-right', DATA_CELL)}>{row.count}</td>
                  <td className={cn('px-2 py-2 text-right', DATA_CELL, heatTextClass(row.avgPerf1d))}>{fmtPct(row.avgPerf1d)}</td>
                  <td className={cn('px-2 py-2 text-right', DATA_CELL, heatTextClass(row.avgPerf20d))}>{fmtPct(row.avgPerf20d)}</td>
                  <td className={cn('px-2 py-2 text-right', DATA_CELL, heatTextClass(row.avgRS))}>{fmtPct(row.avgRS)}</td>
                  <td className={cn('px-2 py-2 text-right', DATA_CELL, semanticTextColorClass('green.500'))}>{row.stage2pct.toFixed(0)}%</td>
                  <td className={cn('px-2 py-2 text-right', DATA_CELL, semanticTextColorClass('red.500'))}>{row.stage4pct.toFixed(0)}%</td>
                  <td className="px-2 py-2">
                    <Badge variant="outline" className={cn('font-normal', healthBadgeClass(row.health))}>
                      {row.health}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selectedSector && selectedStocks.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="mb-3 flex items-center justify-between gap-2">
            <p className="text-sm font-semibold">{selectedSector} — {selectedStocks.length} stocks</p>
            <Badge
              variant="outline"
              className="cursor-pointer font-normal"
              onClick={() => setSelectedSector(null)}
            >
              Close
            </Badge>
          </div>
          <div className="max-h-[400px] overflow-auto rounded-md border border-border">
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-[1] border-b border-border bg-card">
                <tr>
                  <th className="px-2 py-2 text-left font-medium">Ticker</th>
                  <th className="px-2 py-2 text-right font-medium">Price</th>
                  <th className="px-2 py-2 text-left font-medium">Stage</th>
                  <th className="px-2 py-2 text-right font-medium">1D</th>
                  <th className="px-2 py-2 text-right font-medium">20D</th>
                  <th className="px-2 py-2 text-right font-medium">RS</th>
                  <th className="px-2 py-2 text-right font-medium">Ext150%</th>
                  <th className="px-2 py-2 text-right font-medium">ATR%</th>
                </tr>
              </thead>
              <tbody>
                {selectedStocks.map((s: any) => (
                  <tr
                    key={s.symbol}
                    className="border-b border-border/80 transition-colors last:border-0 hover:bg-[rgb(var(--bg-hover))]"
                  >
                    <td className="px-2 py-2"><SymbolLink symbol={s.symbol} /></td>
                    <td className={cn('px-2 py-2 text-right', DATA_CELL)}>{s.current_price?.toFixed(2) ?? '—'}</td>
                    <td className="px-2 py-2"><StageBadge stage={s.stage_label || '—'} /></td>
                    <td className={cn('px-2 py-2 text-right', DATA_CELL, heatTextClass(s.perf_1d))}>{fmtPct(s.perf_1d)}</td>
                    <td className={cn('px-2 py-2 text-right', DATA_CELL, heatTextClass(s.perf_20d))}>{fmtPct(s.perf_20d)}</td>
                    <td className={cn('px-2 py-2 text-right', DATA_CELL, heatTextClass(s.rs_mansfield_pct))}>{fmtPct(s.rs_mansfield_pct)}</td>
                    <td className={cn('px-2 py-2 text-right', DATA_CELL, heatTextClass(s.ext_pct))}>{fmtPct(s.ext_pct)}</td>
                    <td className={cn('px-2 py-2 text-right', DATA_CELL)}>{s.atrp_14?.toFixed(1) ?? '—'}%</td>
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

export default SectorView;
