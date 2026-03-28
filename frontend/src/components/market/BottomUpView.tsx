import React from 'react';
import { Search } from 'lucide-react';
import StageBadge from '../shared/StageBadge';
import StageBar from '../shared/StageBar';
import { SymbolLink } from './SymbolChartUI';
import { ACTION_COLORS } from '../../constants/chart';
import { cn } from '@/lib/utils';
import { heatTextClass, semanticTextColorClass } from '@/lib/semantic-text-color';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';

const DATA_CELL = 'font-mono text-xs tracking-tight';

const fmtPct = (v: unknown): string => {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—';
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
};

type SortKey = 'symbol' | 'stage_label' | 'action_label' | 'perf_1d' | 'perf_5d' | 'perf_20d' | 'perf_252d' | 'rsi' | 'ext_pct' | 'atrp_14' | 'rs_mansfield_pct' | 'ema10_dist_n' | 'sma150_slope' | 'scan_tier';

interface BottomUpViewProps {
  snapshots: any[];
}

function colorToBadgeClass(active: boolean, palette: string): string {
  const subtle = (border: string, bgOn: string, bgOff: string, textOff: string) =>
    cn(
      'cursor-pointer border font-normal transition-opacity hover:opacity-85',
      active ? cn('text-white', border, bgOn) : cn(border, bgOff, textOff)
    );
  switch (palette) {
    case 'green':
      return subtle(
        'border-emerald-500/50',
        'bg-emerald-600',
        'bg-emerald-500/10',
        'text-emerald-800 dark:text-emerald-300'
      );
    case 'blue':
      return subtle(
        'border-blue-500/50',
        'bg-blue-600',
        'bg-blue-500/10',
        'text-blue-800 dark:text-blue-300'
      );
    case 'orange':
      return subtle(
        'border-orange-500/50',
        'bg-orange-600',
        'bg-orange-500/10',
        'text-orange-800 dark:text-orange-300'
      );
    case 'red':
      return subtle(
        'border-red-500/50',
        'bg-red-600',
        'bg-red-500/10',
        'text-red-800 dark:text-red-300'
      );
    default:
      return cn(
        'cursor-pointer border border-border font-normal transition-opacity hover:opacity-85',
        active ? 'bg-primary text-primary-foreground' : 'bg-muted/60 text-muted-foreground'
      );
  }
}

const BottomUpView: React.FC<BottomUpViewProps> = ({ snapshots }) => {
  const [search, setSearch] = React.useState('');
  const [sortKey, setSortKey] = React.useState<SortKey>('scan_tier');
  const [sortDir, setSortDir] = React.useState<'asc' | 'desc'>('asc');
  const [stageFilter, setStageFilter] = React.useState<string | null>(null);
  const [actionFilter, setActionFilter] = React.useState<string | null>(null);

  const handleSort = React.useCallback((key: SortKey) => {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir(key === 'symbol' ? 'asc' : 'desc');
    }
  }, [sortKey]);

  const stageCounts = React.useMemo(() => {
    const counts: Record<string, number> = {};
    snapshots.forEach((s: any) => {
      const stage = s.stage_label;
      if (stage) counts[stage] = (counts[stage] || 0) + 1;
    });
    return counts;
  }, [snapshots]);

  const actionCounts = React.useMemo(() => {
    const counts: Record<string, number> = {};
    snapshots.forEach((s: any) => {
      const action = s.action_label || s.scan_action || 'WATCH';
      counts[action] = (counts[action] || 0) + 1;
    });
    return counts;
  }, [snapshots]);

  const filteredRows = React.useMemo(() => {
    let rows = [...snapshots];
    if (search) {
      const q = search.toUpperCase();
      rows = rows.filter((r: any) =>
        r.symbol?.toUpperCase().includes(q) ||
        r.sector?.toUpperCase().includes(q) ||
        r.name?.toUpperCase().includes(q)
      );
    }
    if (stageFilter) {
      rows = rows.filter((r: any) => r.stage_label === stageFilter);
    }
    if (actionFilter) {
      rows = rows.filter((r: any) => (r.action_label || r.scan_action || 'WATCH') === actionFilter);
    }
    rows.sort((a: any, b: any) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      const cmp = typeof av === 'string' ? av.localeCompare(bv) : av - bv;
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return rows;
  }, [snapshots, search, sortKey, sortDir, stageFilter, actionFilter]);

  const SortHeader: React.FC<{ k: SortKey; label: string; align?: 'left' | 'right' }> = ({ k, label, align = 'left' }) => (
    <th
      className={cn(
        'cursor-pointer select-none px-2 py-2 font-medium transition-colors hover:bg-muted/80',
        align === 'right' ? 'text-right' : 'text-left'
      )}
      onClick={() => handleSort(k)}
    >
      <div className={cn('flex items-center gap-1', align === 'right' && 'justify-end')}>
        <span className="text-xs font-semibold">{label}</span>
        {sortKey === k && (
          <span className="text-xs text-emerald-600 dark:text-emerald-400">{sortDir === 'asc' ? '▲' : '▼'}</span>
        )}
      </div>
    </th>
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="mb-2 flex items-center justify-between">
          <p className="text-sm font-semibold">Stage Distribution</p>
          <p className="text-xs text-muted-foreground">{snapshots.length} symbols</p>
        </div>
        <StageBar counts={stageCounts} onClick={(stage: string) => setStageFilter(prev => prev === stage ? null : stage)} activeStage={stageFilter} />
      </div>

      <div className="flex flex-wrap gap-2">
        {Object.entries(actionCounts).sort(([a], [b]) => a.localeCompare(b)).map(([action, count]) => (
          <Badge
            key={action}
            variant="outline"
            className={colorToBadgeClass(actionFilter === action, ACTION_COLORS[action] || 'gray')}
            onClick={() => setActionFilter(prev => prev === action ? null : action)}
          >
            {action}: {count}
          </Badge>
        ))}
        {(stageFilter || actionFilter) && (
          <Badge
            variant="outline"
            className="cursor-pointer border-border transition-colors hover:bg-muted"
            onClick={() => { setStageFilter(null); setActionFilter(null); }}
          >
            Clear Filters
          </Badge>
        )}
      </div>

      <div className="flex items-center gap-2">
        <div className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input
            className="h-8 pl-8 text-sm"
            placeholder="Search symbol, sector, or name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <span className="shrink-0 text-xs text-muted-foreground">{filteredRows.length} results</span>
      </div>

      <div className="overflow-hidden rounded-lg border border-border bg-card">
        <div className="max-h-[70vh] overflow-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 z-[1] border-b border-border bg-card">
              <tr>
                <SortHeader k="symbol" label="Ticker" />
                <th className="px-2 py-2 text-left font-medium">Sector</th>
                <SortHeader k="stage_label" label="Stage" />
                <SortHeader k="action_label" label="Action" />
                <SortHeader k="scan_tier" label="Tier" />
                <SortHeader k="perf_1d" label="1D" align="right" />
                <SortHeader k="perf_5d" label="5D" align="right" />
                <SortHeader k="perf_20d" label="MTD" align="right" />
                <SortHeader k="perf_252d" label="YTD" align="right" />
                <SortHeader k="rsi" label="RSI" align="right" />
                <SortHeader k="ext_pct" label="Ext150%" align="right" />
                <SortHeader k="ema10_dist_n" label="EMA10d" align="right" />
                <SortHeader k="atrp_14" label="ATR%" align="right" />
                <SortHeader k="rs_mansfield_pct" label="RS" align="right" />
                <SortHeader k="sma150_slope" label="Slope" align="right" />
              </tr>
            </thead>
            <tbody>
              {filteredRows.slice(0, 500).map((row: any) => {
                const action = row.action_label || row.scan_action || '';
                return (
                  <tr
                    key={row.symbol}
                    className="border-b border-border/80 transition-colors last:border-0 hover:bg-[rgb(var(--bg-hover))]"
                  >
                    <td className="px-2 py-2">
                      <SymbolLink symbol={row.symbol} />
                    </td>
                    <td className="max-w-[100px] truncate px-2 py-2 text-xs text-muted-foreground">{row.sector || '—'}</td>
                    <td className="px-2 py-2"><StageBadge stage={row.stage_label || '—'} /></td>
                    <td className="px-2 py-2">
                      {action && (
                        <Badge
                          variant="outline"
                          className={cn('font-normal', colorToBadgeClass(false, ACTION_COLORS[action] || 'gray'))}
                        >
                          {action}
                        </Badge>
                      )}
                    </td>
                    <td className={cn('px-2 py-2', DATA_CELL)}>{row.scan_tier || '—'}</td>
                    <td className={cn('px-2 py-2 text-right', DATA_CELL, heatTextClass(row.perf_1d))}>{fmtPct(row.perf_1d)}</td>
                    <td className={cn('px-2 py-2 text-right', DATA_CELL, heatTextClass(row.perf_5d))}>{fmtPct(row.perf_5d)}</td>
                    <td className={cn('px-2 py-2 text-right', DATA_CELL, heatTextClass(row.perf_20d))}>{fmtPct(row.perf_20d)}</td>
                    <td className={cn('px-2 py-2 text-right', DATA_CELL, heatTextClass(row.perf_252d))}>{fmtPct(row.perf_252d)}</td>
                    <td className={cn(
                      'px-2 py-2 text-right',
                      DATA_CELL,
                      (row.rsi ?? 50) > 70 ? semanticTextColorClass('red.500') : (row.rsi ?? 50) < 30 ? semanticTextColorClass('green.500') : undefined
                    )}>{row.rsi?.toFixed(0) ?? '—'}</td>
                    <td className={cn('px-2 py-2 text-right', DATA_CELL, heatTextClass(row.ext_pct))}>{fmtPct(row.ext_pct)}</td>
                    <td className={cn('px-2 py-2 text-right', DATA_CELL)}>{row.ema10_dist_n?.toFixed(1) ?? '—'}</td>
                    <td className={cn('px-2 py-2 text-right', DATA_CELL)}>{row.atrp_14?.toFixed(1) ?? '—'}%</td>
                    <td className={cn('px-2 py-2 text-right', DATA_CELL, heatTextClass(row.rs_mansfield_pct))}>{fmtPct(row.rs_mansfield_pct)}</td>
                    <td className={cn('px-2 py-2 text-right', DATA_CELL, heatTextClass(row.sma150_slope))}>{row.sma150_slope?.toFixed(2) ?? '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default BottomUpView;
