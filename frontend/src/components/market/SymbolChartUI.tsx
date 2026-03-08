/**
 * Shared symbol chart UI: clickable symbol links that open a TradingView chart slide panel.
 * Used by Market Dashboard and Market Tracked pages.
 * Optimized: memoized components, stable callbacks, lazy-loaded chart.
 */
import React, { useCallback, useMemo, memo, useState } from 'react';
import {
  Badge,
  Box,
  Button,
  HStack,
  Spinner,
  Text,
  DialogRoot,
  DialogBackdrop,
  DialogPositioner,
  DialogContent,
  DialogBody,
  IconButton,
  PopoverRoot,
  PopoverTrigger,
  PopoverPositioner,
  PopoverContent,
  PopoverBody,
} from '@chakra-ui/react';
import { FiX } from 'react-icons/fi';
import { marketDataApi } from '../../services/api';
import TradeModal from '../orders/TradeModal';

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
  const lineColor = change != null ? (change >= 0 ? '#16A34A' : '#DC2626') : '#6366F1';
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
    <Box p={2} minW="160px">
      <HStack justify="space-between" mb="2px">
        <Text fontSize="xs" fontWeight="semibold">{symbol}</Text>
        {last != null && change != null && (
          <Text fontSize="10px" fontWeight="medium" color={change >= 0 ? 'green.500' : 'red.500'}>
            {change >= 0 ? '+' : ''}{change.toFixed(1)}%
          </Text>
        )}
      </HStack>
      {loading ? (
        <HStack gap={1}>
          <Spinner size="xs" />
          <Text fontSize="xs" color="fg.muted">Loading...</Text>
        </HStack>
      ) : pts.length >= 2 ? (
        <>
          <svg width={SVG_W} height={SVG_H} style={{ display: 'block' }}>
            <path d={pathD} fill="none" stroke={lineColor} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          {last != null && (
            <Text fontSize="10px" color="fg.muted" mt="2px">${last.toFixed(2)}</Text>
          )}
        </>
      ) : (
        <Text fontSize="xs" color="fg.muted">No data available</Text>
      )}
    </Box>
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
    <PopoverRoot open={hovered} positioning={{ placement: 'top' }} lazyMount unmountOnExit>
      <PopoverTrigger asChild>
        <Text
          as="span"
          role="button"
          tabIndex={0}
          fontWeight="medium"
          cursor="pointer"
          _hover={{ textDecoration: 'underline', color: 'brand.500' }}
          onMouseEnter={onEnter}
          onMouseLeave={onLeave}
          onClick={handleClick}
          onKeyDown={handleKeyDown}
        >
          {children ?? symbol}
          {isHeld && <Badge size="xs" colorPalette="blue" variant="subtle" ml={1}>Held</Badge>}
        </Text>
      </PopoverTrigger>
      <PopoverPositioner>
        <PopoverContent
          borderRadius="lg"
          shadow="lg"
          borderWidth="1px"
          borderColor="border.subtle"
          bg="bg.panel"
          w="auto"
          onMouseEnter={keepOpen}
          onMouseLeave={onLeave}
        >
          <PopoverBody p={0}>
            <SparklinePopoverContent symbol={symbol} />
          </PopoverBody>
        </PopoverContent>
      </PopoverPositioner>
    </PopoverRoot>
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
    <HStack gap={3} px={4} py={2} bg="bg.subtle" borderBottomWidth="1px" borderColor="border.subtle" flexWrap="wrap">
      {items.map((item, i) => (
        <HStack key={i} gap={1}>
          <Text fontSize="xs" color="fg.muted">{item.label}</Text>
          <Text fontSize="xs" fontWeight="semibold" color={item.color || 'fg.default'}>{item.value}</Text>
        </HStack>
      ))}
    </HStack>
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
    <DialogRoot open={!!symbol} onOpenChange={(d) => { if (!d.open) onClose(); }}>
      <DialogBackdrop bg="blackAlpha.400" />
      <DialogPositioner
        position="fixed"
        top="0"
        right="0"
        bottom="0"
        display="flex"
        justifyContent="flex-end"
        alignItems="stretch"
        p={0}
        m={0}
      >
        <DialogContent
          position="relative"
          w={{ base: '95vw', lg: '60vw' }}
          maxW="1100px"
          h="100vh"
          borderRadius={0}
          borderLeft="1px"
          borderColor="border.subtle"
          bg="bg.panel"
          m={0}
          p={0}
          overflow="hidden"
        >
          <HStack
            justify="space-between"
            align="center"
            px={4}
            py={2}
            borderBottomWidth="1px"
            borderColor="border.subtle"
          >
            <HStack gap={2}>
              <Text fontWeight="semibold" fontSize="sm">{symbol}</Text>
              {isHeld && <Badge size="sm" colorPalette="blue" variant="subtle">Held</Badge>}
              <Button
                size="xs"
                variant="outline"
                colorPalette="blue"
                onClick={() => setTradeOpen(true)}
              >
                Trade
              </Button>
            </HStack>
            <IconButton aria-label="Close chart" size="sm" variant="ghost" onClick={onClose}>
              <FiX />
            </IconButton>
          </HStack>
          {symbol && <SnapshotContextStrip symbol={symbol} />}
          <DialogBody p={0} flex="1" overflow="hidden">
            {symbol && (
              <React.Suspense fallback={<HStack p={4}><Spinner size="sm" /> <Text fontSize="sm">Loading chart…</Text></HStack>}>
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
          </DialogBody>
        </DialogContent>
      </DialogPositioner>

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
    </DialogRoot>
  );
};

export const ChartSlidePanel = memo(ChartSlidePanelInner);
