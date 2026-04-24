/**
 * Terminal Dashboard - Multi-pane market intelligence view
 *
 * 4 interactive panes: Watchlist, Chart, Market Regime, Scanner
 */

import React, { useCallback, useState, useEffect, Suspense } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, TrendingUp, BarChart2, Activity, Zap, Loader2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Page } from '@/components/ui/Page';
import { cn } from '@/lib/utils';
import api, { marketDataApi, unwrapResponse } from '@/services/api';
import { useSnapshotTable } from '@/hooks/useSnapshotTable';
import StageBadge from '@/components/shared/StageBadge';
import { ChartContext, SymbolLink } from '@/components/market/SymbolChartUI';
import { ACTION_COLORS } from '@/constants/chart';
import type { MarketSnapshotRow } from '@/types/market';

const RegimeBanner = React.lazy(() => import('@/components/market/RegimeBanner'));
const SymbolChartWithMarkers = React.lazy(() => import('@/components/charts/SymbolChartWithMarkers'));

interface QuickStats {
  regime: string;
  regimeScore: number;
  spyChange: number;
  vix: number;
  breadthPct: number;
}

type PaneType = 'watchlist' | 'chart' | 'regime' | 'scanner';

interface Pane {
  id: string;
  type: PaneType;
  title: string;
  icon: React.ElementType;
}

const DEFAULT_LAYOUT: Pane[] = [
  { id: 'watchlist', type: 'watchlist', title: 'Watchlist', icon: Activity },
  { id: 'chart', type: 'chart', title: 'Chart', icon: TrendingUp },
  { id: 'regime', type: 'regime', title: 'Market Regime', icon: BarChart2 },
  { id: 'scanner', type: 'scanner', title: 'Scanner', icon: Zap },
];

type Bar = { time: string; open: number; high: number; low: number; close: number; volume?: number };

function actionBadgeClass(palette: string): string {
  switch (palette) {
    case 'green':
      return 'border-emerald-500/50 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300';
    case 'blue':
      return 'border-blue-500/50 bg-blue-500/10 text-blue-800 dark:text-blue-300';
    case 'orange':
      return 'border-orange-500/50 bg-orange-500/10 text-orange-800 dark:text-orange-300';
    case 'red':
      return 'border-red-500/50 bg-red-500/10 text-red-800 dark:text-red-300';
    default:
      return 'border-border bg-muted/60 text-muted-foreground';
  }
}

export function Terminal() {
  const [commandInput, setCommandInput] = useState('');
  const [selectedPane, setSelectedPane] = useState<string>('watchlist');
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [layout] = useState<Pane[]>(DEFAULT_LAYOUT);

  const selectSymbol = useCallback((symbol: string) => {
    setSelectedSymbol(symbol);
    setSelectedPane('chart');
  }, []);

  const { data: stats } = useQuery<QuickStats>({
    queryKey: ['terminal-stats'],
    queryFn: async () => {
      const [regime] = await Promise.all([
        api.get('/market-data/regime/current').catch(() => ({ data: {} })),
      ]);

      return {
        regime: regime.data?.regime_state || 'R3',
        regimeScore: regime.data?.composite_score || 50,
        spyChange: regime.data?.spy_change || 0,
        vix: regime.data?.vix || 0,
        breadthPct: regime.data?.breadth_pct || 50,
      };
    },
    refetchInterval: 30000,
    staleTime: 15000,
  });

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        document.getElementById('terminal-command')?.focus();
      }
      if (e.key >= '1' && e.key <= '4' && !e.metaKey && !e.ctrlKey && !e.altKey) {
        const idx = parseInt(e.key) - 1;
        if (layout[idx]) {
          setSelectedPane(layout[idx].id);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [layout]);

  const handleCommand = useCallback((cmd: string) => {
    const parts = cmd.trim().split(/\s+/);
    const command = parts[0].toLowerCase();

    switch (command) {
      case 'scan':
        setSelectedPane('scanner');
        break;
      case 'chart': {
        const sym = parts[1];
        if (sym && /^[A-Za-z]{1,5}$/.test(sym)) {
          setSelectedSymbol(sym.toUpperCase());
        }
        setSelectedPane('chart');
        break;
      }
      case 'regime':
        setSelectedPane('regime');
        break;
      default:
        if (/^[A-Za-z]{1,5}$/.test(command)) {
          setSelectedSymbol(command.toUpperCase());
          setSelectedPane('chart');
        }
    }
    setCommandInput('');
  }, []);

  const renderPane = (pane: Pane) => {
    const isSelected = selectedPane === pane.id;
    const Icon = pane.icon;

    return (
      <Card
        key={pane.id}
        className={cn(
          "flex flex-col h-full transition-colors cursor-pointer",
          isSelected
            ? "ring-2 ring-primary ring-offset-2 ring-offset-background"
            : "hover:border-muted-foreground/50"
        )}
        onClick={() => setSelectedPane(pane.id)}
      >
        <CardHeader className="py-2 px-3 border-b flex-none">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Icon className="w-4 h-4 text-muted-foreground" />
              <CardTitle className="text-sm font-medium">
                {pane.title}
                {pane.type === 'chart' && selectedSymbol && (
                  <span className="ml-1.5 text-muted-foreground font-normal">
                    — {selectedSymbol}
                  </span>
                )}
              </CardTitle>
            </div>
            <Badge variant={isSelected ? "default" : "secondary"} className="text-xs h-5">
              {layout.indexOf(pane) + 1}
            </Badge>
          </div>
        </CardHeader>

        <CardContent className="p-3 flex-1 min-h-0 overflow-auto">
          {pane.type === 'watchlist' && (
            <WatchlistPane selectedSymbol={selectedSymbol} onSelectSymbol={selectSymbol} />
          )}
          {pane.type === 'chart' && <ChartPane symbol={selectedSymbol} />}
          {pane.type === 'regime' && <RegimePane />}
          {pane.type === 'scanner' && (
            <ScannerPane selectedSymbol={selectedSymbol} onSelectSymbol={selectSymbol} />
          )}
        </CardContent>
      </Card>
    );
  };

  const regimeColor = (regime: string) => {
    switch (regime) {
      case 'R1': return 'bg-emerald-500';
      case 'R2': return 'bg-emerald-600';
      case 'R3': return 'bg-amber-500';
      case 'R4': return 'bg-orange-500';
      case 'R5': return 'bg-red-500';
      default: return 'bg-muted';
    }
  };

  return (
    <ChartContext.Provider value={selectSymbol}>
      <Page fullWidth className="flex flex-col h-[calc(100vh-4rem)]">
        {/* Header Row */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <h1 className="font-heading text-2xl font-semibold tracking-tight">Terminal</h1>
            <p className="text-sm text-muted-foreground">Multi-pane market intelligence</p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Quick Stats */}
            <div className="flex items-center gap-3 text-sm">
              <div className="flex items-center gap-1.5">
                <span className="text-muted-foreground text-xs">Regime</span>
                <Badge className={cn("text-xs h-5", regimeColor(stats?.regime || 'R3'))}>
                  {stats?.regime || 'R3'}
                </Badge>
              </div>

              <div className="flex items-center gap-1">
                <span className="text-muted-foreground text-xs">VIX</span>
                <span className={cn(
                  "text-xs font-medium",
                  stats?.vix != null && stats.vix > 25 ? "text-destructive" : "text-foreground"
                )}>
                  {stats?.vix != null ? stats.vix.toFixed(1) : '--'}
                </span>
              </div>

              <div className="flex items-center gap-1">
                <span className="text-muted-foreground text-xs">SPY</span>
                <span className={cn(
                  "text-xs font-medium",
                  stats?.spyChange != null && stats.spyChange >= 0 ? "text-emerald-600" : "text-destructive"
                )}>
                  {stats?.spyChange != null ? `${stats.spyChange >= 0 ? '+' : ''}${stats.spyChange.toFixed(2)}%` : '--'}
                </span>
              </div>
            </div>

            {/* Command Input */}
            <div className="relative w-full sm:w-48">
              <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
              <Input
                id="terminal-command"
                placeholder="⌘K symbol..."
                className="pl-7 h-8 text-sm"
                value={commandInput}
                onChange={(e) => setCommandInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleCommand(commandInput);
                  }
                }}
              />
            </div>
          </div>
        </div>

        {/* 2x2 Grid - fills remaining height */}
        <div className="grid grid-cols-1 md:grid-cols-2 grid-rows-2 gap-3 flex-1 min-h-0">
          {layout.map((pane) => (
            <div key={pane.id} className="min-h-0">
              {renderPane(pane)}
            </div>
          ))}
        </div>
      </Page>
    </ChartContext.Provider>
  );
}

// --- Shared helpers ---

function LoadingSkeleton() {
  return (
    <div className="space-y-2 p-1">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="h-7 rounded bg-muted animate-pulse" />
      ))}
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center h-full text-muted-foreground">
      <p className="text-sm">{message}</p>
    </div>
  );
}

function ActionBadge({ label }: { label: string }) {
  const palette = ACTION_COLORS[label] || 'gray';
  return (
    <Badge
      variant="outline"
      className={cn("w-14 justify-center text-[10px] h-5 font-normal", actionBadgeClass(palette))}
    >
      {label}
    </Badge>
  );
}

// --- Pane Components ---

interface ListPaneProps {
  selectedSymbol: string | null;
  onSelectSymbol: (symbol: string) => void;
}

function WatchlistPane({ selectedSymbol, onSelectSymbol }: ListPaneProps) {
  const { data, isLoading } = useSnapshotTable({
    limit: 20,
    sort_by: 'perf_1d',
    sort_dir: 'desc',
    include_plan: true,
  });
  const rows = data?.rows ?? [];

  if (isLoading) return <LoadingSkeleton />;
  if (!rows.length) return <EmptyState message="No watchlist data" />;

  return (
    <div className="space-y-0.5">
      <div className="flex items-center justify-between text-[10px] text-muted-foreground px-2 pb-1.5 border-b uppercase tracking-wide">
        <span>Symbol</span>
        <div className="flex items-center gap-3">
          <span className="w-16 text-right">Price</span>
          <span className="w-14 text-right">Chg%</span>
          <span className="w-10 text-center">Stage</span>
          <span className="w-14 text-center">Action</span>
        </div>
      </div>

      {rows.map((row: MarketSnapshotRow) => (
        <div
          key={row.symbol}
          className={cn(
            "flex items-center justify-between px-2 py-1.5 rounded hover:bg-muted cursor-pointer transition-colors text-sm",
            selectedSymbol === row.symbol && "bg-muted"
          )}
          onClick={() => onSelectSymbol(row.symbol)}
        >
          <SymbolLink symbol={row.symbol} showHeldBadge={false} />
          <div className="flex items-center gap-3">
            <span className="w-16 text-right text-muted-foreground tabular-nums">
              {row.current_price != null ? `$${row.current_price.toFixed(2)}` : '--'}
            </span>
            <span className={cn(
              "w-14 text-right font-medium tabular-nums",
              (row.perf_1d ?? 0) >= 0 ? "text-emerald-600" : "text-destructive"
            )}>
              {row.perf_1d != null
                ? `${row.perf_1d >= 0 ? '+' : ''}${row.perf_1d.toFixed(1)}%`
                : '--'}
            </span>
            <div className="w-10 flex justify-center">
              <StageBadge stage={row.stage_label ?? '?'} />
            </div>
            <div className="w-14 flex justify-center">
              {row.action_label ? <ActionBadge label={row.action_label} /> : null}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function ChartPane({ symbol }: { symbol: string | null }) {
  const { data: bars = [], isLoading, isError } = useQuery<Bar[]>({
    queryKey: ['terminal-chart-bars', symbol],
    queryFn: async () => {
      if (!symbol) return [];
      const res = await marketDataApi.getHistory(symbol, '1y', '1d');
      return unwrapResponse<Bar>(res, 'bars');
    },
    enabled: !!symbol,
    staleTime: 300_000,
  });

  if (!symbol) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
        <TrendingUp className="w-10 h-10 mb-2 opacity-30" />
        <p className="text-sm">Select a symbol to view chart</p>
        <p className="text-xs">Type symbol in command bar</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full gap-2 text-muted-foreground">
        <Loader2 className="w-4 h-4 animate-spin" />
        <span className="text-sm">Loading {symbol}…</span>
      </div>
    );
  }

  if (isError || bars.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
        <TrendingUp className="w-10 h-10 mb-2 opacity-30" />
        <p className="text-sm">No chart data for {symbol}</p>
      </div>
    );
  }

  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center h-full">
          <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <SymbolChartWithMarkers bars={bars} events={[]} symbol={symbol} />
    </Suspense>
  );
}

function RegimePane() {
  return (
    <Suspense fallback={<div className="animate-pulse text-muted-foreground text-sm">Loading...</div>}>
      <RegimeBanner />
    </Suspense>
  );
}

function ScannerPane({ selectedSymbol, onSelectSymbol }: ListPaneProps) {
  const { data, isLoading } = useSnapshotTable({
    limit: 15,
    action_labels: 'BUY,WATCH',
    sort_by: 'rs_mansfield_pct',
    sort_dir: 'desc',
  });
  const rows = data?.rows ?? [];

  if (isLoading) return <LoadingSkeleton />;
  if (!rows.length) return <EmptyState message="No scan results" />;

  return (
    <div className="space-y-0.5">
      <div className="flex items-center justify-between text-[10px] text-muted-foreground px-2 pb-1.5 border-b uppercase tracking-wide">
        <span>Symbol</span>
        <div className="flex items-center gap-3">
          <span className="w-10 text-center">Stage</span>
          <span className="w-8 text-right">RS</span>
          <span className="w-10 text-center">Tier</span>
          <span className="w-14 text-center">Action</span>
        </div>
      </div>

      {rows.map((row: MarketSnapshotRow) => (
        <div
          key={row.symbol}
          className={cn(
            "flex items-center justify-between px-2 py-1.5 rounded hover:bg-muted cursor-pointer transition-colors text-sm",
            selectedSymbol === row.symbol && "bg-muted"
          )}
          onClick={() => onSelectSymbol(row.symbol)}
        >
          <SymbolLink symbol={row.symbol} showHeldBadge={false} />
          <div className="flex items-center gap-3">
            <div className="w-10 flex justify-center">
              <StageBadge stage={row.stage_label ?? '?'} />
            </div>
            <span className="w-8 text-right text-muted-foreground tabular-nums">
              {row.rs_mansfield_pct != null ? Math.round(row.rs_mansfield_pct) : '--'}
            </span>
            <span className="w-10 text-center text-xs text-muted-foreground">
              {row.scan_tier ?? '--'}
            </span>
            <div className="w-14 flex justify-center">
              {row.action_label ? <ActionBadge label={row.action_label} /> : null}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default Terminal;
