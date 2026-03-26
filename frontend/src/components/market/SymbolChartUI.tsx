/**
 * Shared symbol chart UI: clickable symbol links that open a TradingView chart slide panel.
 * Used by Market Dashboard and Market Tracked pages.
 * Optimized: memoized components, stable callbacks, lazy-loaded chart.
 */
import React, { useCallback, useMemo, memo, useState } from 'react';
import * as Dialog from "@radix-ui/react-dialog";
import * as Popover from "@radix-ui/react-popover";
import { Loader2, X } from 'lucide-react';
import { marketDataApi } from '../../services/api';
import TradeModal from '../orders/TradeModal';
import { cn } from '@/lib/utils';
import { semanticTextColorClass } from '@/lib/semantic-text-color';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

export const PortfolioSymbolsContext = React.createContext<Record<string, any> | null>(null);

export const ChartContext = React.createContext<(symbol: string) => void>(() => {});

const sparklineCache = new Map<string, number[]>();
const sparklineInflight = new Map<string, Promise<number[]>>();

function fetchSparkline(symbol: string): Promise<number[]> {
  if (sparklineCache.has(symbol)) return Promise.resolve(sparklineCache.get(symbol)!);
  const existing = sparklineInflight.get(symbol);
  if (existing) return existing;
  const p = (async () => {
    try {
      const res = await marketDataApi.getHistory(symbol, '1mo', '1d');
      const bars: any[] = (res as any)?.bars || (res as any)?.data || [];
      const closes = bars.map((b: any) => b.close).filter((v: any) => typeof v === 'number');
      sparklineCache.set(symbol, closes);
      return closes;
    } catch {
      sparklineCache.set(symbol, []);
      return [] as number[];
    } finally {
      sparklineInflight.delete(symbol);
    }
  })();
  sparklineInflight.set(symbol, p);
  return p;
}

const SVG_W = 140;
const SVG_H = 32;

const SparklinePopoverContentInner: React.FC<{ symbol: string }> = ({ symbol }) => {
  const [values, setValues] = React.useState<number[] | null>(sparklineCache.get(symbol) ?? null);
  const [loading, setLoading] = React.useState(!sparklineCache.has(symbol));

  React.useEffect(() => {
    if (sparklineCache.has(symbol)) {
      setValues(sparklineCache.get(symbol)!);
      setLoading(false);
      return;
    }
    let cancelled = false;
    fetchSparkline(symbol).then((closes) => {
      if (!cancelled) {
        setValues(closes);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  const last = values?.length ? values[values.length - 1] : null;
  const prev = values && values.length > 1 ? values[values.length - 2] : null;
  const change = last != null && prev != null && prev !== 0 ? ((last - prev) / prev) * 100 : null;
  const lineColor =
    change != null
      ? change >= 0
        ? 'rgb(var(--status-success) / 1)'
        : 'rgb(var(--status-danger) / 1)'
      : 'rgb(var(--chart-neutral) / 1)';
  const pts = values?.slice(-20) || [];

  const pathD = useMemo(() => {
    if (pts.length < 2) return '';
    const min = Math.min(...pts);
    const max = Math.max(...pts);
    const range = max - min || 1;
    return pts
      .map((v, i) => {
        const x = (i / (pts.length - 1)) * SVG_W;
        const y = SVG_H - ((v - min) / range) * (SVG_H - 4) - 2;
        return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');
  }, [pts]);

  return (
    <div className="min-w-[160px] p-2">
      <div className="mb-px flex items-center justify-between">
        <span className="text-xs font-semibold">{symbol}</span>
        {last != null && change != null && (
          <span
            className={cn(
              'text-[10px] font-medium',
              change >= 0 ? semanticTextColorClass('green.500') : semanticTextColorClass('red.500')
            )}
          >
            {change >= 0 ? '+' : ''}{change.toFixed(1)}%
          </span>
        )}
      </div>
      {loading ? (
        <div className="flex items-center gap-1">
          <Loader2 className="size-3.5 animate-spin text-muted-foreground" aria-hidden />
          <span className="text-xs text-muted-foreground">Loading...</span>
        </div>
      ) : pts.length >= 2 ? (
        <>
          <svg width={SVG_W} height={SVG_H} className="block">
            <path d={pathD} fill="none" stroke={lineColor} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          {last != null && (
            <span className="mt-px text-[10px] text-muted-foreground">${last.toFixed(2)}</span>
          )}
        </>
      ) : (
        <span className="text-xs text-muted-foreground">No data available</span>
      )}
    </div>
  );
};

const SparklinePopoverContent = memo(SparklinePopoverContentInner);

const SymbolLinkInner: React.FC<{ symbol: string; children?: React.ReactNode; showHeldBadge?: boolean }> = ({ symbol, children, showHeldBadge = true }) => {
  const openChart = React.useContext(ChartContext);
  const portfolioSymbols = React.useContext(PortfolioSymbolsContext);
  const isHeld = showHeldBadge && portfolioSymbols != null && symbol in (portfolioSymbols || {});
  const [hovered, setHovered] = React.useState(false);
  const hoverTimer = React.useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const onEnter = useCallback(() => {
    clearTimeout(hoverTimer.current);
    hoverTimer.current = setTimeout(() => setHovered(true), 250);
  }, []);
  const onLeave = useCallback(() => {
    clearTimeout(hoverTimer.current);
    hoverTimer.current = setTimeout(() => setHovered(false), 150);
  }, []);

  React.useEffect(() => () => clearTimeout(hoverTimer.current), []);

  const openAndClose = useCallback(() => {
    setHovered(false);
    openChart(symbol);
  }, [symbol, openChart]);

  const keepOpen = useCallback(() => clearTimeout(hoverTimer.current), []);

  const handleClick = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    openAndClose();
  }, [openAndClose]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      e.stopPropagation();
      openAndClose();
    }
  }, [openAndClose]);

  return (
    <Popover.Root open={hovered} onOpenChange={setHovered} modal={false}>
      <Popover.Trigger asChild>
        <span
          role="button"
          tabIndex={0}
          className="cursor-pointer font-medium hover:text-primary hover:underline"
          onMouseEnter={onEnter}
          onMouseLeave={onLeave}
          onClick={handleClick}
          onKeyDown={handleKeyDown}
        >
          {children ?? symbol}
          {isHeld && (
            <Badge variant="secondary" className="ml-1 h-4 px-1 py-0 text-[10px] font-normal">
              Held
            </Badge>
          )}
        </span>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          side="top"
          align="center"
          sideOffset={6}
          className="z-50 w-auto rounded-lg border border-border bg-popover text-popover-foreground shadow-lg outline-none"
          onOpenAutoFocus={(e) => e.preventDefault()}
          onMouseEnter={keepOpen}
          onMouseLeave={onLeave}
        >
          <SparklinePopoverContent symbol={symbol} />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
};

export const SymbolLink = memo(SymbolLinkInner);

const TradingViewChartLazy = React.lazy(() => import('../charts/TradingViewChart'));

const SnapshotContextStrip: React.FC<{ symbol: string }> = memo(({ symbol }) => {
  const [snap, setSnap] = React.useState<Record<string, any> | null>(null);
  React.useEffect(() => {
    if (!symbol) return;
    marketDataApi.getSnapshot(symbol).then((res: any) => {
      setSnap(res?.data || res || null);
    }).catch(() => {});
  }, [symbol]);
  if (!snap) return null;

  const items: Array<{ label: string; value: string; color?: string }> = [];
  if (snap.stage_label) items.push({ label: 'Stage', value: snap.stage_label });
  if (snap.current_stage_days) items.push({ label: 'Days', value: `${snap.current_stage_days}d` });
  if (snap.rsi != null) items.push({ label: 'RSI', value: Number(snap.rsi).toFixed(0), color: snap.rsi > 70 ? 'red.400' : snap.rsi < 30 ? 'green.400' : undefined });
  if (snap.pe_ttm != null) items.push({ label: 'P/E', value: Number(snap.pe_ttm).toFixed(1) });
  if (snap.rs_mansfield_pct != null) items.push({ label: 'RS', value: `${Number(snap.rs_mansfield_pct).toFixed(1)}%`, color: snap.rs_mansfield_pct >= 0 ? 'green.400' : 'red.400' });
  if (snap.atr_14 != null) items.push({ label: 'ATR', value: Number(snap.atr_14).toFixed(2) });
  if (snap.dividend_yield != null) items.push({ label: 'Yield', value: `${Number(snap.dividend_yield).toFixed(2)}%` });
  if (snap.sector) items.push({ label: 'Sector', value: snap.sector });

  const td: string[] = [];
  if (snap.td_buy_complete) td.push('Buy 9');
  if (snap.td_sell_complete) td.push('Sell 9');
  if (snap.td_buy_countdown >= 12) td.push(`BC${snap.td_buy_countdown}`);
  if (snap.td_sell_countdown >= 12) td.push(`SC${snap.td_sell_countdown}`);
  if (td.length) items.push({ label: 'TD', value: td.join(' ') });

  const gapsUp = snap.gaps_unfilled_up ?? 0;
  const gapsDn = snap.gaps_unfilled_down ?? 0;
  if (gapsUp || gapsDn) items.push({ label: 'Gaps', value: `${gapsUp}↑ ${gapsDn}↓` });

  if (!items.length) return null;
  return (
    <div className="flex flex-wrap gap-3 border-b border-border bg-muted/50 px-4 py-2">
      {items.map((item, i) => (
        <div key={i} className="flex items-center gap-1">
          <span className="text-xs text-muted-foreground">{item.label}</span>
          <span className={cn('text-xs font-semibold text-foreground', semanticTextColorClass(item.color))}>
            {item.value}
          </span>
        </div>
      ))}
    </div>
  );
});

const ChartSlidePanelInner: React.FC<{ symbol: string | null; onClose: () => void }> = ({ symbol, onClose }) => {
  const chartHeight = typeof window !== 'undefined' ? window.innerHeight - 100 : 400;
  const portfolioSymbols = React.useContext(PortfolioSymbolsContext);
  const isHeld = symbol ? symbol in (portfolioSymbols || {}) : false;
  const [tradeOpen, setTradeOpen] = useState(false);

  const posData = symbol && portfolioSymbols?.[symbol];
  const sharesHeld = posData ? posData.quantity : 0;
  const currentPrice = posData && posData.quantity > 0 ? posData.market_value / posData.quantity : 0;
  const averageCost = posData && posData.quantity > 0 ? posData.cost_basis / posData.quantity : undefined;

  return (
    <>
      <Dialog.Root open={!!symbol} onOpenChange={(open) => { if (!open) onClose(); }}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0" />
          <Dialog.Content
            className={cn(
              'fixed top-0 right-0 z-50 flex h-[100dvh] flex-col border-l border-border bg-card p-0 shadow-xl outline-none',
              'w-[95vw] max-w-[1100px] lg:w-[60vw]',
              'data-[state=closed]:animate-out data-[state=closed]:slide-out-to-right data-[state=open]:animate-in data-[state=open]:slide-in-from-right duration-200'
            )}
            onOpenAutoFocus={(e) => e.preventDefault()}
            aria-describedby={undefined}
          >
            <Dialog.Title className="sr-only">
              {symbol ? `Chart ${symbol}` : 'Chart'}
            </Dialog.Title>
            <div className="flex items-center justify-between border-b border-border px-4 py-2">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold">{symbol}</span>
                {isHeld && (
                  <Badge variant="secondary" className="text-xs font-normal">Held</Badge>
                )}
                <Button size="xs" variant="outline" onClick={() => setTradeOpen(true)}>
                  Trade
                </Button>
              </div>
              <Button type="button" size="icon-sm" variant="ghost" aria-label="Close chart" onClick={onClose}>
                <X className="size-4" />
              </Button>
            </div>
            {symbol && <SnapshotContextStrip symbol={symbol} />}
            <div className="min-h-0 flex-1 overflow-hidden p-0">
              {symbol && (
                <React.Suspense
                  fallback={(
                    <div className="flex items-center gap-2 p-4">
                      <Loader2 className="size-4 animate-spin text-muted-foreground" aria-hidden />
                      <span className="text-sm text-muted-foreground">Loading chart…</span>
                    </div>
                  )}
                >
                  <TradingViewChartLazy
                    symbol={symbol}
                    onClose={onClose}
                    height={chartHeight}
                    showHeader={false}
                    showControls={false}
                    autosize
                  />
                </React.Suspense>
              )}
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {tradeOpen && symbol && (
        <TradeModal
          isOpen={tradeOpen}
          symbol={symbol}
          currentPrice={currentPrice || 0}
          sharesHeld={sharesHeld}
          averageCost={averageCost}
          onClose={() => setTradeOpen(false)}
        />
      )}
    </>
  );
};

export const ChartSlidePanel = memo(ChartSlidePanelInner);
