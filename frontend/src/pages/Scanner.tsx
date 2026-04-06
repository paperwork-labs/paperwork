import React, { useState, useMemo, useCallback } from 'react';
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Filter,
  Search,
  TrendingUp,
} from 'lucide-react';

import { useMarketSnapshots, type MarketSnapshotRow } from '../hooks/useMarketSnapshots';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import ErrorBoundary from '@/components/ErrorBoundary';

const STAGE_FILTERS = [
  { label: 'All', value: '' },
  { label: '2A', value: '2A' },
  { label: '2B', value: '2B' },
  { label: '2C', value: '2C' },
  { label: '3A', value: '3A' },
];

const STAGE_COLORS: Record<string, string> = {
  '1A': 'bg-slate-600',
  '1B': 'bg-slate-500',
  '2A': 'bg-emerald-600',
  '2B': 'bg-emerald-500',
  '2C': 'bg-emerald-400',
  '3A': 'bg-amber-500',
  '3B': 'bg-amber-600',
  '4A': 'bg-red-500',
  '4B': 'bg-red-600',
  '4C': 'bg-red-700',
};

type SortKey = 'rs_mansfield_pct' | 'vol_ratio' | 'perf_20d' | 'atrp_14' | 'current_stage_days' | 'symbol';
type SortDir = 'asc' | 'desc';

interface SortHeaderProps {
  label: string;
  field: SortKey;
  className?: string;
  sortKey: SortKey;
  sortDir: SortDir;
  onToggleSort: (key: SortKey) => void;
}

const SortHeader: React.FC<SortHeaderProps> = ({
  label,
  field,
  className,
  sortKey,
  sortDir,
  onToggleSort,
}) => {
  const active = sortKey === field;
  const Icon = active ? (sortDir === 'desc' ? ArrowDown : ArrowUp) : ArrowUpDown;
  return (
    <button
      type="button"
      className={cn(
        'flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors',
        active && 'text-foreground',
        className,
      )}
      onClick={() => onToggleSort(field)}
    >
      {label}
      <Icon className="size-3" />
    </button>
  );
};

const fmt = (v: number | undefined, decimals = 1): string =>
  v != null ? v.toFixed(decimals) : '—';

const pctCell = (v: number | undefined): React.ReactNode => {
  if (v == null) return <span className="text-muted-foreground">—</span>;
  const color = v > 0 ? 'text-emerald-500' : v < 0 ? 'text-red-400' : 'text-muted-foreground';
  return <span className={color}>{v > 0 ? '+' : ''}{v.toFixed(1)}%</span>;
};

const Scanner: React.FC = () => {
  const [search, setSearch] = useState('');
  const [stageFilter, setStageFilter] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('rs_mansfield_pct');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [volConfirmOnly, setVolConfirmOnly] = useState(false);

  const { data, isPending, isError, error } = useMarketSnapshots();
  const rows: MarketSnapshotRow[] = data ?? [];

  const toggleSort = useCallback(
    (key: SortKey) => {
      if (sortKey === key) {
        setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'));
      } else {
        setSortKey(key);
        setSortDir('desc');
      }
    },
    [sortKey],
  );

  const filtered = useMemo(() => {
    let out = rows;

    if (stageFilter) {
      out = out.filter((r) => r.stage_label === stageFilter);
    }

    if (volConfirmOnly) {
      out = out.filter((r) => (r.vol_ratio ?? 0) >= 1.0);
    }

    if (search) {
      const q = search.toUpperCase();
      out = out.filter(
        (r) =>
          r.symbol?.toUpperCase().includes(q) ||
          r.name?.toUpperCase().includes(q) ||
          r.sector?.toUpperCase().includes(q),
      );
    }

    out = [...out].sort((a, b) => {
      const av = a[sortKey] ?? -Infinity;
      const bv = b[sortKey] ?? -Infinity;
      if (typeof av === 'string' && typeof bv === 'string') {
        return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      return sortDir === 'asc' ? Number(av) - Number(bv) : Number(bv) - Number(av);
    });

    return out;
  }, [rows, stageFilter, volConfirmOnly, search, sortKey, sortDir]);

  if (isError) {
    return (
      <div className="p-6 text-center text-destructive">
        Failed to load scanner data.{' '}
        {error instanceof Error ? error.message : String(error)}
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-[1100px] flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500/10">
            <TrendingUp className="size-5 text-emerald-500" />
          </div>
          <div>
            <h1 className="font-heading text-lg font-semibold tracking-tight text-foreground">
              Scanner
            </h1>
            <p className="text-xs text-muted-foreground">
              Stage 2 breakout candidates ranked by relative strength
            </p>
          </div>
        </div>
        <Badge variant="outline" className="font-mono text-xs">
          {filtered.length} results
        </Badge>
      </div>

      <Card>
        <CardContent className="flex flex-wrap items-center gap-3 pt-5">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search symbol, name, or sector..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-8 pl-8 text-xs"
            />
          </div>

          <div className="flex items-center gap-1">
            <Filter className="size-3.5 text-muted-foreground" />
            {STAGE_FILTERS.map((f) => (
              <Button
                key={f.value}
                type="button"
                size="xs"
                variant={stageFilter === f.value ? 'default' : 'ghost'}
                onClick={() => setStageFilter(f.value)}
                className="text-xs"
              >
                {f.label}
              </Button>
            ))}
          </div>

          <Button
            type="button"
            size="xs"
            variant={volConfirmOnly ? 'default' : 'ghost'}
            onClick={() => setVolConfirmOnly(!volConfirmOnly)}
            className="text-xs"
          >
            Vol &ge; 1.0
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="overflow-x-auto p-0">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                <th className="px-3 py-2.5 text-left">
                  <SortHeader
                    label="Symbol"
                    field="symbol"
                    sortKey={sortKey}
                    sortDir={sortDir}
                    onToggleSort={toggleSort}
                  />
                </th>
                <th className="px-3 py-2.5 text-left">Stage</th>
                <th className="px-3 py-2.5 text-right">
                  <SortHeader
                    label="RS Mansfield"
                    field="rs_mansfield_pct"
                    className="justify-end"
                    sortKey={sortKey}
                    sortDir={sortDir}
                    onToggleSort={toggleSort}
                  />
                </th>
                <th className="px-3 py-2.5 text-right">
                  <SortHeader
                    label="Vol Ratio"
                    field="vol_ratio"
                    className="justify-end"
                    sortKey={sortKey}
                    sortDir={sortDir}
                    onToggleSort={toggleSort}
                  />
                </th>
                <th className="px-3 py-2.5 text-right">
                  <SortHeader
                    label="20d %"
                    field="perf_20d"
                    className="justify-end"
                    sortKey={sortKey}
                    sortDir={sortDir}
                    onToggleSort={toggleSort}
                  />
                </th>
                <th className="px-3 py-2.5 text-right">
                  <SortHeader
                    label="ATR%"
                    field="atrp_14"
                    className="justify-end"
                    sortKey={sortKey}
                    sortDir={sortDir}
                    onToggleSort={toggleSort}
                  />
                </th>
                <th className="px-3 py-2.5 text-right">
                  <SortHeader
                    label="Days"
                    field="current_stage_days"
                    className="justify-end"
                    sortKey={sortKey}
                    sortDir={sortDir}
                    onToggleSort={toggleSort}
                  />
                </th>
                <th className="px-3 py-2.5 text-right">Price</th>
                <th className="px-3 py-2.5 text-left">Sector</th>
                <th className="px-3 py-2.5 text-left">Scan Tier</th>
              </tr>
            </thead>
            <tbody>
              <ErrorBoundary
                fallback={(
                  <tr>
                    <td colSpan={10} className="px-3 py-4 text-center text-sm text-muted-foreground">
                      Something went wrong in this section. Try refreshing the page.
                    </td>
                  </tr>
                )}
                onError={(error, info) => {
                  console.error('ErrorBoundary [scanner-table]:', error, info);
                }}
              >
                {isPending
                  ? Array.from({ length: 12 }).map((_, i) => (
                      <tr key={i} className="border-b border-border/50">
                        {Array.from({ length: 10 }).map((_, j) => (
                          <td key={j} className="px-3 py-2">
                            <Skeleton className="h-4 w-full" />
                          </td>
                        ))}
                      </tr>
                    ))
                  : filtered.map((row) => (
                      <tr
                        key={row.symbol}
                        className="border-b border-border/50 transition-colors hover:bg-muted/60"
                      >
                        <td className="px-3 py-2">
                          <div>
                            <span className="font-medium text-foreground">{row.symbol}</span>
                            {row.name && (
                              <span className="ml-1.5 text-muted-foreground truncate max-w-[120px] inline-block align-bottom">
                                {row.name}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-3 py-2">
                          {row.stage_label ? (
                            <Badge
                              className={cn(
                                'border-0 text-white text-[10px] px-1.5 py-0',
                                STAGE_COLORS[row.stage_label] || 'bg-slate-500',
                              )}
                            >
                              {row.stage_label}
                            </Badge>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td className="px-3 py-2 text-right font-mono">
                          {pctCell(row.rs_mansfield_pct)}
                        </td>
                        <td className="px-3 py-2 text-right font-mono">
                          <span
                            className={
                              (row.vol_ratio ?? 0) >= 1.0
                                ? 'text-emerald-500'
                                : 'text-muted-foreground'
                            }
                          >
                            {fmt(row.vol_ratio)}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-right font-mono">
                          {pctCell(row.perf_20d)}
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-muted-foreground">
                          {fmt(row.atrp_14)}
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-muted-foreground">
                          {row.current_stage_days ?? '—'}
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-foreground">
                          ${fmt(row.current_price, 2)}
                        </td>
                        <td className="px-3 py-2 text-muted-foreground truncate max-w-[100px]">
                          {row.sector || '—'}
                        </td>
                        <td className="px-3 py-2">
                          {row.scan_tier ? (
                            <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                              {row.scan_tier}
                            </Badge>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
              </ErrorBoundary>
            </tbody>
          </table>
          {!isPending && filtered.length === 0 && (
            <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
              No candidates match the current filters.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default Scanner;
