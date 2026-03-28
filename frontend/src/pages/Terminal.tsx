/**
 * Terminal Dashboard - Multi-pane market intelligence view
 * 
 * 4 interactive panes: Watchlist, Chart, Market Regime, Scanner
 */

import React, { useCallback, useState, useEffect, Suspense } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, TrendingUp, BarChart2, Activity, Zap } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Page } from '@/components/ui/Page';
import { cn } from '@/lib/utils';
import api from '@/services/api';

// Lazy load RegimeBanner (note: CircuitBreakerBanner uses Chakra which conflicts with Tailwind)
const RegimeBanner = React.lazy(() => import('@/components/market/RegimeBanner'));

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

export function Terminal() {
  const [commandInput, setCommandInput] = useState('');
  const [selectedPane, setSelectedPane] = useState<string>('watchlist');
  const [layout] = useState<Pane[]>(DEFAULT_LAYOUT);

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
    const parts = cmd.toLowerCase().trim().split(' ');
    const command = parts[0];

    switch (command) {
      case 'scan':
        setSelectedPane('scanner');
        break;
      case 'chart':
        setSelectedPane('chart');
        break;
      case 'regime':
        setSelectedPane('regime');
        break;
      default:
        if (/^[A-Za-z]{1,5}$/.test(command)) {
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
              </CardTitle>
            </div>
            <Badge variant={isSelected ? "default" : "secondary"} className="text-xs h-5">
              {layout.indexOf(pane) + 1}
            </Badge>
          </div>
        </CardHeader>
        
        <CardContent className="p-3 flex-1 min-h-0 overflow-auto">
          {pane.type === 'watchlist' && <WatchlistPane />}
          {pane.type === 'chart' && <ChartPane />}
          {pane.type === 'regime' && <RegimePane />}
          {pane.type === 'scanner' && <ScannerPane />}
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
  );
}

// --- Pane Components ---

function WatchlistPane() {
  // Demo data - watchlist API endpoint not yet implemented
  const items = [
    { symbol: 'AAPL', price: 185.50, change: 1.2 },
    { symbol: 'MSFT', price: 415.20, change: -0.5 },
    { symbol: 'NVDA', price: 875.00, change: 2.8 },
    { symbol: 'GOOGL', price: 142.30, change: 0.3 },
    { symbol: 'AMZN', price: 178.25, change: 0.8 },
    { symbol: 'META', price: 505.10, change: 1.5 },
  ];

  return (
    <div className="space-y-0.5">
      {items.slice(0, 8).map((item: { symbol: string; price: number; change: number }) => (
        <div
          key={item.symbol}
          className="flex items-center justify-between px-2 py-1.5 rounded hover:bg-muted cursor-pointer transition-colors text-sm"
        >
          <span className="font-medium">{item.symbol}</span>
          <div className="flex items-center gap-3">
            <span className="text-muted-foreground">${item.price?.toFixed(2)}</span>
            <span className={cn(
              "font-medium tabular-nums",
              item.change >= 0 ? "text-emerald-600" : "text-destructive"
            )}>
              {item.change >= 0 ? '+' : ''}{item.change?.toFixed(1)}%
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

function ChartPane() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
      <TrendingUp className="w-10 h-10 mb-2 opacity-30" />
      <p className="text-sm">Select a symbol to view chart</p>
      <p className="text-xs">Type symbol in command bar</p>
    </div>
  );
}

function RegimePane() {
  return (
    <Suspense fallback={<div className="animate-pulse text-muted-foreground text-sm">Loading...</div>}>
      <RegimeBanner />
    </Suspense>
  );
}

function ScannerPane() {
  // Demo data - scan API endpoint not yet implemented
  const items = [
    { symbol: 'PLTR', stage: '2A', rs: 85, action: 'BUY' },
    { symbol: 'ARM', stage: '2B', rs: 78, action: 'WATCH' },
    { symbol: 'SMCI', stage: '2A', rs: 92, action: 'BUY' },
    { symbol: 'CRWD', stage: '2A', rs: 88, action: 'BUY' },
    { symbol: 'ANET', stage: '2B', rs: 75, action: 'WATCH' },
  ];

  return (
    <div className="space-y-0.5">
      <div className="flex items-center justify-between text-[10px] text-muted-foreground px-2 pb-1.5 border-b uppercase tracking-wide">
        <span>Symbol</span>
        <div className="flex items-center gap-3">
          <span className="w-10 text-center">Stage</span>
          <span className="w-6 text-right">RS</span>
          <span className="w-14 text-center">Action</span>
        </div>
      </div>
      
      {items.slice(0, 6).map((item: { symbol: string; stage: string; rs: number; action: string }) => (
        <div
          key={item.symbol}
          className="flex items-center justify-between px-2 py-1.5 rounded hover:bg-muted cursor-pointer transition-colors text-sm"
        >
          <span className="font-medium">{item.symbol}</span>
          <div className="flex items-center gap-3">
            <Badge 
              variant="secondary"
              className={cn(
                "w-10 justify-center text-[10px] h-5",
                item.stage?.startsWith('2') && "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300"
              )}
            >
              {item.stage}
            </Badge>
            <span className="w-6 text-right text-muted-foreground tabular-nums">{item.rs}</span>
            <Badge
              className={cn(
                "w-14 justify-center text-[10px] h-5",
                item.action === 'BUY' && "bg-emerald-500",
                item.action === 'WATCH' && "bg-amber-500",
                item.action === 'SELL' && "bg-destructive",
              )}
            >
              {item.action}
            </Badge>
          </div>
        </div>
      ))}
    </div>
  );
}

export default Terminal;
